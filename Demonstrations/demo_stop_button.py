"""Independent debounced button events; this script controls no actuators."""
from machine import Pin
import time

STOP_BUTTON_PIN = 36
BUTTON_ACTIVE_LOW = True
DEBOUNCE_MS = 50
POLL_MS = 10


def print_state(value):
    pressed = value == (0 if BUTTON_ACTIVE_LOW else 1)
    print("Button PRESSED" if pressed else "Button RELEASED")


def main():
    print("STOP BUTTON DEMO | IO36 | Pump disconnected")
    print("Press and release the USER button to show debounced input events.")
    print("This isolated demo reports the button only. Ctrl+C stops it.")
    try:
        pull = Pin.PULL_UP if BUTTON_ACTIVE_LOW else Pin.PULL_DOWN
        button = Pin(STOP_BUTTON_PIN, Pin.IN, pull)
        stable = candidate = button.value()
        changed_at = time.ticks_ms()
        print_state(stable)
        while True:
            now = time.ticks_ms()
            value = button.value()
            if value != candidate:
                candidate = value
                changed_at = now
            elif candidate != stable and time.ticks_diff(now, changed_at) >= DEBOUNCE_MS:
                stable = candidate
                print_state(stable)
            time.sleep_ms(POLL_MS)
    except KeyboardInterrupt:
        print("Demo stopped.")
    except Exception as exc:
        print("DEMO ERROR:", exc, "| check button pin and firmware")


if __name__ == "__main__":
    main()

