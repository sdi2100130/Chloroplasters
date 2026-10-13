from machine import Pin, I2C, PWM
import time
import onewire
import ds18x20
import sys
import select

# =========================================================
# Chloroplasters Hardware Test - Interactive Diagnostic CLI
# =========================================================

# --- Pin Configuration ---
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
ADS1015_ADDR = 0x48
SHT31_ADDR = 0x44

PH_CHANNEL = 0
EC_CHANNEL = 1
TURBIDITY_CHANNEL = 2

FLOW_SENSOR_PIN = 2
WATER_TEMP_TEST_PINS = (20, 16)

RGB_GREEN_PIN = 21
RGB_RED_PIN = 22
RGB_BLUE_PIN = 23
RGB_COMMON_ANODE = False

STOP_BUTTON_TEST_PINS = (3,)

FAN_PIN = 19
RED_SOLUTION= 6
CLEAR_SOLUTION = 7
POTASSIUM = 8
ACID =9


flow_pulse_count = 0

# --- Helper Utilities ---
def heading(title):
    print("\n" + "=" * 50)
    print(title)
    print("=" * 50)

def ask(prompt_text, default=""):
    try:
        val = input(prompt_text).strip()
        return val if val else default
    except (KeyboardInterrupt, EOFError):
        return "q"

# --- RGB Setup & Functions ---
def setup_rgb():
    red_pwm = PWM(Pin(RGB_RED_PIN))
    green_pwm = PWM(Pin(RGB_GREEN_PIN))
    blue_pwm = PWM(Pin(RGB_BLUE_PIN))
    red_pwm.freq(1000)
    green_pwm.freq(1000)
    blue_pwm.freq(1000)
    return red_pwm, green_pwm, blue_pwm

rgb_red_pwm, rgb_green_pwm, rgb_blue_pwm = setup_rgb()

def set_rgb(red, green, blue):
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

def interactive_rgb():
    heading("INTERACTIVE RGB LED TEST")
    preset_colors = {
        "1": ("RED", 255, 0, 0),
        "2": ("GREEN", 0, 255, 0),
        "3": ("BLUE", 0, 0, 255),
        "4": ("ORANGE", 255, 120, 0),
        "5": ("WHITE", 255, 255, 255),
        "0": ("OFF", 0, 0, 0),
    }

    while True:
        print("\nLED Options:")
        for k in sorted(preset_colors.keys()):
            print(f" [{k}] {preset_colors[k][0]}")
        print(" [c] Set Custom RGB (0-255)")
        print(" [b] Back to Main Menu")

        choice = ask("Select option: ").lower()
        if choice in preset_colors:
            name, r, g, b = preset_colors[choice]
            print(f"Setting LED to {name}...")
            set_rgb(r, g, b)
        elif choice == "c":
            try:
                r = int(ask("Red (0-255): ", "0"))
                g = int(ask("Green (0-255): ", "0"))
                b = int(ask("Blue (0-255): ", "0"))
                set_rgb(r, g, b)
                print(f"Applied custom RGB: ({r}, {g}, {b})")
            except ValueError:
                print("Invalid numerical values.")
        elif choice in ("b", "q"):
            break
        else:
            print("Unknown selection.")

# --- I2C & Environmental Sensors ---
def get_i2c():
    try:
        return I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)
    except Exception as e:
        print("I2C initialization failed:", e)
        return None

def interactive_i2c_scan(i2c):
    heading("I2C BUS SCAN")
    if i2c is None:
        print("I2C bus not available.")
        return
    devices = i2c.scan()
    print("Devices found:", [hex(d) for d in devices])
    print("ADS1015 (0x48):", "FOUND" if ADS1015_ADDR in devices else "MISSING")
    print("SHT31   (0x44):", "FOUND" if SHT31_ADDR in devices else "MISSING")
    time.sleep(1.5)

ADS1015_REG_CONVERSION = 0x00
ADS1015_REG_CONFIG = 0x01
ADS1015_CONFIG_BASE = 0x8583
ADS1015_MUX = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}

def ads1015_read_channel(i2c, channel):
    if i2c is None or channel not in ADS1015_MUX:
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
    except Exception:
        return None

