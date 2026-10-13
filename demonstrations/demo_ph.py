"""pH sensor demonstration with acid/base syringe movements; use water."""

from machine import Pin, I2C, PWM
import time

# Uses the sensor, ADC bus and acid/base servos. Pump pins are never used.
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
ADS1015_ADDR = 0x48
ADS1015_CONFIG_BASE = 0x8383  # Single shot, +/-4.096 V, 1600 SPS.
FULL_SCALE_VOLTS = 4.096
SAMPLES = 10
INTERVAL_MS = 1000


def decode_voltage(data):
    raw = ((data[0] << 8) | data[1]) >> 4
    if raw & 0x800:
        raw -= 4096
    return raw * FULL_SCALE_VOLTS / 2048


def read_voltage(i2c):
    total = 0.0
    config = ADS1015_CONFIG_BASE | ((4 + CHANNEL) << 12)
    for _ in range(SAMPLES):
        i2c.writeto(ADS1015_ADDR, bytes([1, config >> 8, config & 255]))
        time.sleep_ms(5)
        i2c.writeto(ADS1015_ADDR, b'\x00')
        data = i2c.readfrom(ADS1015_ADDR, 2)
        if len(data) != 2:
            raise ValueError("Incomplete ADC reading")
        if ((data[0] << 8) | data[1]) >> 4 == 2047:
            raise ValueError("ADC saturated; check input voltage and wiring")
        total += decode_voltage(data)
    voltage = total / SAMPLES
    if voltage < 0:
        raise ValueError("Negative single-ended voltage; check signal and ground")
    return voltage


def wait_for_next(start):
    remaining = INTERVAL_MS - time.ticks_diff(time.ticks_ms(), start)
    if remaining > 0:
        time.sleep_ms(remaining)


CHANNEL = 0
NEUTRAL_PH = 7.0
NEUTRAL_VOLTAGE = 1.1  # Placeholder from the pH test; measure with buffer.
VOLTS_PER_PH = 0.12   # Signed slope; measure using two known buffers.
PH_MIN = 5.5
PH_MAX = 6.5
ACID_SERVO_PIN = 9  # Matches demo_acid_servo.py.
BASE_SERVO_PIN = 8  # Matches demo_base_servo.py.
SERVO_REST_ANGLE = 0
SERVO_MAX_ANGLE = 45
MIN_PULSE_US = 500
MAX_PULSE_US = 2500
HOLD_SECONDS = 1.8
RETURN_SECONDS = 1.0


def validate_settings():
    if not 0 <= PH_MIN < PH_MAX <= 14:
        raise ValueError("pH thresholds must satisfy 0 <= minimum < maximum <= 14")
    if not 0 <= SERVO_REST_ANGLE < SERVO_MAX_ANGLE <= 180:
        raise ValueError("Angles must satisfy 0 <= rest < maximum <= 180")
    if not 0 < MIN_PULSE_US < MAX_PULSE_US < 20000:
        raise ValueError("Invalid servo pulse limits")
    if HOLD_SECONDS <= 0 or RETURN_SECONDS <= 0:
        raise ValueError("Invalid movement timing")
    if VOLTS_PER_PH == 0:
        raise ValueError("VOLTS_PER_PH must be nonzero")


def angle_to_duty(angle):
    if not SERVO_REST_ANGLE <= angle <= SERVO_MAX_ANGLE:
        raise ValueError("Angle outside configured movement limits")
    pulse_us = MIN_PULSE_US + int(angle / 180 * (MAX_PULSE_US - MIN_PULSE_US))
    return int(pulse_us * 65535 / 20000)


def move_servo(pin_number):
    pwm = None
    try:
        for seconds in (3, 2, 1):
            print("Syringe IO{} moves in {}".format(pin_number, seconds))
            time.sleep(1)
        pwm = PWM(Pin(pin_number, Pin.OUT, value=0), freq=50, duty_u16=0)
        pwm.duty_u16(angle_to_duty(SERVO_REST_ANGLE))
        time.sleep(RETURN_SECONDS)
        pwm.duty_u16(angle_to_duty(SERVO_MAX_ANGLE))
        time.sleep(HOLD_SECONDS)
    finally:
        if pwm is not None:
            try:
                pwm.duty_u16(angle_to_duty(SERVO_REST_ANGLE))
                time.sleep(RETURN_SECONDS)
            finally:
                try:
                    pwm.deinit()
                finally:
                    Pin(pin_number, Pin.OUT, value=0)


def voltage_to_ph(voltage):
    if VOLTS_PER_PH == 0:
        raise ValueError("VOLTS_PER_PH must be nonzero")
    return NEUTRAL_PH + (voltage - NEUTRAL_VOLTAGE) / VOLTS_PER_PH


def main():
    print("PH SENSOR DEMO | Pump disconnected")
    print("Rinse the probe between samples; wait for each reading to stabilize.")
    print("Use empty syringes or water; pH calibration is a placeholder.")
    print("pH > {}: acid IO{} | pH < {}: base IO{}".format(
        PH_MAX, ACID_SERVO_PIN, PH_MIN, BASE_SERVO_PIN))
    print("One movement per excursion; return pH to range to rearm. Ctrl+C stops.")
    armed = True
    try:
        validate_settings()
        i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)
        if ADS1015_ADDR not in i2c.scan():
            print("ERROR: ADS1015 missing at 0x48; check Qwiic wiring and power.")
            return
        while True:
            start = time.ticks_ms()
            try:
                voltage = read_voltage(i2c)
                estimate = voltage_to_ph(voltage)
                if not 0 <= estimate <= 14:
                    raise ValueError("pH estimate outside 0-14; check calibration and wiring")
                print("Voltage: {:.3f} V | pH: {:.2f} | UNCALIBRATED ESTIMATE".format(
                    voltage, estimate))
            except Exception as exc:
                print("READ ERROR:", exc, "| no measurement available")
            else:
                if PH_MIN <= estimate <= PH_MAX:
                    armed = True
                    print("pH in range | Servos at rest; armed.")
                elif armed:
                    if estimate > PH_MAX:
                        print("pH HIGH | Moving ACID syringe to lower pH.")
                        move_servo(ACID_SERVO_PIN)
                    else:
                        print("pH LOW | Moving BASE syringe to raise pH.")
                        move_servo(BASE_SERVO_PIN)
                    armed = False
                    print("Movement complete | Return pH to range to rearm.")
                else:
                    print("Waiting for pH to return to range; no repeat movement.")
            wait_for_next(start)
    except KeyboardInterrupt:
        print("Demo stopped.")
    except Exception as exc:
        print("DEMO ERROR:", exc)


if __name__ == "__main__":
    main()
