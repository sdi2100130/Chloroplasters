
# XRP Tower Garden Control System
# Chloroplasters


from xrp import *
from machine import Pin, I2C
import time


# ============================================
# PIN SETUP - XRP Controller
# ============================================

# --- I2C bus configuration ---
# Both ADS1015 and SHT31 share the same I2C bus (Qwiic 0).
# Daisy-chain SHT31 from ADS1015's second Qwiic connector.
I2C_SDA_PIN = 4    # IO4 -> Qwiic 0 SDA
I2C_SCL_PIN = 5    # IO5 -> Qwiic 0 SCL

# I2C device addresses
ADS1015_ADDR = 0x48   # Default address of SparkFun ADS1015
SHT31_ADDR   = 0x44   # Default address of SHT31


# --- Analog sensor channels on ADS1015 ---
# These are NOT XRP pins - they're channel numbers on the ADS1015 chip.
# Note: No soil moisture sensor - Tower Garden is hydroponic.
PH_CHANNEL        = 0    # ADS1015 A0 -> Generic BNC pH sensor
EC_CHANNEL        = 1    # ADS1015 A1 -> DFRobot TDS Sensor SEN0244
TURBIDITY_CHANNEL = 2    # ADS1015 A2 -> DFRobot Turbidity SEN0189 (via voltage divider 5V->3.3V!)
# Channel A3 reserved for future expansion


# --- Digital sensors ---
FLOW_SENSOR_PIN     = 2    # IO2  -> YF-S201 Flow sensor (yellow wire, VCC=5V)
WATER_TEMP_PIN      = 20   # IO20 -> DS18B20 waterproof temperature sensor (1-Wire) ΘΕΡΜΟΚΡΑΣΙΑΣ!!!! 
                           #         VCC=3.3V, GND=GND, needs 4.7kΩ pull-up resistor!


# --- Outputs: SERVOS for chemical dosing (syringe pump system) ---
# Each servo pushes a 20mL syringe to dispense ~1mL doses.
PH_ACID_SERVO_PIN     = 6    # IO6  (Servo 1) -> Servo for citric acid syringe (pH↓)
PH_BASE_SERVO_PIN     = 7    # IO7  (Servo 3) -> Servo for potassium bicarbonate syringe (pH↑)
NUTRIENT_SERVO_PIN    = 27   # IO27 (Servo 4) -> Servo for nutrient solution syringe (EC↑)


# --- Outputs: PUMPS & FAN (via relay modules - NEVER direct!) ---
WATER_PUMP_PIN       = 12   # IO12 -> Relay 1 (main irrigation pump)
FRESH_WATER_PUMP_PIN = 18   # IO18 -> Relay 2 (fresh water pump for dilution)
FAN_PIN              = 19   # IO19 -> Relay 3 (cooling fan)


# --- Outputs: LEDs (with 220Ω current-limiting resistors) ---
RED_LIGHT_PIN    = 22   # IO22 -> Red LED (tank empty / pump failure / syringes empty)
ORANGE_LIGHT_PIN = 23   # IO23 -> Orange LED (water needs replacing)


# --- Stop button (built-in USER button on XRP) ---
STOP_BUTTON_PIN = 36    # IO36 -> Built-in USER button on XRP

# =========================================================
# THRESHOLD VALUES (from project flowcharts)
# =========================================================

MOISTURE_MIN      = 35     # %    - below this -> pump ON
MOISTURE_TARGET   = 60     # %    - at this    -> pump OFF
PH_MIN            = 5.5    # pH   - too low
PH_MAX            = 6.5    # pH   - too high
EC_MIN            = 1.0    # mS/cm - too few nutrients
EC_MAX            = 2.0    # mS/cm - too many nutrients
TURBIDITY_MAX     = 30     # NTU   - water too dirty
WATER_TEMP_MAX    = 30     # °C    - turn fan ON
WATER_TEMP_MIN    = 26     # °C    - turn fan OFF
TANK_HUMIDITY_MIN = 5      # %     - below this -> tank empty


