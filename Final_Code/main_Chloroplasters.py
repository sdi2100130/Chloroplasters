# =========================================================
# Chloroplasters - Smart Tower Garden
# Main control program for SparkFun XRP (RP2350)
# =========================================================

from machine import Pin, PWM
import time
from sensors import read_all
from homeostasis import homeostasis, record_flow_pulse, reset_state, set_last_water_time

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
WATER_TEMP_PIN  = 16    # DS18B20 waterproof (4.7kΩ pull-up!)

# --- Servo actuators (PWM) ---
PH_ACID_SERVO_PIN  = 6  # Citric acid (pH down)
PH_BASE_SERVO_PIN  = 7  # Potassium bicarbonate (pH up)
NUTRIENT_SERVO_PIN = 8  # Nutrient straw lift/lower servo (EC up)
NUTRIENT_2_SERVO_PIN = 9  # Optional/unused second nutrient servo

# --- Relay outputs ---
WATER_PUMP_PIN       = 12  # Main irrigation pump
FRESH_WATER_PUMP_PIN = 18  # Fresh water dilution (optional)
FAN_PIN              = 19  # Cooling fan

# --- RGB status LED ---
RGB_GREEN_PIN = 21  # Green channel: normal operation
RGB_RED_PIN   = 22  # Red channel: safe mode / problem
RGB_BLUE_PIN  = 23  # Blue channel: no-flow warning

# Set to True if your RGB LED is common-anode instead of common-cathode.
RGB_COMMON_ANODE = False

# --- User input ---
STOP_BUTTON_PIN = 36   # Built-in USER button

# =========================================================
# 2. THRESHOLDS & CONSTANTS
# =========================================================

# pH limits
PH_MIN = 5.5  # TRIAL-AND-ERROR: adjust after testing ideal pH range for the plants.
PH_MAX = 6.5  # TRIAL-AND-ERROR: adjust after testing ideal pH range for the plants.

# EC limits (mS/cm)
EC_MIN = 1.0  # TRIAL-AND-ERROR: adjust after testing nutrient strength and sensor readings.
EC_MAX = 2.0  # TRIAL-AND-ERROR: adjust after testing nutrient strength and sensor readings.
FRESH_WATER_PUMP_ENABLED = False

# Water temperature
WATER_TEMP_MAX = 30   # TRIAL-AND-ERROR: fan ON temperature; tune for real reservoir behavior.
WATER_TEMP_MIN = 26   # TRIAL-AND-ERROR: fan OFF temperature; tune to avoid rapid on/off cycling.

# Turbidity (NTU)
TURBIDITY_MAX = 30  # TRIAL-AND-ERROR: adjust after comparing sensor values with visibly clean/cloudy water.

# --- Irrigation (flow-based) ---
PULSES_PER_LITER    = 450   # TRIAL-AND-ERROR: calibrate by measuring pulses for 1 real liter.
WATER_TARGET_HOT    = 2.5   # TRIAL-AND-ERROR: adjust liters delivered in hot/dry conditions.
WATER_TARGET_NORMAL = 2.0   # TRIAL-AND-ERROR: adjust normal watering volume after plant/system tests.
WATER_TARGET_COLD   = 1.5   # TRIAL-AND-ERROR: adjust liters delivered in cold/humid conditions.

IRRIGATION_INTERVAL  = 1800  # TRIAL-AND-ERROR: default watering gap; tune after observing moisture/root needs.
WATER_TARGET_PULSES  = int(WATER_TARGET_NORMAL * PULSES_PER_LITER)

# Safety timeouts
PUMP_TIMEOUT_SECONDS = 300  # TRIAL-AND-ERROR: max pump runtime; set safely above normal watering duration.
NO_FLOW_TIMEOUT      = 60   # TRIAL-AND-ERROR: no-flow alarm delay; tune for startup lag and sensor reliability.

