
from machine import Pin
import time


FLOW_SENSOR_PIN = 2   # IO2 -> yellow wire from flow sensor

# YF-S201 calibration: ~450 pulses per liter of water
# Formula: Flow (L/min) = pulses_per_second / 7.5
PULSES_PER_LITER = 450


pulse_count = 0

def pulse_handler(pin):
    """Called automatically every time the sensor sends a pulse."""
    global pulse_count
    pulse_count += 1

# Setup the pin as input with pull-up, and attach interrupt
flow_pin = Pin(FLOW_SENSOR_PIN, Pin.IN, Pin.PULL_UP)
flow_pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_handler)

# MAIN TEST LOOP


print("=" * 50)
print("FLOW SENSOR TEST - YF-S201")
print("=" * 50)
print("Sensor connected to IO" + str(FLOW_SENSOR_PIN))
print()
print("INSTRUCTIONS:")
print("- Blow gently into the sensor")
print("- OR run water through it")
print("- Watch the numbers below")
print()
print("Press CTRL+C to stop")
print("=" * 50)
print()

# Reading interval in seconds
INTERVAL = 1.0

while True:
    # Reset counter and wait
    pulse_count = 0
    time.sleep(INTERVAL)

    # Read pulses from this interval
    pulses = pulse_count

    # Calculate flow rate
    pulses_per_second = pulses / INTERVAL
    flow_rate_lpm = pulses_per_second / 7.5   # liters per minute
    flow_rate_lph = flow_rate_lpm * 60        # liters per hour

    # Display results
    if pulses == 0:
        print(" No flow detected   | Pulses: 0")
    else:
        print(" FLOW DETECTED!     | Pulses: " + str(pulses) +
              " | " + "{:.2f}".format(flow_rate_lpm) + " L/min" +
              " | " + "{:.1f}".format(flow_rate_lph) + " L/hour")