# =========================================================
# I2C BUS INITIALIZATION
# =========================================================

i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)


# =========================================================
# ADS1015 ANALOG-TO-DIGITAL CONVERTER FUNCTIONS
# =========================================================
# The ADS1015 is a 12-bit ADC with 4 channels (A0-A3).
# We talk to it over I2C to read analog voltages.

# ADS1015 register addresses
ADS1015_REG_CONVERSION = 0x00
ADS1015_REG_CONFIG     = 0x01

# ADS1015 configuration bits for single-ended reads
# Format: OS=1 (start conversion), MUX (channel), PGA=4.096V, MODE=single-shot,
#         DR=1600 SPS, COMP_QUE=disabled
ADS1015_CONFIG_BASE = 0x8583

# Channel selection bits (MUX bits in config register)
# A0=100, A1=101, A2=110, A3=111 (shifted to bits 14-12)
ADS1015_MUX = {
    0: 0x4000,  # A0
    1: 0x5000,  # A1
    2: 0x6000,  # A2
    3: 0x7000,  # A3
}

def ads1015_read_channel(channel):
    """
    Read voltage from one channel (0-3) of the ADS1015.
    Returns voltage in volts (0.0 to ~4.096V), or None on error.
    """
    if channel not in ADS1015_MUX:
        print("Invalid ADS1015 channel:", channel)
        return None

    try:
        # Build the config register value for this channel
        config = ADS1015_CONFIG_BASE | ADS1015_MUX[channel]

        # Write config register to start conversion
        config_bytes = bytes([
            ADS1015_REG_CONFIG,
            (config >> 8) & 0xFF,
            config & 0xFF
        ])
        i2c.writeto(ADS1015_ADDR, config_bytes)

        # Wait for conversion to complete (~1ms for 1600 SPS)
        time.sleep(0.005)

        # Point to conversion register
        i2c.writeto(ADS1015_ADDR, bytes([ADS1015_REG_CONVERSION]))

        # Read 2 bytes from conversion register
        data = i2c.readfrom(ADS1015_ADDR, 2)

        # ADS1015 returns 12-bit value in upper bits of 16-bit register
        raw = (data[0] << 8) | data[1]
        raw = raw >> 4  # Shift right 4 bits to get 12-bit value (0-2047 for positive)

        # Handle negative values (two's complement, but we expect positives here)
        if raw > 2047:
            raw = raw - 4096

        # Convert raw to voltage (PGA=4.096V, so 1 LSB = 4.096/2048 = 2mV)
        voltage = raw * 4.096 / 2048
        return voltage

    except Exception as e:
        print("ADS1015 read error on channel", channel, ":", e)
        return None


# =========================================================
# SHT31 TEMPERATURE & HUMIDITY SENSOR (I2C)
# =========================================================

def read_sht31():
    """
    Read temperature and humidity from SHT31.
    Returns tuple: (temperature_C, humidity_percent)
    Returns (None, None) on read failure.
    """
    try:
        # Send measurement command (high repeatability, no clock stretching)
        i2c.writeto(SHT31_ADDR, b'\x24\x00')
        time.sleep(0.02)  # Wait ~20ms for measurement
        data = i2c.readfrom(SHT31_ADDR, 6)

        temp_raw = (data[0] << 8) | data[1]
        hum_raw  = (data[3] << 8) | data[4]

        temperature = -45 + (175 * temp_raw / 65535)
        humidity    = 100 * hum_raw / 65535
        return (temperature, humidity)
    except Exception as e:
        print("SHT31 read error:", e)
        return (None, None)


# =========================================================
# FLOW SENSOR PULSE COUNTING (interrupt-based)
# =========================================================

flow_pulse_count = 0

def flow_pulse_handler(pin):
    """Called automatically on each pulse from the flow sensor."""
    global flow_pulse_count
    flow_pulse_count += 1

