from machine import I2C, Pin
import time


# Qwiic / ADS1015 setup
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
ADS1015_ADDR = 0x48
PH_CHANNEL = 0   # ADS1015 A0 -> analog output from pH interface board

# ADS1015 settings
ADS1015_REG_CONVERSION = 0x00
ADS1015_REG_CONFIG = 0x01
ADS1015_CONFIG_BASE = 0x8583
ADS1015_MUX = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}

# Generic BNC pH interface calibration.
# Put the probe in pH 7.00 buffer and adjust NEUTRAL_VOLTAGE until pH reads 7.00.
# Then use pH 4.00 or pH 10.00 buffer to adjust VOLTS_PER_PH if needed.
NEUTRAL_PH = 7.0
NEUTRAL_VOLTAGE = 2.03
VOLTS_PER_PH = 0.18

# Reading settings
SAMPLES = 20
SAMPLE_DELAY = 0.02
INTERVAL = 1.0


i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)


def read_ads1015_channel(channel):
    """Read one ADS1015 channel and return voltage."""
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


def read_average_voltage():
    """Take several ADS1015 readings and return the average voltage."""
    total = 0
    for _ in range(SAMPLES):
        total += read_ads1015_channel(PH_CHANNEL)
        time.sleep(SAMPLE_DELAY)
    return total / SAMPLES


def voltage_to_ph(voltage):
    """Convert voltage to pH using a generic linear calibration."""
    return NEUTRAL_PH + ((NEUTRAL_VOLTAGE - voltage) / VOLTS_PER_PH)


print("=" * 50)
print("PH SENSOR TEST - GENERIC BNC PROBE")
print("=" * 50)
print("Qwiic ADS1015 address: 0x" + "{:02X}".format(ADS1015_ADDR))
print("Sensor analog output connected to ADS1015 A" + str(PH_CHANNEL))
print()
print("INSTRUCTIONS:")
print("- Connect ADS1015 to the XRP Qwiic port")
print("- Connect probe board VCC to 3.3V or 5V as required by its board")
print("- Connect probe board GND to ADS1015/XRP GND")
print("- Connect probe board analog output to ADS1015 A" + str(PH_CHANNEL))
print("- Rinse probe with clean water before each test")
print("- For best accuracy, calibrate with pH 7.00 and pH 4.00/10.00 buffers")
print()
print("Press CTRL+C to stop")
print("=" * 50)
print()


while True:
    voltage = read_average_voltage()
    ph = voltage_to_ph(voltage)

    print("Voltage: " + "{:.3f}".format(voltage) + " V" +
          " | pH: " + "{:.2f}".format(ph))

    time.sleep(INTERVAL)
