# =========================================================
# Chloroplasters - Smart Tower Garden
# Main control program for SparkFun XRP (RP2350)
# =========================================================

from machine import Pin, I2C, PWM
import time
import onewire
import ds18x20

# =========================================================
# 1. PIN ASSIGNMENTS
# =========================================================

# --- I2C bus (ADS1015 + SHT31 via Qwiic) ---
I2C_SDA_PIN  = 4
I2C_SCL_PIN  = 5
ADS1015_ADDR = 0x48
SHT31_ADDR   = 0x44

# --- Analog channels on ADS1015 ---
PH_CHANNEL        = 0   # A0 -> pH sensor
EC_CHANNEL        = 1   # A1 -> EC/TDS sensor
TURBIDITY_CHANNEL = 2   # A2 -> Turbidity sensor (educational)

# --- Digital sensors ---
FLOW_SENSOR_PIN = 2     # YF-S201 flow sensor (interrupt)
WATER_TEMP_PIN  = 20    # DS18B20 waterproof (4.7kΩ pull-up!)

# --- Syringe servos (PWM) ---
PH_ACID_SERVO_PIN  = 6  # Citric acid (pH down)
PH_BASE_SERVO_PIN  = 7  # Potassium bicarbonate (pH up)
NUTRIENT_SERVO_PIN = 8  # Liquid fertilizer (EC up)

# --- Relay outputs ---
WATER_PUMP_PIN       = 12  # Main irrigation pump
FRESH_WATER_PUMP_PIN = 18  # Fresh water dilution (optional)
FAN_PIN              = 19  # Cooling fan

# --- Status LEDs ---
GREEN_LIGHT_PIN  = 21  # Normal operation
RED_LIGHT_PIN    = 22  # Safe mode / problem
ORANGE_LIGHT_PIN = 23  # Dirty water / warning

# --- User input ---
STOP_BUTTON_PIN = 36   # Built-in USER button

# =========================================================
# 2. THRESHOLDS & CONSTANTS
# =========================================================

# pH limits
PH_MIN = 5.5
PH_MAX = 6.5

# EC limits (mS/cm)
EC_MIN = 1.0
EC_MAX = 2.0

# Water temperature
WATER_TEMP_MAX = 30   # Turn fan ON
WATER_TEMP_MIN = 26   # Turn fan OFF

# Turbidity (NTU)
TURBIDITY_MAX = 30

# --- Irrigation (flow-based) ---
PULSES_PER_LITER    = 450   # YF-S201 calibration
WATER_TARGET_HOT    = 2.5   # Liters when hot/dry
WATER_TARGET_NORMAL = 2.0
WATER_TARGET_COLD   = 1.5

IRRIGATION_INTERVAL  = 1800  # Default: 30 min
WATER_TARGET_PULSES  = int(WATER_TARGET_NORMAL * PULSES_PER_LITER)

# Safety timeouts
PUMP_TIMEOUT_SECONDS = 300  # Max pump runtime
NO_FLOW_TIMEOUT      = 60   # Seconds with no pulses = problem

# --- Dosing ---
SERVO_1ML_ANGLE   = 20      # Degrees per 1mL dose (CALIBRATE!)
DOSE_MIXING_WAIT  = 300     # Wait 5 min between doses for mixing
MAX_DOSES_PER_CYCLE = 4     # Abort if not converging

# =========================================================
# 3. STATE VARIABLES
# =========================================================

last_water_time      = 0
is_watering          = False
watering_start_time  = 0
flow_pulse_count     = 0
last_pulse_seen_time = 0

last_ph_dose_time = 0
last_ec_dose_time = 0

# =========================================================
# 4. HARDWARE INITIALIZATION
# =========================================================

# I2C bus
i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)

# DS18B20 water temperature
ds_pin = Pin(WATER_TEMP_PIN)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
roms = ds_sensor.scan()
if not roms:
    print("WARNING: DS18B20 not found! Check 4.7kΩ pull-up resistor.")

# Flow sensor interrupt
def flow_pulse_handler(pin):
    global flow_pulse_count, last_pulse_seen_time
    flow_pulse_count += 1
    last_pulse_seen_time = time.time()