flow_pin = Pin(FLOW_SENSOR_PIN, Pin.IN, Pin.PULL_UP)
flow_pin.irq(trigger=Pin.IRQ_RISING, handler=flow_pulse_handler)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def read_digital(pin):
    """Read digital pin value."""
    return digitalRead(pin)

def is_button_pressed():
    """Check if STOP button is pressed."""
    return read_digital(STOP_BUTTON_PIN) == 1

def set_output(pin, state):
    """Turn output pin ON (1) or OFF (0)."""
    digitalWrite(pin, state)


# =========================================================
# SENSOR READING FUNCTIONS (using ADS1015 for analog)
# =========================================================

def get_moisture():
    """
    Read soil moisture as percentage (%) via ADS1015 channel A0.
    Capacitive sensors output higher voltage when DRY,
    so we invert: lower voltage = more moisture.
    """
    voltage = ads1015_read_channel(SOIL_MOISTURE_CHANNEL)
    if voltage is None:
        return -999

    # Calibrate these voltage values for YOUR specific sensor:
    # - Test in dry air -> note the voltage (e.g. ~3.0V)
    # - Test in water  -> note the voltage (e.g. ~1.5V)
    DRY_VOLTAGE = 3.0    # Voltage when sensor is in dry air
    WET_VOLTAGE = 1.5    # Voltage when sensor is fully wet

    # Map voltage to percentage (clamp to 0-100)
    percent = (DRY_VOLTAGE - voltage) / (DRY_VOLTAGE - WET_VOLTAGE) * 100
    if percent < 0:
        percent = 0
    if percent > 100:
        percent = 100
    return percent

def get_ph():
    """
    Read pH value via ADS1015 channel A1.
    Most pH probes output ~2.5V at pH 7, with ~59mV per pH unit.
    CALIBRATE with pH 4.0 and pH 7.0 buffer solutions for accuracy!
    """
    voltage = ads1015_read_channel(PH_CHANNEL)
    if voltage is None:
        return -999

    # Standard pH conversion formula (calibrate for your sensor!)
    ph = 7 + (2.5 - voltage) / 0.18  # 0.18V per pH unit (typical)
    return ph

def get_ec():
    """
    Read electrical conductivity in mS/cm via ADS1015 channel A2.
    Calibrate with a known EC standard solution!
    """
    voltage = ads1015_read_channel(EC_CHANNEL)
    if voltage is None:
        return -999

    # Simple linear conversion (calibrate for your sensor!)
    ec = voltage * 2.0  # Example - adjust based on calibration
    return ec

def get_turbidity():
    """
    Read turbidity in NTU via ADS1015 channel A3.
    DFRobot Gravity sensor: clearer water = higher voltage.
    NOTE: Sensor output is 5V, scaled down by voltage divider to ~3.3V max.
    """
    voltage = ads1015_read_channel(TURBIDITY_CHANNEL)
    if voltage is None:
        return -999

    # If voltage divider is 1kΩ/2kΩ, multiply by ~1.5 to get original sensor voltage
    actual_voltage = voltage * 1.5  # Adjust based on your divider ratio

    # Approximate turbidity formula (calibrate for your sensor!)
    if actual_voltage < 0.1:
        ntu = 3000  # Sensor disconnected or extremely dirty
    else:
        ntu = 3000 / actual_voltage  # Calibrate against known samples!
    return ntu

def get_water_temp():
    """Read water temperature (°C) from SHT31."""
    temp, _ = read_sht31()
    if temp is None:
        return -999
    return temp

def get_humidity():
    """Read tank-area humidity (%) from SHT31. Used to detect empty tank."""
    _, hum = read_sht31()
    if hum is None:
        return -999
    return hum

def get_flow():
    """
    Get flow sensor pulse count from last interval, then reset.
    Returns 0 if no water is flowing.
    """
    global flow_pulse_count
    pulses = flow_pulse_count
    flow_pulse_count = 0
    return pulses


# =========================================================
# HOMEOSTASIS FUNCTIONS
# =========================================================

