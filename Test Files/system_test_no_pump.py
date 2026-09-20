from machine import Pin, I2C, PWM
import time
import onewire
import ds18x20


# =========================================================
# Chloroplasters hardware test - NO PUMP OUTPUTS USED
# =========================================================
# This file does not touch WATER_PUMP_PIN or FRESH_WATER_PUMP_PIN.
# Run it on the XRP/MicroPython board to test wiring safely.


# I2C bus
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
ADS1015_ADDR = 0x48
SHT31_ADDR = 0x44

# ADS1015 channels
PH_CHANNEL = 0
EC_CHANNEL = 1
TURBIDITY_CHANNEL = 2

# Digital sensors
FLOW_SENSOR_PIN = 2
WATER_TEMP_TEST_PINS = (20, 16)

# RGB status LED
RGB_GREEN_PIN = 21
RGB_RED_PIN = 22
RGB_BLUE_PIN = 23
RGB_COMMON_ANODE = False

# Stop button candidates. Different firmware versions can expose the button
# differently, so the test tries each option without crashing.
STOP_BUTTON_TEST_PINS = (3,)

# Optional actuator tests. Leave False unless you are ready to test them.
TEST_FAN = True
TEST_SERVOS = False
FAN_PIN = 19
PH_ACID_SERVO_PIN = 6
PH_BASE_SERVO_PIN = 7
NUTRIENT_SERVO_PIN = 8


flow_pulse_count = 0


def heading(title):
    print()
    print("=" * 50)
    print(title)
    print("=" * 50)


def set_output(pin_num, state):
    p = Pin(pin_num, Pin.OUT)
    p.value(state)


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


def test_rgb():
    heading("RGB LED TEST")
    colors = (
        ("RED", 255, 0, 0),
        ("GREEN", 0, 255, 0),
        ("BLUE", 0, 0, 255),
        ("ORANGE", 255, 120, 0),
        ("OFF", 0, 0, 0),
    )
    for name, red, green, blue in colors:
        print("RGB:", name)
        set_rgb(red, green, blue)
        time.sleep(1)


def test_i2c():
    heading("I2C SCAN")
    try:
        i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)
        devices = i2c.scan()
        print("I2C devices found:", [hex(device) for device in devices])
        if ADS1015_ADDR in devices:
            print("ADS1015 found at 0x48")
        else:
            print("ADS1015 NOT found at 0x48")
        if SHT31_ADDR in devices:
            print("SHT31 found at 0x44")
        else:
            print("SHT31 NOT found at 0x44")
        return i2c
    except Exception as e:
        print("I2C test failed:", e)
        return None


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
    except Exception as e:
        print("ADS1015 channel", channel, "failed:", e)
        return None


def test_ads1015(i2c):
    heading("ADS1015 ANALOG SENSOR TEST")
    channels = (
        ("pH", PH_CHANNEL),
        ("EC/TDS", EC_CHANNEL),
        ("Turbidity", TURBIDITY_CHANNEL),
    )
    for name, channel in channels:
        voltage = ads1015_read_channel(i2c, channel)
        if voltage is None:
            print(name, "channel", channel, "read failed")
        else:
            print(name, "channel", channel, "voltage:", round(voltage, 3), "V")


def test_sht31(i2c):
    heading("SHT31 AIR TEMP/HUMIDITY TEST")
    if i2c is None:
        print("Skipped because I2C failed")
        return
    try:
        i2c.writeto(SHT31_ADDR, b'\x24\x00')
        time.sleep(0.02)
        data = i2c.readfrom(SHT31_ADDR, 6)
        temp_raw = (data[0] << 8) | data[1]
        hum_raw = (data[3] << 8) | data[4]
        temperature = -45 + (175 * temp_raw / 65535)
        humidity = 100 * hum_raw / 65535
        print("Air temperature:", round(temperature, 2), "C")
        print("Air humidity:", round(humidity, 2), "%")
    except Exception as e:
        print("SHT31 read failed:", e)


def test_water_temp():
    heading("DS18B20 WATER TEMP TEST")
    for pin_num in WATER_TEMP_TEST_PINS:
        print("Trying DS18B20 on IO" + str(pin_num))
        try:
            pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)
            ds = ds18x20.DS18X20(onewire.OneWire(pin))
            sensors = ds.scan()
            print("Sensors found on IO" + str(pin_num) + ":", sensors)
            if sensors:
                ds.convert_temp()
                time.sleep(1)
                for index, sensor in enumerate(sensors):
                    temp = ds.read_temp(sensor)
                    print("IO" + str(pin_num), "sensor", index + 1, "temperature:", round(temp, 2), "C")
                return pin_num
        except Exception as e:
            print("IO" + str(pin_num), "failed:", e)
    print("No DS18B20 found on IO20 or IO16")
    print("Check DATA wire, GND, 3.3V, and 4.7k pull-up resistor.")
    return None