flow_pin = Pin(FLOW_SENSOR_PIN, Pin.IN, Pin.PULL_UP)
flow_pin.irq(trigger=Pin.IRQ_RISING, handler=flow_pulse_handler)

# =========================================================
# 5. ADS1015 LOW-LEVEL DRIVER
# =========================================================

ADS1015_REG_CONVERSION = 0x00
ADS1015_REG_CONFIG     = 0x01
ADS1015_CONFIG_BASE    = 0x8583
ADS1015_MUX = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}

def ads1015_read_channel(channel):
    """Read voltage from an ADS1015 channel (0-3). Returns None on failure."""
    if channel not in ADS1015_MUX:
        return None
    try:
        config = ADS1015_CONFIG_BASE | ADS1015_MUX[channel]
        config_bytes = bytes([ADS1015_REG_CONFIG, (config >> 8) & 0xFF, config & 0xFF])
        i2c.writeto(ADS1015_ADDR, config_bytes)
        time.sleep(0.005)
        i2c.writeto(ADS1015_ADDR, bytes([ADS1015_REG_CONVERSION]))
        data = i2c.readfrom(ADS1015_ADDR, 2)
        raw = (data[0] << 8) | data[1]
        raw = raw >> 4
        if raw > 2047:
            raw = raw - 4096
        return raw * 4.096 / 2048
    except Exception as e:
        print("ADS1015 error:", e)
        return None

# =========================================================
# 6. SENSOR READING FUNCTIONS
# =========================================================

def get_water_temp():
    """Read DS18B20 water temperature. Returns -999 on failure."""
    if not roms:
        return -999
    try:
        ds_sensor.convert_temp()
        time.sleep_ms(750)
        return ds_sensor.read_temp(roms[0])
    except:
        return -999

def get_ph():
    """Read pH from ADS1015 A0. Returns -999 on failure."""
    voltage = ads1015_read_channel(PH_CHANNEL)
    if voltage is None:
        return -999
    # CALIBRATE: pH = 7 + (V_ref - V_measured) / slope
    return 7 + (2.5 - voltage) / 0.18

def get_ec():
    """Read EC (mS/cm) from ADS1015 A1. Returns -999 on failure."""
    voltage = ads1015_read_channel(EC_CHANNEL)
    if voltage is None:
        return -999
    # CALIBRATE: simple linear approximation
    return voltage * 2.0

def get_turbidity():
    """Read turbidity (NTU) from ADS1015 A2. Returns -999 on failure."""
    voltage = ads1015_read_channel(TURBIDITY_CHANNEL)
    if voltage is None:
        return -999
    actual_voltage = voltage * 1.5
    if actual_voltage < 0.1:
        return 3000
    return 3000 / actual_voltage

def read_sht31():
    """Read SHT31 air temp & humidity. Returns (None, None) on failure."""
    try:
        i2c.writeto(SHT31_ADDR, b'\x24\x00')
        time.sleep(0.02)
        data = i2c.readfrom(SHT31_ADDR, 6)
        temp_raw = (data[0] << 8) | data[1]
        hum_raw  = (data[3] << 8) | data[4]
        temperature = -45 + (175 * temp_raw / 65535)
        humidity    = 100 * hum_raw / 65535
        return (temperature, humidity)
    except Exception as e:
        print("SHT31 error:", e)
        return (None, None)

# =========================================================
# 7. ACTUATOR FUNCTIONS
# =========================================================

def set_servo_angle(pin_num, angle):
    """Move servo to angle (0-180)."""
    pwm = PWM(Pin(pin_num))
    pwm.freq(50)
    min_duty = 1000
    max_duty = 9000
    duty = min_duty + int((angle / 180) * (max_duty - min_duty))
    pwm.duty_u16(duty)
    time.sleep(0.5)
    pwm.deinit()

def push_syringe(servo_pin):
    """Dispense 1mL from a syringe."""
    print("Dosing syringe on pin", servo_pin)
    set_servo_angle(servo_pin, SERVO_1ML_ANGLE)
    time.sleep(1)
    set_servo_angle(servo_pin, 0)

