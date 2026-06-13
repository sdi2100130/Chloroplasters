from machine import I2C, Pin
import time


# Qwiic / ADS1015 setup
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
ADS1015_ADDR = 0x48
TURBIDITY_CHANNEL = 2   # ADS1015 A2 -> analog output from SEN0189

# ADS1015 settings
ADS1015_REG_CONVERSION = 0x00
ADS1015_REG_CONFIG = 0x01
ADS1015_CONFIG_BASE = 0x8583
ADS1015_MUX = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}

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
        total += read_ads1015_channel(TURBIDITY_CHANNEL)
        time.sleep(SAMPLE_DELAY)
    return total / SAMPLES


def voltage_to_ntu(voltage):
    """Estimate turbidity in NTU using the SEN0189 example curve."""
    if voltage < 0.1:
        return 3000.0

    ntu = -1120.4 * voltage * voltage + 5742.3 * voltage - 4352.9

    if ntu < 0:
        return 0.0
    if ntu > 3000:
        return 3000.0
    return ntu


print("=" * 50)
print("TURBIDITY SENSOR TEST - DFRobot Gravity SEN0189")
print("=" * 50)
print("Qwiic ADS1015 address: 0x" + "{:02X}".format(ADS1015_ADDR))
print("Sensor analog output connected to ADS1015 A" + str(TURBIDITY_CHANNEL))
print()
print("INSTRUCTIONS:")
print("- Connect ADS1015 to the XRP Qwiic port")
print("- Connect sensor VCC to 3.3V or 5V as required by its board")
print("- Connect sensor GND to ADS1015/XRP GND")
print("- Connect sensor analog output to ADS1015 A" + str(TURBIDITY_CHANNEL))
print("- Keep analog output voltage within the ADS1015 input range")
print("- Place probe in clean water first to see the baseline reading")
print()
print("Press CTRL+C to stop")
print("=" * 50)
print()


while True:
    voltage = read_average_voltage()
    ntu = voltage_to_ntu(voltage)

    print("Voltage: " + "{:.3f}".format(voltage) + " V" +
          " | Turbidity: " + "{:.1f}".format(ntu) + " NTU")

    time.sleep(INTERVAL)
