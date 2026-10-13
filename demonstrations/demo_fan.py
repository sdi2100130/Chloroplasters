"""Independent cooling fan: three seconds off, five seconds on, then off."""
from machine import Pin
import time

FAN_PIN = 19
FAN_ACTIVE_HIGH = False
ON_SECONDS = 5


def main():
    fan = None
    off = 0 if FAN_ACTIVE_HIGH else 1
    on = 1 - off
    print("FAN DEMO | IO19 | Pump disconnected")
    print("Three seconds OFF, five seconds ON, then OFF. Ctrl+C stops the fan.")
    try:
        fan = Pin(FAN_PIN, Pin.OUT, value=off)
        for seconds in (3, 2, 1):
            print("Fan OFF; starts in", seconds)
            time.sleep(1)
        print("Fan ON")
        fan.value(on)
        time.sleep(ON_SECONDS)
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