def set_output(pin_num, state):
    """Set a digital output pin ON (1) or OFF (0)."""
    p = Pin(pin_num, Pin.OUT)
    p.value(state)

# =========================================================
# 8. SAFETY & STATE HELPERS
# =========================================================

def is_button_pressed():
    p = Pin(STOP_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    return p.value() == 0

def wait_for_button_release():
    while is_button_pressed():
        time.sleep(0.05)

def all_outputs_off():
    """Force all pumps, fan, and watering state into a safe OFF condition."""
    global is_watering
    set_output(WATER_PUMP_PIN, 0)
    set_output(FRESH_WATER_PUMP_PIN, 0)
    set_output(FAN_PIN, 0)
    is_watering = False

def show_normal_state():
    set_output(RED_LIGHT_PIN, 0)
    set_output(GREEN_LIGHT_PIN, 1)

def show_safe_state():
    set_output(GREEN_LIGHT_PIN, 0)
    set_output(RED_LIGHT_PIN, 1)

# =========================================================
# 9. HOMEOSTASIS FUNCTIONS
# =========================================================

def ph_homeostasis():
    """Maintain pH between PH_MIN and PH_MAX."""
    global last_ph_dose_time
    ph = get_ph()
    print("pH level:", ph)
    if ph == -999:
        return
    # Cooldown: avoid over-dosing before mixing finishes
    if time.time() - last_ph_dose_time < DOSE_MIXING_WAIT:
        return
    if ph > PH_MAX:
        print(">>> pH HIGH - dosing citric acid")
        push_syringe(PH_ACID_SERVO_PIN)
        last_ph_dose_time = time.time()
    elif ph < PH_MIN:
        print(">>> pH LOW - dosing potassium bicarbonate")
        push_syringe(PH_BASE_SERVO_PIN)
        last_ph_dose_time = time.time()

def conductivity_homeostasis():
    """Maintain EC between EC_MIN and EC_MAX."""
    global last_ec_dose_time
    ec = get_ec()
    print("EC level:", ec, "mS/cm")
    if ec == -999:
        return
    if time.time() - last_ec_dose_time < DOSE_MIXING_WAIT:
        return
    if ec < EC_MIN:
        print(">>> EC LOW - dosing nutrient")
        push_syringe(NUTRIENT_SERVO_PIN)
        last_ec_dose_time = time.time()
    elif ec > EC_MAX:
        print(">>> EC HIGH - adding fresh water")
        set_output(FRESH_WATER_PUMP_PIN, 1)
        time.sleep(5)
        set_output(FRESH_WATER_PUMP_PIN, 0)
        last_ec_dose_time = time.time()

def turbidity_check():
    """Set orange warning LED if water is too cloudy."""
    ntu = get_turbidity()
    if ntu == -999:
        return
    if ntu > TURBIDITY_MAX:
        set_output(ORANGE_LIGHT_PIN, 1)
        print(">>> Water cloudy:", ntu, "NTU")
    else:
        set_output(ORANGE_LIGHT_PIN, 0)

def temperature_protection():
    """Switch fan based on water temperature."""
    water_temp = get_water_temp()
    if water_temp == -999:
        return
    if water_temp > WATER_TEMP_MAX:
        set_output(FAN_PIN, 1)
        print(">>> Water hot (", water_temp, "°C) - fan ON")
    elif water_temp < WATER_TEMP_MIN:
        set_output(FAN_PIN, 0)

def adjust_watering_by_weather():
    """Adjust irrigation interval & target volume based on room conditions."""
    global IRRIGATION_INTERVAL, WATER_TARGET_PULSES
    air_temp, air_hum = read_sht31()
    if air_temp is None or air_hum is None:
        IRRIGATION_INTERVAL = 1800
        WATER_TARGET_PULSES = int(WATER_TARGET_NORMAL * PULSES_PER_LITER)
        return
    print("[Weather] Air:", air_temp, "°C,", air_hum, "%")
    if air_temp > 28 or air_hum < 40:
        IRRIGATION_INTERVAL = 900
        WATER_TARGET_PULSES = int(WATER_TARGET_HOT * PULSES_PER_LITER)
        print("[Weather] HOT/DRY -> 15 min, target", WATER_TARGET_HOT, "L")
    elif air_temp < 18 or air_hum > 75:
        IRRIGATION_INTERVAL = 2700
        WATER_TARGET_PULSES = int(WATER_TARGET_COLD * PULSES_PER_LITER)
        print("[Weather] COLD/HUMID -> 45 min, target", WATER_TARGET_COLD, "L")
    else:
        IRRIGATION_INTERVAL = 1800
        WATER_TARGET_PULSES = int(WATER_TARGET_NORMAL * PULSES_PER_LITER)
        print("[Weather] NORMAL -> 30 min, target", WATER_TARGET_NORMAL, "L")

def check_and_water():
    """Flow-based irrigation: pump until target liters delivered or safety triggers."""
    global last_water_time, is_watering, watering_start_time
    global flow_pulse_count, last_pulse_seen_time
    current_time = time.time()

    # Not watering -> check if it's time to start
    if not is_watering:
        adjust_watering_by_weather()
        if current_time - last_water_time >= IRRIGATION_INTERVAL:
            print("-> Starting pump. Target:", WATER_TARGET_PULSES, "pulses")
            flow_pulse_count = 0
            watering_start_time = current_time
            last_pulse_seen_time = current_time
            set_output(WATER_PUMP_PIN, 1)
            is_watering = True
        else:
            time_left = IRRIGATION_INTERVAL - (current_time - last_water_time)
            print("-> Next watering in", int(time_left / 60), "min")
        return

    # Watering -> check for completion or problems
    liters_so_far = flow_pulse_count / PULSES_PER_LITER
    elapsed = current_time - watering_start_time
    print("-> Watering:", flow_pulse_count, "pulses (", round(liters_so_far, 2),
          "L) in", int(elapsed), "s")

    # Target reached
    if flow_pulse_count >= WATER_TARGET_PULSES:
        print("-> Target reached. Stopping pump.")
        set_output(WATER_PUMP_PIN, 0)
        is_watering = False
        last_water_time = current_time
        return

    # No flow detected -> empty tank or pump failure
    if current_time - last_pulse_seen_time > NO_FLOW_TIMEOUT:
        print("!!! NO FLOW for", NO_FLOW_TIMEOUT, "s - stopping pump!")
        set_output(WATER_PUMP_PIN, 0)
        set_output(RED_LIGHT_PIN, 1)
        is_watering = False
        last_water_time = current_time
        return

    # Max runtime exceeded
    if elapsed > PUMP_TIMEOUT_SECONDS:
        print("!!! Pump timeout exceeded. Stopping.")
        set_output(WATER_PUMP_PIN, 0)
        is_watering = False
        last_water_time = current_time
        return

# =========================================================
# 10. STATE MACHINE: NORMAL <-> SAFE
# =========================================================

def normal_state():
    """Normal operation: run homeostasis loop until button pressed."""
    all_outputs_off()
    show_normal_state()
    print("=" * 40)
    print("NORMAL STATE — homeostasis active")
    print("=" * 40)

    while True:
        if is_button_pressed():
            wait_for_button_release()
            return safe_state

        check_and_water()
        ph_homeostasis()
        conductivity_homeostasis()
        turbidity_check()
        temperature_protection()

        time.sleep(2)

def safe_state():
    """Safe mode: all outputs off, red LED on, waiting for resume."""
    all_outputs_off()
    show_safe_state()
    print("=" * 40)
    print("SAFE STATE — system paused")
    print("Press the button again to resume.")
    print("=" * 40)

    while True:
        if is_button_pressed():
            wait_for_button_release()
            return normal_state
        time.sleep(0.1)

# =========================================================
# 11. MAIN ENTRY POINT
# =========================================================

def main():
    global last_water_time
    print("=" * 50)
    print("Chloroplasters Tower Garden — starting")
    print("=" * 50)
    all_outputs_off()
    last_water_time = time.time()

    current_state = normal_state
    while True:
        current_state = current_state()

main()