def ph_homeostasis():
    """pH homeostasis (flowchart p.38)."""
    ph = get_ph()
    print("pH level:", ph)

    if ph == -999:
        print("pH sensor error - skipping")
        return

    if ph > PH_MAX:
        print("pH too HIGH - adding citric acid")
        set_output(PH_PUMP_ACID_PIN, 1)
        time.sleep(2)
        set_output(PH_PUMP_ACID_PIN, 0)
        print("Citric acid added")

    elif ph < PH_MIN:
        print("pH too LOW - adding potassium bicarbonate")
        set_output(PH_PUMP_BASE_PIN, 1)
        time.sleep(2)
        set_output(PH_PUMP_BASE_PIN, 0)
        print("Potassium bicarbonate added")

    else:
        print("pH OK (5.5 - 6.5)")

def conductivity_homeostasis():
    """EC homeostasis (flowchart p.38)."""
    ec = get_ec()
    print("EC level:", ec, "mS/cm")

    if ec == -999:
        print("EC sensor error - skipping")
        return

    if ec < EC_MIN:
        print("EC too LOW - adding nutrient solution")
        set_output(NUTRIENT_PUMP_PIN, 1)
        time.sleep(3)
        set_output(NUTRIENT_PUMP_PIN, 0)
        print("Nutrients added")

    elif ec > EC_MAX:
        print("EC too HIGH - adding fresh water (dilution)")
        set_output(FRESH_WATER_PUMP_PIN, 1)
        time.sleep(5)
        set_output(FRESH_WATER_PUMP_PIN, 0)
        print("Fresh water added")

    else:
        print("EC OK (1.0 - 2.0 mS/cm)")

def turbidity_homeostasis():
    """Turbidity homeostasis (flowchart p.39)."""
    turbidity = get_turbidity()
    print("Turbidity:", turbidity, "NTU")

    if turbidity == -999:
        print("Turbidity sensor error - skipping")
        return

    if turbidity > TURBIDITY_MAX:
        print("Water DIRTY - turning ON orange warning light")
        set_output(ORANGE_LIGHT_PIN, 1)
    else:
        print("Water clarity OK")
        set_output(ORANGE_LIGHT_PIN, 0)

def flow_homeostasis():
    """Flow homeostasis (flowchart p.39)."""
    flow = get_flow()
    print("Flow rate (pulses):", flow)

    if flow == 0:
        print("NO WATER FLOW detected!")
        humidity = get_humidity()
        print("Tank humidity:", humidity, "%")

        if humidity != -999 and humidity < TANK_HUMIDITY_MIN:
            print("TANK EMPTY - turning ON red warning light")
            set_output(RED_LIGHT_PIN, 1)
        else:
            print("Pump may be broken - attempting restart")
            set_output(WATER_PUMP_PIN, 0)
            time.sleep(2)
            set_output(WATER_PUMP_PIN, 1)
            time.sleep(3)

            new_flow = get_flow()
            if new_flow > 0:
                print("Pump restart SUCCESSFUL")
                set_output(RED_LIGHT_PIN, 0)
            else:
                print("Pump restart FAILED - manual check needed")
                set_output(RED_LIGHT_PIN, 1)

def watertemp_homeostasis():
    """Water temperature homeostasis (flowchart p.40)."""
    temp = get_water_temp()
    print("Water temperature:", temp, "°C")

    if temp == -999:
        print("Temperature sensor error - skipping")
        return

    if temp > WATER_TEMP_MAX:
        print("Water too HOT - activating cooling fan")
        set_output(FAN_PIN, 1)
    elif temp < WATER_TEMP_MIN:
        print("Water cooled down - turning OFF fan")
        set_output(FAN_PIN, 0)
    else:
        print("Water temperature OK")


# =========================================================
# IRRIGATION CONTROL
# =========================================================