def flow_pulse_handler(pin):
    global flow_pulse_count
    flow_pulse_count += 1


def test_flow_sensor():
    heading("FLOW SENSOR PASSIVE TEST")
    global flow_pulse_count
    flow_pulse_count = 0
    flow_pin = Pin(FLOW_SENSOR_PIN, Pin.IN, Pin.PULL_UP)
    flow_pin.irq(trigger=Pin.IRQ_RISING, handler=flow_pulse_handler)
    print("Counting pulses on IO" + str(FLOW_SENSOR_PIN) + " for 10 seconds.")
    print("Move water through the sensor now if you can. Pump is NOT used.")
    for remaining in range(10, 0, -1):
        print("Seconds left:", remaining, "pulses:", flow_pulse_count)
        time.sleep(1)
    flow_pin.irq(handler=None)
    print("Final flow pulse count:", flow_pulse_count)
    if flow_pulse_count == 0:
        print("No pulses detected. Check sensor power, signal wire, and flow direction.")
    else:
        print("Flow sensor produced pulses.")


def is_button_pressed(button):
    try:
        return button.value() == 0
    except Exception:
        return False


def test_stop_button(excluded_pin=None):
    heading("STOP BUTTON TEST")
    button = None
    working_pin = None

    if isinstance(STOP_BUTTON_TEST_PINS, tuple) or isinstance(STOP_BUTTON_TEST_PINS, list):
        button_candidates = STOP_BUTTON_TEST_PINS
    else:
        button_candidates = (STOP_BUTTON_TEST_PINS,)

    for pin_name in button_candidates:
        if pin_name == excluded_pin:
            print("Skipping stop button pin", pin_name, "because DS18B20 is using it.")
            continue
        try:
            button = Pin(pin_name, Pin.IN, Pin.PULL_UP)
            working_pin = pin_name
            print("Using stop button pin:", pin_name)
            break
        except Exception as e:
            print("Stop button pin", pin_name, "not usable:", e)

    if button is None:
        print("No valid stop button pin found. Skipping stop button test.")
        return None

    print("Reading stop button for 5 seconds. Press it now.")
    for remaining in range(5, 0, -1):
        if is_button_pressed(button):
            print("Button is PRESSED")
        else:
            print("Button is released")
        time.sleep(1)

    return working_pin


def set_servo_angle(pin_num, angle):
    pwm = PWM(Pin(pin_num))
    pwm.freq(50)
    min_duty = 1000
    max_duty = 9000
    duty = min_duty + int((angle / 180) * (max_duty - min_duty))
    pwm.duty_u16(duty)
    time.sleep(0.5)
    pwm.deinit()


def test_optional_outputs():
    if TEST_FAN:
        heading("OPTIONAL FAN TEST")
        print("Fan ON for 2 seconds")
        set_output(FAN_PIN, 1)
        time.sleep(2)
        print("Fan OFF")
        set_output(FAN_PIN, 0)

    if TEST_SERVOS:
        heading("OPTIONAL SERVO TEST")
        for servo_pin in (PH_ACID_SERVO_PIN, PH_BASE_SERVO_PIN, NUTRIENT_SERVO_PIN):
            print("Testing servo on IO" + str(servo_pin))
            set_servo_angle(servo_pin, 20)
            time.sleep(1)
            set_servo_angle(servo_pin, 0)


def cleanup_outputs():
    set_rgb(0, 0, 0)
    if TEST_FAN:
        try:
            set_output(FAN_PIN, 0)
        except Exception:
            pass


def main():
    heading("CHLOROPLASTERS SYSTEM TEST - NO PUMP")
    print("This test does not activate the main pump or fresh water pump.")

    try:
        set_rgb(0, 0, 0)

        test_rgb()
        i2c = test_i2c()
        test_ads1015(i2c)
        test_sht31(i2c)
        found_temp_pin = test_water_temp()
        test_flow_sensor()
        found_stop_button_pin = test_stop_button(excluded_pin=found_temp_pin)
        test_optional_outputs()

        heading("TEST COMPLETE")
        if found_temp_pin is not None:
            print("Use WATER_TEMP_PIN =", found_temp_pin, "in main_Chloroplasters.py")
        if found_stop_button_pin is not None:
            print("Use STOP_BUTTON_PIN =", repr(found_stop_button_pin), "in main_Chloroplasters.py")
        elif found_temp_pin is not None:
            print("No separate stop button pin found. Do not use IO" + str(found_temp_pin) + " for the stop button.")
        print("Pump outputs were not used.")
    finally:
        print("Test stopped - turning LED off.")
        cleanup_outputs()


main()
