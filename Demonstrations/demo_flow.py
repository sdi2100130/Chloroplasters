"""Real flow pulse monitoring with a stationary-water explanation."""
from machine import Pin, disable_irq, enable_irq
import time

FLOW_SENSOR_PIN = 2
INTERVAL_MS = 1000
pulse_count = 0


def pulse_handler(pin):
    global pulse_count
    pulse_count += 1


def take_pulses():
    global pulse_count
    state = disable_irq()
    try:
        count = pulse_count
        pulse_count = 0
    finally:
        enable_irq(state)
    return count


def main():
    global pulse_count
    flow_pin = None
    total = 0
    pulse_count = 0
    print("FLOW SENSOR DEMO | Pump disconnected | REAL INPUT ONLY")
    print("Stationary water produces no flow pulses; zero is expected.")
    print("This shot explains the sensor; it does not demonstrate flowing water.")
    print("Zero pulses alone cannot confirm that the sensor works.")
    print("Press Ctrl+C to stop.")
    try:
        flow_pin = Pin(FLOW_SENSOR_PIN, Pin.IN, Pin.PULL_UP)
        flow_pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_handler)
        while True:
            time.sleep_ms(INTERVAL_MS)
            count = take_pulses()
            total += count
            if count == 0:
                print("No flow pulses | interval: 0 | total:", total,
                      "| expected with pump disconnected")
            else:
                print("Real input pulses | interval:", count, "| total:", total,
                      "| unexpected in stationary water; check setup")
    except KeyboardInterrupt:
        print("Demo stopped.")
    except Exception as exc:
        print("DEMO ERROR:", exc)
    finally:
        if flow_pin is not None:
            flow_pin.irq(handler=None)


if __name__ == "__main__":
    main()