# --- Dosing ---
SERVO_1ML_ANGLE   = 20      # TRIAL-AND-ERROR: acid/base syringe angle for one dose; calibrate with real mL output.
NUTRIENT_STRAW_REST_ANGLE = 0  # TRIAL-AND-ERROR: angle where nutrient straw is fully raised/resting.
NUTRIENT_STRAW_FEED_ANGLE = 90  # TRIAL-AND-ERROR: angle where nutrient straw feeds correctly.
NUTRIENT_STRAW_FEED_SECONDS = 5  # TRIAL-AND-ERROR: time straw stays in feed position.
DOSE_MIXING_WAIT  = 300     # TRIAL-AND-ERROR: wait time for acid/base/nutrients to mix before dosing again.
MAX_DOSES_PER_CYCLE = 4     # TRIAL-AND-ERROR: safety cap if readings do not converge after repeated dosing.

# =========================================================
# 3. HARDWARE INITIALIZATION
# =========================================================

# Flow sensor interrupt
def flow_pulse_handler(pin):
    record_flow_pulse()

flow_pin = Pin(FLOW_SENSOR_PIN, Pin.IN, Pin.PULL_UP)
flow_pin.irq(trigger=Pin.IRQ_RISING, handler=flow_pulse_handler)

# RGB status LED PWM channels
rgb_red_pwm = PWM(Pin(RGB_RED_PIN))
rgb_green_pwm = PWM(Pin(RGB_GREEN_PIN))
rgb_blue_pwm = PWM(Pin(RGB_BLUE_PIN))
rgb_red_pwm.freq(1000)
rgb_green_pwm.freq(1000)
rgb_blue_pwm.freq(1000)

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
    """Move an acid/base syringe servo to dose, then return to rest."""
    print("Dosing syringe on pin", servo_pin)
    set_servo_angle(servo_pin, SERVO_1ML_ANGLE)
    time.sleep(1)
    set_servo_angle(servo_pin, 0)

def feed_nutrients_with_straw(servo_pin):
    """Lower the nutrient straw to feed nutrients, then raise it back up."""
    print("Feeding nutrients with straw servo on pin", servo_pin)
    set_servo_angle(servo_pin, NUTRIENT_STRAW_FEED_ANGLE)
    time.sleep(NUTRIENT_STRAW_FEED_SECONDS)
    set_servo_angle(servo_pin, NUTRIENT_STRAW_REST_ANGLE)

def push_syringes_parallel(servo_pins):
    """Dispense from multiple syringes for the same amount of time."""
    print("Dosing syringes on pins", servo_pins)
    pwms = []
    try:
        for servo_pin in servo_pins:
            pwm = PWM(Pin(servo_pin))
            pwm.freq(50)
            pwms.append(pwm)

        min_duty = 1000
        max_duty = 9000
        dose_duty = min_duty + int((SERVO_1ML_ANGLE / 180) * (max_duty - min_duty))
        rest_duty = min_duty

        for pwm in pwms:
            pwm.duty_u16(dose_duty)
        time.sleep(1)
        for pwm in pwms:
            pwm.duty_u16(rest_duty)
        time.sleep(0.5)
    finally:
        for pwm in pwms:
            pwm.deinit()

def set_output(pin_num, state):
    """Set a digital output pin ON (1) or OFF (0)."""
    p = Pin(pin_num, Pin.OUT)
    p.value(state)

def set_rgb(red, green, blue):
    """Set RGB status LED using 0-255 values."""
    red = max(0, min(255, red))
    green = max(0, min(255, green))
    blue = max(0, min(255, blue))

    red_duty = int(red * 65535 / 255)
    green_duty = int(green * 65535 / 255)
    blue_duty = int(blue * 65535 / 255)

    if RGB_COMMON_ANODE:
        red_duty = 65535 - red_duty
        green_duty = 65535 - green_duty
        blue_duty = 65535 - blue_duty

    rgb_red_pwm.duty_u16(red_duty)
    rgb_green_pwm.duty_u16(green_duty)
    rgb_blue_pwm.duty_u16(blue_duty)

