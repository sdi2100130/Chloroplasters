# =========================================================
# Chloroplasters - Sensor readings
# =========================================================

from machine import Pin, I2C
import time
import onewire
import ds18x20

# --- I2C bus (ADS1015 + SHT31 via Qwiic) ---
I2C_SDA_PIN  = 4
I2C_SCL_PIN  = 5
ADS1015_ADDR = 0x48
SHT31_ADDR   = 0x44

# --- Analog channels on ADS1015 ---
PH_CHANNEL        = 0
EC_CHANNEL        = 1
TURBIDITY_CHANNEL = 2

# --- Digital sensors ---
WATER_TEMP_PIN = 16

ADS1015_REG_CONVERSION = 0x00
ADS1015_REG_CONFIG     = 0x01
ADS1015_CONFIG_BASE    = 0x8583
ADS1015_MUX = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}

i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)

ds_pin = Pin(WATER_TEMP_PIN)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
roms = ds_sensor.scan()
if not roms:
    print("WARNING: DS18B20 not found! Check 4.7k pull-up resistor.")


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


def get_water_temp():
    """Read DS18B20 water temperature. Returns -999 on failure."""
    if not roms:
        return -999
    try:
        ds_sensor.convert_temp()
        time.sleep_ms(750)
        return ds_sensor.read_temp(roms[0])
    except Exception:
        return -999


def get_ph():
    """Read pH from ADS1015 A0. Returns -999 on failure."""
    voltage = ads1015_read_channel(PH_CHANNEL)
    if voltage is None:
        return -999
    return 7 + (2.5 - voltage) / 0.18  # TRIAL-AND-ERROR: calibrate 2.5V reference and 0.18 slope with pH buffers.


def get_ec():
    """Read EC (mS/cm) from ADS1015 A1. Returns -999 on failure."""
    voltage = ads1015_read_channel(EC_CHANNEL)
    if voltage is None:
        return -999
    return voltage * 2.0  # TRIAL-AND-ERROR: replace multiplier after calibrating with known EC solution.


def get_turbidity():
    """Read turbidity (NTU) from ADS1015 A2. Returns -999 on failure."""
    voltage = ads1015_read_channel(TURBIDITY_CHANNEL)
    if voltage is None:
        return -999
    actual_voltage = voltage * 1.5  # TRIAL-AND-ERROR: adjust scaling for the real turbidity sensor wiring/output.
    if actual_voltage < 0.1:
        return 3000
    return 3000 / actual_voltage  # TRIAL-AND-ERROR: calibrate NTU conversion with known/observed water samples.


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


def read_all():
    """Read all environmental sensors and return one snapshot dictionary."""
    air_temp, air_humidity = read_sht31()
    return {
        "ph": get_ph(),
        "ec": get_ec(),
        "turbidity": get_turbidity(),
        "water_temp": get_water_temp(),
        "air_temp": air_temp,
        "air_humidity": air_humidity,
    }