def interactive_ads1015(i2c):
    heading("ADS1015 ANALOG SENSORS")
    if i2c is None:
        print("I2C bus not available.")
        return

    channels = (("pH", PH_CHANNEL), ("EC/TDS", EC_CHANNEL), ("Turbidity", TURBIDITY_CHANNEL))
    print("Streaming analog readings live (updating every second).")
    print("Press Ctrl+C to return to the main menu.\n")

    try:
        while True:
            readings = []
            for name, ch in channels:
                v = ads1015_read_channel(i2c, ch)
                v_str = f"{round(v, 3):.3f} V" if v is not None else "ERR"
                readings.append(f"{name}: {v_str}")
            
            print(" | ".join(readings))
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

    print("\nExited Analog Sensors test.")

def interactive_sht31(i2c):
    heading("SHT31 AIR SENSOR")
    if i2c is None:
        print("I2C bus not available.")
        return

    print("Streaming air temp and humidity live.")
    print("Press Ctrl+C to return to the main menu.\n")

    try:
        while True:
            try:
                i2c.writeto(SHT31_ADDR, b'\x24\x00')
                time.sleep(0.02)
                data = i2c.readfrom(SHT31_ADDR, 6)
                temp = -45 + (175 * ((data[0] << 8) | data[1]) / 65535)
                hum = 100 * ((data[3] << 8) | data[4]) / 65535
                print(f"Air Temp: {round(temp, 2)} C | Air Humidity: {round(hum, 2)} %")
            except Exception as e:
                print("SHT31 read failed:", e)
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

    print("\nExited Air Sensor test.")
    
# --- Water Temp (DS18B20) ---
def interactive_water_temp():
    heading("DS18B20 WATER TEMPERATURE")
    pin_num = 16  # Fixed to verified working pin IO16
    print(f"Connecting to DS18B20 on IO{pin_num}...")

    try:
        pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)
        ds = ds18x20.DS18X20(onewire.OneWire(pin))
        sensors = ds.scan()
        if not sensors:
            print(f"No DS18B20 found on IO{pin_num}. Verify 4.7k pull-up resistor.")
            return

        print(f"Found {len(sensors)} sensor(s). Live reading every second.")
        print("Press Ctrl+C to return to the main menu.\n")

        while True:
            ds.convert_temp()
            time.sleep(0.75)
            for i, s in enumerate(sensors):
                temp = ds.read_temp(s)
                print(f" Sensor {i+1}: {round(temp, 2)} C")
            time.sleep(0.5)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"DS18B20 error on IO{pin_num}:", e)

    print("\nExited Water Temp test.")

# --- Flow Sensor ---
def flow_pulse_handler(pin):
    global flow_pulse_count
    flow_pulse_count += 1

def interactive_flow_sensor():
    heading("FLOW SENSOR TEST")
    global flow_pulse_count
    flow_pulse_count = 0
    flow_pin = Pin(FLOW_SENSOR_PIN, Pin.IN, Pin.PULL_UP)
    flow_pin.irq(trigger=Pin.IRQ_RISING, handler=flow_pulse_handler)

    print(f"Monitoring IO{FLOW_SENSOR_PIN}. Blow or push liquid through the sensor.")
    print("Live pulse counts will print automatically.")
    print("Press Ctrl+C to return to the main menu.\n")

    last_count = -1
    try:
        while True:
            if flow_pulse_count != last_count:
                print(f"Total pulses registered: {flow_pulse_count}")
                last_count = flow_pulse_count
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        flow_pin.irq(handler=None)

    print(f"\nExited Flow Sensor test. Final pulses: {flow_pulse_count}")
    
# --- Stop Button ---
def interactive_stop_button():
    heading("STOP BUTTON TEST")
    btn_pin = STOP_BUTTON_TEST_PINS[0]
    try:
        button = Pin(btn_pin, Pin.IN, Pin.PULL_UP)
    except Exception as e:
        print("Pin setup error:", e)
        return

    print("Live monitoring IO" + str(btn_pin) + " (Inverted: 1=PRESSED, 0=RELEASED).")
    print("Press the button to test.")
    print("Press Ctrl+C to return to the main menu.\n")

    last_state = -1
    try:
        while True:
            cur_state = button.value()
            if cur_state != last_state:
                # Inverted logic: 1 -> Pressed, 0 -> Released
                if cur_state == 1:
                    print("  [HARDWARE EVENT] Button: PRESSED  (High / 1)")
                else:
                    print("  [HARDWARE EVENT] Button: RELEASED (Low / 0)")
                last_state = cur_state

            time.sleep(0.05)
    except KeyboardInterrupt:
        pass

    print("\nExited Stop Button test.")
    
