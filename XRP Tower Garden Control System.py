# XRP Tower Garden Control System
# Chloroplasters 

from xrp import *
from machine import Pin, I2C
import time


# ============================================
# PIN SETUP
# ============================================

# --- I2C bus for SHT31 (temperature + humidity) ---
SHT31_SDA_PIN = 13         # Green wire -> IO13
SHT31_SCL_PIN = 14         # Yellow wire -> IO14
SHT31_ADDR    = 0x44       # Default I2C address for SHT31

# --- Analog sensors ---
SOIL_MOISTURE_PIN  = 0     # Capacitive soil moisture sensor
PH_SENSOR_PIN      = 1     # pH sensor (analog)
EC_SENSOR_PIN      = 2     # Conductivity sensor (analog)
TURBIDITY_SENSOR_PIN = 9   # DFRobot Gravity Turbidity -> IO9 (blue wire)

# --- Digital sensors ---
FLOW_SENSOR_PIN    = 2     # Water flow sensor pulse output -> IO2 (yellow wire)

# --- Outputs (pumps, lights, fan) ---
WATER_PUMP_PIN       = 0   # Main irrigation pump
PH_PUMP_ACID_PIN     = 1   # Pump for citric acid (pH too high)
PH_PUMP_BASE_PIN     = 2   # Pump for potassium bicarbonate (pH too low)
NUTRIENT_PUMP_PIN    = 3   # Pump for nutrient solution
FRESH_WATER_PUMP_PIN = 4   # Pump for fresh water (dilution)
FAN_PIN              = 5   # Cooling fan for water
RED_LIGHT_PIN        = 6   # Red LED - tank empty warning
ORANGE_LIGHT_PIN     = 7   # Orange LED - replace water warning

# Button to stop the system
STOP_BUTTON_PIN = 8


# ============================================
# THRESHOLD VALUES - From flowcharts
# ============================================

MOISTURE_MIN     = 35      # % - turn pump ON below this
MOISTURE_TARGET  = 60      # % - turn pump OFF at this
PH_MIN           = 5.5     # pH too low
PH_MAX           = 6.5     # pH too high
EC_MIN           = 1.0     # mS/cm - too little nutrients
EC_MAX           = 2.0     # mS/cm - too many nutrients
TURBIDITY_MAX    = 30      # NTU - water too dirty
WATER_TEMP_MAX   = 30      # °C - turn fan ON
WATER_TEMP_MIN   = 26      # °C - turn fan OFF
TANK_HUMIDITY_MIN = 5      # % - below this means tank is empty


# ============================================
# I2C SETUP FOR SHT31
# ============================================

# Initialize I2C bus once at startup
i2c = I2C(0, scl=Pin(SHT31_SCL_PIN), sda=Pin(SHT31_SDA_PIN), freq=100000)


# ============================================
# FLOW SENSOR PULSE COUNTING
# ============================================
# The flow sensor outputs digital pulses - one pulse per small amount of water.
# We count pulses using an interrupt so we don't miss any.

flow_pulse_count = 0

def flow_pulse_handler(pin):
    """Interrupt handler - called every time a pulse arrives from flow sensor."""
    global flow_pulse_count
    flow_pulse_count += 1

# Set up the flow sensor pin with an interrupt on rising edge
flow_pin = Pin(FLOW_SENSOR_PIN, Pin.IN, Pin.PULL_UP)
flow_pin.irq(trigger=Pin.IRQ_RISING, handler=flow_pulse_handler)


# ============================================
# HELPER FUNCTIONS
# ============================================

def read_sensor(pin):
    """Read analog sensor value (0-1023)"""
    return analogRead(pin)

def read_digital(pin):
    """Read digital sensor value"""
    return digitalRead(pin)

def is_button_pressed():
    """Check if stop button is pressed"""
    return read_digital(STOP_BUTTON_PIN) == 1

def set_output(pin, state):
    """Turn output pin ON (1) or OFF (0)"""
    digitalWrite(pin, state)


# ============================================
# SHT31 SENSOR FUNCTIONS (I2C)
# ============================================

def read_sht31():
    """
    Read temperature and humidity from the SHT31 sensor over I2C.
    Returns a tuple: (temperature_C, humidity_percent)
    Returns (None, None) on read failure.
    """
    try:
        # Send measurement command: high repeatability, no clock stretching
        i2c.writeto(SHT31_ADDR, b'\x24\x00')
        time.sleep(0.02)  # Wait ~20ms for measurement
        data = i2c.readfrom(SHT31_ADDR, 6)

        # Bytes 0-1: temperature, byte 2: CRC
        # Bytes 3-4: humidity, byte 5: CRC
        temp_raw = (data[0] << 8) | data[1]
        hum_raw  = (data[3] << 8) | data[4]

        # Convert per SHT31 datasheet
        temperature = -45 + (175 * temp_raw / 65535)
        humidity    = 100 * hum_raw / 65535
        return (temperature, humidity)
    except Exception as e:
        print("SHT31 read error:", e)
        return (None, None)