def check_and_water():
    """Soil moisture check & irrigation control (flowchart p.25)."""
    moisture = get_moisture()
    print("Soil moisture:", moisture, "%")

    if moisture == -999:
        print("Moisture sensor error - skipping irrigation check")
        return

    if moisture < MOISTURE_MIN:
        print("Soil too DRY - starting water pump")
        set_output(WATER_PUMP_PIN, 1)
    elif moisture >= MOISTURE_TARGET:
        print("Soil moist enough - stopping water pump")
        set_output(WATER_PUMP_PIN, 0)


# =========================================================
# MAIN PROGRAM
# =========================================================

def main():
    print("=" * 50)
    print("Chloroplasters Tower Garden - Starting...")
    print("=" * 50)

    # Initialize all outputs to OFF for safety
    set_output(WATER_PUMP_PIN, 0)
    set_output(PH_PUMP_ACID_PIN, 0)
    set_output(PH_PUMP_BASE_PIN, 0)
    set_output(NUTRIENT_PUMP_PIN, 0)
    set_output(FRESH_WATER_PUMP_PIN, 0)
    set_output(FAN_PIN, 0)
    set_output(RED_LIGHT_PIN, 0)
    set_output(ORANGE_LIGHT_PIN, 0)

    time.sleep(2)

    # Scan I2C bus to verify devices are connected
    print("\nScanning I2C bus...")
    devices = i2c.scan()
    print("Found I2C devices at addresses:", [hex(d) for d in devices])

    if ADS1015_ADDR in devices:
        print("ADS1015 detected at 0x48 -> OK")
    else:
        print("WARNING: ADS1015 NOT FOUND - check wiring on Qwiic 0!")

    if SHT31_ADDR in devices:
        print("SHT31 detected at 0x44 -> OK")
    else:
        print("WARNING: SHT31 NOT FOUND - check wiring on Qwiic 1!")

    # Quick initial sensor check
    t, h = read_sht31()
    if t is not None:
        print("Initial SHT31 reading -> Temp:", t, "°C, Humidity:", h, "%")

    # Main monitoring loop
    while True:
        print("\n" + "=" * 50)
        print("New monitoring cycle")
        print("=" * 50)

        # Check STOP button
        if is_button_pressed():
            print("STOP button pressed - shutting down system")
            set_output(WATER_PUMP_PIN, 0)
            set_output(FAN_PIN, 0)
            break

        print("\n--- Reading Sensors ---")

        # 1. Irrigation check
        check_and_water()

        # 2. pH check
        ph = get_ph()
        if ph != -999 and (ph < PH_MIN or ph > PH_MAX):
            print("pH out of range!")
            ph_homeostasis()
        else:
            print("pH within range (5.5 - 6.5)")

        # 3. EC check
        ec = get_ec()
        if ec != -999 and (ec < EC_MIN or ec > EC_MAX):
            print("EC out of range!")
            conductivity_homeostasis()
        else:
            print("EC within range (1.0 - 2.0 mS/cm)")

        # 4. Turbidity check
        turbidity = get_turbidity()
        if turbidity != -999 and turbidity > TURBIDITY_MAX:
            print("Turbidity too high!")
            turbidity_homeostasis()
        else:
            print("Turbidity OK (< 30 NTU)")
            set_output(ORANGE_LIGHT_PIN, 0)

        # 5. Water temperature check
        temp = get_water_temp()
        if temp != -999 and temp > WATER_TEMP_MAX:
            print("Water too hot!")
            watertemp_homeostasis()
        else:
            print("Water temperature OK")
            if temp != -999 and temp < WATER_TEMP_MIN:
                set_output(FAN_PIN, 0)

        # 6. Flow check
        flow = get_flow()
        if flow == 0:
            print("No flow detected!")
            flow_homeostasis()
        else:
            print("Water flow OK (", flow, "pulses)")
            set_output(RED_LIGHT_PIN, 0)

        print("\n--- Cycle complete. Waiting 10 seconds ---")
        time.sleep(10)

    print("System stopped. Goodbye!")


=========================================

main()