# --- Fan and Actuator Tests ---
def set_output(pin_num, state):
    p = Pin(pin_num, Pin.OUT)
    p.value(state)

def interactive_fan():
    heading("FAN CONTROL TEST")
    while True:
        print("\nFan Options:")
        print(" [1] Turn Fan ON")
        print(" [0] Turn Fan OFF")
        print(" [b] Back to Main Menu")
        choice = ask("Select: ").lower()
        if choice == "1":
            set_output(FAN_PIN, 1)
            print(f"Fan IO{FAN_PIN} turned ON.")
        elif choice == "0":
            set_output(FAN_PIN, 0)
            print(f"Fan IO{FAN_PIN} turned OFF.")
        elif choice in ("b", "q"):
            set_output(FAN_PIN, 0)
            print("Fan ensured OFF.")
            break

def angle_to_duty(angle):
    """Accurate 50Hz 16-bit duty cycle for 0.5ms (0 deg) to 2.5ms (180 deg)."""
    angle = max(0, min(180, angle))
    min_pulse_us = 500
    max_pulse_us = 2500
    pulse_us = min_pulse_us + int((angle / 180) * (max_pulse_us - min_pulse_us))
    return int(pulse_us * 65535 / 20000)

def set_servo_angle(pin_num, angle):
    pwm = PWM(Pin(pin_num))
    pwm.freq(50)
    duty = angle_to_duty(angle)
    pwm.duty_u16(duty)
    time.sleep(0.8)  # Allow time for physical mechanical transit
    pwm.deinit()

def interactive_servos():
    heading("SERVO TEST")
    servos = {
        "1": ("red solution servo", RED_SOLUTION),
        "2": ("clear solution servo", CLEAR_SOLUTION),
        "3": ("potassium servo", POTASSIUM),
        "4": ("acid servo", ACID),
    }
    while True:
        print("\nSelect Servo to control:")
        for k in sorted(servos.keys()):
            print(f" [{k}] {servos[k][0]} (IO{servos[k][1]})")
        print(" [b] Back to Main Menu")

        choice = ask("Select servo: ").lower()
        if choice in servos:
            label, pin = servos[choice]
            angle_str = ask(f"Target angle for {label} (0-180): ")
            if angle_str.lower() in ("b", "q"):
                continue
            try:
                angle = int(angle_str)
                angle = max(0, min(180, angle))
                print(f"Moving {label} on IO{pin} to {angle} degrees...")
                set_servo_angle(pin, angle)
            except ValueError:
                print("Invalid numerical angle.")
        elif choice in ("b", "q"):
            break

# --- Main Master Loop ---
def main():
    i2c = get_i2c()

    while True:
        heading("CHLOROPLASTERS DIAGNOSTIC SUITE")
        print(" [1] RGB LED Diagnostic (Color Control)")
        print(" [2] I2C Bus Scan")
        print(" [3] ADS1015 Analog Sensors (pH, EC, Turbidity)")
        print(" [4] SHT31 Air Temp & Humidity")
        print(" [5] DS18B20 Water Temperature")
        print(" [6] Flow Sensor Pulse Monitor")
        print(" [7] Stop Button Test")
        print(" [8] Fan Output Control")
        print(" [9] Syringe Servos Control")
        print(" [q] Quit and turn off outputs")

        choice = ask("\nSelect test to run: ").lower()

        if choice == "1":
            interactive_rgb()
        elif choice == "2":
            interactive_i2c_scan(i2c)
        elif choice == "3":
            interactive_ads1015(i2c)
        elif choice == "4":
            interactive_sht31(i2c)
        elif choice == "5":
            interactive_water_temp()
        elif choice == "6":
            interactive_flow_sensor()
        elif choice == "7":
            interactive_stop_button()
        elif choice == "8":
            interactive_fan()
        elif choice == "9":
            interactive_servos()
        elif choice == "q":
            print("\nShutting down diagnostics.")
            set_rgb(0, 0, 0)
            set_output(FAN_PIN, 0)
            break
        else:
            print("Invalid menu choice.")

main()