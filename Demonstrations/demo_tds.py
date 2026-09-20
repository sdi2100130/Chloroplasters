"""Independent tds sensor video demonstration."""

from machine import Pin, I2C
import time

# Only this sensor and its ADC bus are initialized. Pump pins are never used.
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


CHANNEL = 1
WATER_TEMPERATURE_C = 25.0  # Assumed temperature, not another sensor reading.
CALIBRATION_FACTOR = 1.0   # Placeholder; adjust using a known TDS standard.


def voltage_to_tds(voltage):
    compensation = 1.0 + 0.02 * (WATER_TEMPERATURE_C - 25.0)
    if compensation <= 0 or CALIBRATION_FACTOR <= 0:
        raise ValueError("Invalid temperature or calibration factor")
    v = voltage / compensation
    return max(0.0, (133.42 * v ** 3 - 255.86 * v ** 2 + 857.39 * v)
               * 0.5 * CALIBRATION_FACTOR)


def main():
    print("TDS SENSOR DEMO | Pump disconnected")
    print("Compare separate water samples; rinse the probe between them.")
    print("Only this sensor is read. Press Ctrl+C to stop.")
    baseline = None
    try:
        i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)
        if ADS1015_ADDR not in i2c.scan():
            print("ERROR: ADS1015 missing at 0x48; check Qwiic wiring and power.")
            return
        while True:
            start = time.ticks_ms()
            try:
                voltage = read_voltage(i2c)
                estimate = voltage_to_tds(voltage)
                print("Voltage: {:.3f} V | TDS: {:.0f} ppm | assumed {:.1f} C | UNCALIBRATED ESTIMATE".format(
                    voltage, estimate, WATER_TEMPERATURE_C))
            except Exception as exc:
                print("READ ERROR:", exc, "| no measurement available")
            wait_for_next(start)
    except KeyboardInterrupt:
        print("Demo stopped.")
    except Exception as exc:
        print("DEMO ERROR:", exc)


if __name__ == "__main__":
    main()