# ============================================
# SENSOR READING FUNCTIONS
# ============================================

def get_moisture():
    """Read soil moisture percentage"""
    raw = read_sensor(SOIL_MOISTURE_PIN)
    # Capacitive: higher raw = drier, so invert
    percent = 100 - (raw / 1023 * 100)
    return percent

def get_ph():
    """Read pH value from sensor"""
    raw = read_sensor(PH_SENSOR_PIN)
    voltage = raw / 1023 * 3.3  # XRP uses 3.3V
    ph = 7 + (2.5 - voltage) * 3.5  # Adjust formula based on your sensor
    return ph

def get_ec():
    """Read electrical conductivity in mS/cm"""
    raw = read_sensor(EC_SENSOR_PIN)
    voltage = raw / 1023 * 3.3
    ec = voltage * 2  # Example conversion - calibrate!
    return ec

def get_turbidity():
    """
    Read turbidity from DFRobot Gravity Analog Turbidity Sensor (IO9).
    Sensor is powered at 5V but output is read by the XRP ADC.
    Cleaner water -> higher voltage; dirty water -> lower voltage.
    """
    raw = read_sensor(TURBIDITY_SENSOR_PIN)
    voltage = raw / 1023 * 3.3
    # DFRobot's typical curve (calibrate for your unit):
    # NTU = -1120.4 * V^2 + 5742.3 * V - 4353.8  (when V > ~2.5)
    # For simplicity and safety, use a basic inverse relationship:
    if voltage < 0.1:
        ntu = 3000  # Very dirty / sensor disconnected
    else:
        ntu = 3000 / voltage  # Calibrate against known samples!
    return ntu

def get_water_temp():
    """Read water temperature in Celsius from SHT31."""
    temp, _ = read_sht31()
    if temp is None:
        return -999  # Error sentinel
    return temp

def get_humidity():
    """Read humidity (%) from SHT31 - used to check if tank is empty."""
    _, hum = read_sht31()
    if hum is None:
        return -999  # Error sentinel
    return hum

def get_flow():
    """
    Get water flow by reading the pulse count from the last interval.
    Returns the number of pulses counted since last call, then resets.
    A value of 0 means no water is flowing.
    """
    global flow_pulse_count
    pulses = flow_pulse_count
    flow_pulse_count = 0  # Reset for next measurement window
    return pulses


# ============================================
# HOMEOSTASIS FUNCTIONS - From flowcharts
# ============================================

def ph_homeostasis():
    """pH homeostasis (flowchart p.38)"""
    ph = get_ph()
    print("pH level:", ph)

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
        print("pH is OK (5.5 - 6.5)")

def conductivity_homeostasis():
    """EC homeostasis (flowchart p.38)"""
    ec = get_ec()
    print("EC level:", ec, "mS/cm")

    if ec < EC_MIN:
        print("EC too LOW - adding nutrient solution")
        set_output(NUTRIENT_PUMP_PIN, 1)
        time.sleep(3)
        set_output(NUTRIENT_PUMP_PIN, 0)
        print("Nutrients added")

    elif ec > EC_MAX:
        print("EC too HIGH - adding fresh water to dilute")
        set_output(FRESH_WATER_PUMP_PIN, 1)
        time.sleep(5)
        set_output(FRESH_WATER_PUMP_PIN, 0)
        print("Fresh water added")

    else:
        print("EC is OK (1.0 - 2.0 mS/cm)")

def turbidity_homeostasis():
    """Turbidity homeostasis (flowchart p.39)"""
    turbidity = get_turbidity()
    print("Turbidity:", turbidity, "NTU")

    if turbidity > TURBIDITY_MAX:
        print("Water is DIRTY - turn on ORANGE warning light")
        set_output(ORANGE_LIGHT_PIN, 1)
    else:
        print("Water clarity is OK")
        set_output(ORANGE_LIGHT_PIN, 0)

def flow_homeostasis():
    """
    Flow homeostasis (flowchart p.39)
    - Flow = 0 + tank humidity very low -> tank empty (red light)
    - Flow = 0 + humidity normal       -> pump issue, attempt restart
    """
    flow = get_flow()
    print("Flow rate (pulses):", flow)

    if flow == 0:
        print("NO WATER FLOW detected!")
        humidity = get_humidity()
        print("Tank humidity:", humidity, "%")

        if humidity != -999 and humidity < TANK_HUMIDITY_MIN:
            # Tank is empty
            print("TANK IS EMPTY - turn on RED warning light")
            set_output(RED_LIGHT_PIN, 1)
        else:
            # Tank has water but pump not working
            print("Pump may be broken - attempting restart")
            set_output(WATER_PUMP_PIN, 0)
            time.sleep(2)
            set_output(WATER_PUMP_PIN, 1)
            time.sleep(3)

            # Check if flow restored
            new_flow = get_flow()
            if new_flow > 0:
                print("Pump restart SUCCESSFUL")
                set_output(RED_LIGHT_PIN, 0)
            else:
                print("Pump restart FAILED - needs manual check")
                set_output(RED_LIGHT_PIN, 1)

