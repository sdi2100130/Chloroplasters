"""Independent RGB status-light sequence; status meanings are illustrative."""
from machine import Pin, PWM
import time

RGB_RED_PIN = 22
RGB_GREEN_PIN = 21
RGB_BLUE_PIN = 23
RGB_COMMON_ANODE = False
COLOR_SECONDS = 3
PWM_FREQUENCY = 1000
COLORS = (
    ("GREEN - normal operation", (0, 255, 0)),
    ("RED - safe mode / problem", (255, 0, 0)),
    ("BLUE - no-flow warning", (0, 0, 255)),
    ("ORANGE - cloudy-water warning", (255, 120, 0)),
    ("OFF", (0, 0, 0)),
)


def channel_duty(value):
    duty = int(max(0, min(255, value)) * 65535 / 255)
    return 65535 - duty if RGB_COMMON_ANODE else duty


def main():
    channels = []
    off = 1 if RGB_COMMON_ANODE else 0
    print("RGB LED DEMO | Pump disconnected")
    print("Colors demonstrate status meanings, not current sensor conditions.")
    print("Press Ctrl+C to stop and turn the LED off.")
    try:
        for pin_number in (RGB_RED_PIN, RGB_GREEN_PIN, RGB_BLUE_PIN):
            pin = Pin(pin_number, Pin.OUT, value=off)
            pwm = PWM(pin, freq=PWM_FREQUENCY, duty_u16=channel_duty(0))
            channels.append((pin_number, pwm))
        for seconds in (3, 2, 1):
            print("Colors start in", seconds)
            time.sleep(1)
        for label, color in COLORS:
            print(label)
            for (_, pwm), value in zip(channels, color):
                pwm.duty_u16(channel_duty(value))
            time.sleep(COLOR_SECONDS)
    except KeyboardInterrupt:
        print("Demo stopped.")
    except Exception as exc:
        print("DEMO ERROR:", exc)
    finally:
        # Attempt every channel even when one cleanup operation fails.
        for pin_number, pwm in channels:
            try:
                pwm.duty_u16(channel_duty(0))
            except Exception as exc:
                print("LED off error:", exc)
            try:
                pwm.deinit()
            except Exception as exc:
                print("PWM release error:", exc)
            try:
                Pin(pin_number, Pin.OUT, value=off)
            except Exception as exc:
                print("Pin off error:", exc)
        print("LED sequence finished.")


if __name__ == "__main__":
    main()

