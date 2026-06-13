from machine import Pin, I2C
import time

I2C_SDA_PIN = 4    # IO4 -> Qwiic 0 SDA
I2C_SCL_PIN = 5    # IO5 -> Qwiic 0 SCL
SHT31_ADDR  = 0x44 # Default I2C address of SHT31


# =========================================================
# I2C BUS INITIALIZATION
# =========================================================

print("=" * 50)
print("HUMIDITY & TEMPERATURE SENSOR TEST - SHT31")
print("=" * 50)
print("Sensor connected via Qwiic 0 (IO4=SDA, IO5=SCL)")
print()

# Setup the I2C bus
i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)

# Scan the I2C bus for connected devices
print("Scanning I2C bus...")
devices = i2c.scan()

if len(devices) == 0:
    print()
    print("❌ ERROR: No I2C devices found!")
    print()
    print("Check these things:")
    print("  1. Is the Qwiic cable firmly connected on both sides?")
    print("  2. Is the SHT31 connected to Qwiic 0 (not Qwiic 1)?")
    print("  3. Is the cable damaged?")
    print("  4. Try a different Qwiic cable")
    print()
else:
    print("✅ Found " + str(len(devices)) + " I2C device(s):")
    for device in devices:
        print("   Address: " + hex(device))

    if SHT31_ADDR in devices:
        print("   -> SHT31 detected! ✅")
    else:
        print("   -> SHT31 NOT FOUND at 0x44 ❌")
        print("      Check the wiring or the sensor address")
    print()


# =========================================================
# SHT31 READING FUNCTION
# =========================================================

def read_sht31():
    """Read temperature and humidity from SHT31.
    Returns (temperature_C, humidity_percent) or (None, None) on error."""
    try:
        # Send measurement command (high repeatability, no clock stretching)
        i2c.writeto(SHT31_ADDR, b'\x24\x00')
        time.sleep(0.02)  # Wait 20ms for measurement
        data = i2c.readfrom(SHT31_ADDR, 6)

        # Combine bytes into 16-bit values
        temp_raw = (data[0] << 8) | data[1]
        hum_raw  = (data[3] << 8) | data[4]

        # Convert to real values (from SHT31 datasheet)
        temperature = -45 + (175 * temp_raw / 65535)
        humidity    = 100 * hum_raw / 65535
        return (temperature, humidity)
    except Exception as e:
        print("Read error:", e)
        return (None, None)


# =========================================================
# MAIN TEST LOOP
# =========================================================

if SHT31_ADDR in devices:
    print("=" * 50)
    print("READING TEMPERATURE & HUMIDITY...")
    print("=" * 50)
    print()
    print("INSTRUCTIONS:")
    print("- Watch the readings below")
    print("- Try breathing on the sensor (humidity should jump)")
    print("- Try cupping it in your hand (temperature should rise)")
    print("- Try moving it near a cold window or warm lamp")
    print()
    print("Press CTRL+C to stop")
    print("=" * 50)
    print()

    reading_count = 0

    while True:
        # Read the sensor
        temp, hum = read_sht31()

        if temp is None or hum is None:
            print("❌ Failed to read sensor - check connections")
            time.sleep(2)
            continue

        reading_count = reading_count + 1

        # Decide which emoji to show based on temperature
        if temp < 15:
            temp_emoji = "❄️  COOL"
        elif temp < 25:
            temp_emoji = "🌡️  NORMAL"
        elif temp < 30:
            temp_emoji = "☀️  WARM"
        else:
            temp_emoji = "🔥 HOT"

        # Decide which emoji to show based on humidity
        if hum < 30:
            hum_emoji = "🏜️  DRY"
        elif hum < 60:
            hum_emoji = "💧 NORMAL"
        elif hum < 80:
            hum_emoji = "💦 HUMID"
        else:
            hum_emoji = "🌊 VERY HUMID"

        # Print the reading
        print("Reading #" + str(reading_count) +
              " | Temp: " + "{:.2f}".format(temp) + "°C " + temp_emoji +
              " | Humidity: " + "{:.1f}".format(hum) + "% " + hum_emoji)

        # Wait before next reading
        time.sleep(1)