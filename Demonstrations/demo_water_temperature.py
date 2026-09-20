"""DS18B20 water temperature demonstration with cooling fan control."""
from machine import Pin
import onewire
import ds18x20
import time

WATER_TEMP_PIN = 16
INTERVAL_MS = 1000
CONVERSION_MS = 750
FAN_PIN = 19
FAN_ACTIVE_HIGH = True
FAN_ON_TEMP_C = 30.0
FAN_OFF_TEMP_C = 26.0


def main():
    fan = None
    fan_is_on = False
    off = 0 if FAN_ACTIVE_HIGH else 1
    on = 1 - off
    print("WATER TEMPERATURE DEMO | Pump disconnected")
    print("Move the waterproof probe between cooler and warmer water.")
    print("IO16 requires an external 4.7k pull-up. Press Ctrl+C to stop.")
    print("Fan IO{}: ON above {} C, OFF below {} C (hottest probe).".format(
        FAN_PIN, FAN_ON_TEMP_C, FAN_OFF_TEMP_C))
    try:
        fan = Pin(FAN_PIN, Pin.OUT, value=off)
        if not -55 <= FAN_OFF_TEMP_C < FAN_ON_TEMP_C <= 125:
            raise ValueError("Fan thresholds must satisfy -55 <= OFF < ON <= 125")
        sensor = ds18x20.DS18X20(onewire.OneWire(Pin(WATER_TEMP_PIN)))
        roms = sensor.scan()
        if not roms:
            print("ERROR: No DS18B20 found; check IO16, power and pull-up.")
            return
        print("Reading", len(roms), "probe(s) on IO16.")
        while True:
            start = time.ticks_ms()
            try:
                sensor.convert_temp()
                time.sleep_ms(CONVERSION_MS)
                hottest = -55.0
                for index, rom in enumerate(roms):
                    temperature = sensor.read_temp(rom)
                    if not -55 <= temperature <= 125:
                        raise ValueError("Invalid DS18B20 temperature")
                    hottest = max(hottest, temperature)
                    print("Probe {} | Water temperature: {:.2f} C".format(
                        index + 1, temperature))
                if hottest > FAN_ON_TEMP_C:
                    fan_is_on = True
                elif hottest < FAN_OFF_TEMP_C:
                    fan_is_on = False
                fan.value(on if fan_is_on else off)
                print("Fan: {} | Hottest water: {:.2f} C".format(
                    "ON" if fan_is_on else "OFF", hottest))
            except Exception as exc:
                fan.value(off)
                fan_is_on = False
                print("READ ERROR:", exc, "| no measurement available | Fan: OFF")
            remaining = INTERVAL_MS - time.ticks_diff(time.ticks_ms(), start)
            if remaining > 0:
                time.sleep_ms(remaining)
    except KeyboardInterrupt:
        print("Demo stopped.")
    except Exception as exc:
        print("DEMO ERROR:", exc)
    finally:
        if fan is not None:
            fan.value(off)
        print("Fan OFF.")


if __name__ == "__main__":
    main()