def watertemp_homeostasis():
    """Water temperature homeostasis (flowchart p.40)"""
    temp = get_water_temp()
    print("Water temperature:", temp, "°C")

    if temp == -999:
        print("Temperature sensor error - skipping")
        return

    if temp > WATER_TEMP_MAX:
        print("Water too HOT - activating cooling fan")
        set_output(FAN_PIN, 1)

    elif temp < WATER_TEMP_MIN:
        print("Water cooled down - turning off fan")
        set_output(FAN_PIN, 0)

    else:
        print("Water temperature is OK")


# ============================================
# MAIN IRRIGATION FUNCTION
# ============================================

def check_and_water():
    """Main irrigation control (flowchart p.25)"""
    moisture = get_moisture()
    print("Soil moisture:", moisture, "%")

    if moisture < MOISTURE_MIN:
        print("Soil too DRY - starting water pump")
        set_output(WATER_PUMP_PIN, 1)

    elif moisture >= MOISTURE_TARGET:
        print("Soil moist enough - stopping water pump")
        set_output(WATER_PUMP_PIN, 0)


# ============================================
# MAIN PROGRAM - Matches flowchart p.36
# ============================================

def main():
    print("=" * 40)
    print("Chloroplasters Tower Garden Starting...")
    print("=" * 40)

    # Initialize all outputs to OFF
    set_output(WATER_PUMP_PIN, 0)
    set_output(PH_PUMP_ACID_PIN, 0)
    set_output(PH_PUMP_BASE_PIN, 0)
    set_output(NUTRIENT_PUMP_PIN, 0)
    set_output(FRESH_WATER_PUMP_PIN, 0)
    set_output(FAN_PIN, 0)
    set_output(RED_LIGHT_PIN, 0)
    set_output(ORANGE_LIGHT_PIN, 0)

    time.sleep(2)  # Startup delay

    # Quick sanity check on SHT31
    t, h = read_sht31()
    if t is not None:
        print("SHT31 OK -> temp:", t, "°C, humidity:", h, "%")
    else:
        print("WARNING: SHT31 not responding - check wiring on IO13/IO14")

    while True:
        print("\n" + "=" * 40)
        print("New monitoring cycle")
        print("=" * 40)

        # STEP 1: Check stop button (p.36)
        if is_button_pressed():
            print("STOP BUTTON PRESSED - Shutting down system")
            set_output(WATER_PUMP_PIN, 0)
            set_output(FAN_PIN, 0)
            break

        # STEP 2: Read sensors (p.36)
        print("\n--- Reading Sensors ---")

        # Always check irrigation first
        check_and_water()

        # STEP 3: pH check (p.36)
        ph = get_ph()
        if ph < PH_MIN or ph > PH_MAX:
            print("pH out of range! Calling ph_homeostasis()")
            ph_homeostasis()
        else:
            print("pH is within range (5.5 - 6.5)")

        # STEP 4: EC check (p.36)
        ec = get_ec()
        if ec < EC_MIN or ec > EC_MAX:
            print("EC out of range! Calling conductivity_homeostasis()")
            conductivity_homeostasis()
        else:
            print("EC is within range (1.0 - 2.0 mS/cm)")

        # STEP 5: Turbidity check (p.36)
        turbidity = get_turbidity()
        if turbidity > TURBIDITY_MAX:
            print("Turbidity too high! Calling turbidity_homeostasis()")
            turbidity_homeostasis()
        else:
            print("Turbidity is OK (< 30 NTU)")
            set_output(ORANGE_LIGHT_PIN, 0)

        # STEP 6: Water temperature check (p.37) - now from SHT31
        temp = get_water_temp()
        if temp != -999 and temp > WATER_TEMP_MAX:
            print("Water too hot! Calling watertemp_homeostasis()")
            watertemp_homeostasis()
        else:
            print("Water temperature OK or fan already handled")
            if temp != -999 and temp < WATER_TEMP_MIN:
                set_output(FAN_PIN, 0)

        # STEP 7: Flow check (p.37) - now from pulse-counting flow sensor on IO2
        flow = get_flow()
        if flow == 0:
            print("No flow detected! Calling flow_homeostasis()")
            flow_homeostasis()
        else:
            print("Water flow is OK (", flow, "pulses)")
            set_output(RED_LIGHT_PIN, 0)

        # STEP 8: Continue monitoring (p.36)
        print("\n--- Cycle complete. Waiting before next check ---")
        time.sleep(10)

    print("System stopped. Goodbye!")




main()