# =========================================================
# 8. SAFETY & STATE HELPERS
# =========================================================

def is_button_pressed():
    try:
        p = Pin(STOP_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        return p.value() == 0
    except Exception:
        return False

def wait_for_button_release():
    while is_button_pressed():
        time.sleep(0.05)

def all_outputs_off():
    """Force all pumps, fan, and watering state into a safe OFF condition."""
    set_output(WATER_PUMP_PIN, 0)
    set_output(FRESH_WATER_PUMP_PIN, 0)
    set_output(FAN_PIN, 0)
    set_rgb(0, 0, 0)
    reset_state()

def show_normal_state():
    set_rgb(0, 255, 0)

def show_safe_state():
    set_rgb(255, 0, 0)

def show_dirty_water_state():
    set_rgb(255, 120, 0)

def show_no_flow_state():
    set_rgb(0, 0, 255)

def homeostasis_controls():
    return {
        "set_output": set_output,
        "push_syringe": push_syringe,
        "feed_nutrients_with_straw": feed_nutrients_with_straw,
        "push_syringes_parallel": push_syringes_parallel,
        "show_normal_state": show_normal_state,
        "show_safe_state": show_safe_state,
        "show_dirty_water_state": show_dirty_water_state,
        "show_no_flow_state": show_no_flow_state,
        "safe_state": safe_state,
    }

def homeostasis_config():
    return {
        "PH_MIN": PH_MIN,
        "PH_MAX": PH_MAX,
        "EC_MIN": EC_MIN,
        "EC_MAX": EC_MAX,
        "FRESH_WATER_PUMP_ENABLED": FRESH_WATER_PUMP_ENABLED,
        "WATER_TEMP_MAX": WATER_TEMP_MAX,
        "WATER_TEMP_MIN": WATER_TEMP_MIN,
        "TURBIDITY_MAX": TURBIDITY_MAX,
        "PULSES_PER_LITER": PULSES_PER_LITER,
        "WATER_TARGET_HOT": WATER_TARGET_HOT,
        "WATER_TARGET_NORMAL": WATER_TARGET_NORMAL,
        "WATER_TARGET_COLD": WATER_TARGET_COLD,
        "PUMP_TIMEOUT_SECONDS": PUMP_TIMEOUT_SECONDS,
        "NO_FLOW_TIMEOUT": NO_FLOW_TIMEOUT,
        "DOSE_MIXING_WAIT": DOSE_MIXING_WAIT,
        "PH_ACID_SERVO_PIN": PH_ACID_SERVO_PIN,
        "PH_BASE_SERVO_PIN": PH_BASE_SERVO_PIN,
        "NUTRIENT_SERVO_PIN": NUTRIENT_SERVO_PIN,
        "NUTRIENT_2_SERVO_PIN": NUTRIENT_2_SERVO_PIN,
        "NUTRIENT_STRAW_REST_ANGLE": NUTRIENT_STRAW_REST_ANGLE,
        "NUTRIENT_STRAW_FEED_ANGLE": NUTRIENT_STRAW_FEED_ANGLE,
        "NUTRIENT_STRAW_FEED_SECONDS": NUTRIENT_STRAW_FEED_SECONDS,
        "WATER_PUMP_PIN": WATER_PUMP_PIN,
        "FRESH_WATER_PUMP_PIN": FRESH_WATER_PUMP_PIN,
        "FAN_PIN": FAN_PIN,
    }

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

        next_state = homeostasis(
            read_all(),
            homeostasis_controls(),
            homeostasis_config(),
        )
        if next_state is not None:
            return next_state

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
    print("=" * 50)
    print("Chloroplasters Tower Garden — starting")
    print("=" * 50)
    all_outputs_off()
    set_last_water_time(time.time())

    try:
        current_state = normal_state
        while True:
            current_state = current_state()
    finally:
        print("Stopping system - turning outputs off.")
        all_outputs_off()

main()
