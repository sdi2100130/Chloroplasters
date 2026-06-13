
from machine import Pin
import onewire
import ds18x20
import time


DS18B20_PIN = 16   # IO16 -> yellow wire from DS18B20
pin = Pin(16, Pin.IN, Pin.PULL_UP)

print("Pin value before scan:", pin.value())
# SENSOR INITIALIZATION'''

print("=" * 50)
print("WATER TEMPERATURE SENSOR TEST - DS18B20")
print("=" * 50)
print("Sensor connected to IO" + str(DS18B20_PIN))
print()

# Setup the 1-Wire bus on the pin
ow = onewire.OneWire(pin)
print(ow)
ds = ds18x20.DS18X20(ow)
print(ds)
# Scan for connected DS18B20 sensors
print("Scanning for DS18B20 sensors...")
sensors = ds.scan()
print(sensors)

if len(sensors) == 0:
    print()
    print(" ERROR: No DS18B20 sensor found!")
    print()
    print("Check these things:")
    print("  1. Is the sensor connected to IO" + str(DS18B20_PIN) + "?")
    print("  2. Is the 4.7kΩ pull-up resistor installed?")
    print("  3. Is the VCC connected to 3.3V?")
    print("  4. Is the GND connected to GND?")
    print("  5. Are all wires firmly inserted?")
    print()
else:
    print(" Found " + str(len(sensors)) + " sensor(s)")
    for i, sensor in enumerate(sensors):
        print("   Sensor " + str(i + 1) + " ID: " + str(sensor))
    print()


if len(sensors) > 0:
    print("=" * 50)
    print("READING TEMPERATURE...")
    print("=" * 50)
    print()
    print("INSTRUCTIONS:")
    print("- Watch the temperature reading below")
    print("- Try dipping the sensor in cold water")
    print("- Try holding it in your hand to warm it up")
    print("- Try ice water for cold test")
    print()
    print("Press CTRL+C to stop")
    print("=" * 50)
    print()

    reading_count = 0

    while True:
        # Request a temperature conversion from all sensors
        ds.convert_temp()

        # Wait for conversion to complete (DS18B20 needs ~750ms)
        time.sleep(1)

        reading_count = reading_count + 1

        # Read each sensor
        for i, sensor in enumerate(sensors):
            temp = ds.read_temp(sensor)

            # Decide which emoji to show based on temperature
            if temp < 10:
                emoji = "COLD"
            elif temp < 20:
                emoji = "COOL"
            elif temp < 28:
                emoji = "NORMAL"
            elif temp < 35:
                emoji = "WARM"
            else:
                emoji = "HOT"

            # Print the reading
            print("Reading #" + str(reading_count) +
                  " | Sensor " + str(i + 1) +
                  " | Temperature: " + "{:.2f}".format(temp) + "°C" +
                  " | " + emoji)