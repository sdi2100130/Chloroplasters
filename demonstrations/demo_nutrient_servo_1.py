"""Independent nutrient syringe 1 movement; use an empty syringe or water."""
from machine import Pin, PWM
import time

SERVO_PIN = 7
SERVO_REST_ANGLE = 0
SERVO_STEP_ANGLE = 45
SERVO_MAX_ANGLE = 90
MIN_PULSE_US = 500
MAX_PULSE_US = 2500
STEP_SECONDS = 0.8
HOLD_SECONDS = 1.0
RETURN_SECONDS = 1.0


def validate_settings():
    if not 0 <= SERVO_REST_ANGLE < SERVO_MAX_ANGLE <= 180:
        raise ValueError("Angles must satisfy 0 <= rest < maximum <= 180")
    if SERVO_STEP_ANGLE <= 0:
        raise ValueError("Angle step must be positive")
    if not 0 < MIN_PULSE_US < MAX_PULSE_US < 20000:
        raise ValueError("Invalid servo pulse limits")
    if min(STEP_SECONDS, RETURN_SECONDS) <= 0 or HOLD_SECONDS < 0:
        raise ValueError("Invalid movement timing")


def angle_to_duty(angle):
    if not SERVO_REST_ANGLE <= angle <= SERVO_MAX_ANGLE:
        raise ValueError("Angle outside configured movement limits")
    pulse_us = MIN_PULSE_US + int(angle / 180 * (MAX_PULSE_US - MIN_PULSE_US))
    return int(pulse_us * 65535 / 20000)


def main():
    pwm = None
    print("NUTRIENT SYRINGE 1 DEMO | IO7 | Pump disconnected")
    print("Use an empty syringe or water. Check the linkage and angle limits.")
    print("One movement cycle; no dose volume is assumed. Ctrl+C returns to rest.")
    try:
        validate_settings()
        for seconds in (3, 2, 1):
            print("Movement starts in", seconds)
            time.sleep(1)
        pwm = PWM(Pin(SERVO_PIN, Pin.OUT, value=0), freq=50, duty_u16=0)
        angle = SERVO_REST_ANGLE
        print("Rest angle:", angle)
        pwm.duty_u16(angle_to_duty(angle))
        time.sleep(RETURN_SECONDS)
        while angle < SERVO_MAX_ANGLE:
            angle = min(angle + SERVO_STEP_ANGLE, SERVO_MAX_ANGLE)
            print("Move to:", angle, "degrees")
            pwm.duty_u16(angle_to_duty(angle))
            time.sleep(STEP_SECONDS)
        print("Hold for", HOLD_SECONDS, "seconds")
        time.sleep(HOLD_SECONDS)
        while angle > SERVO_REST_ANGLE:
            angle = max(angle - SERVO_STEP_ANGLE, SERVO_REST_ANGLE)
            print("Return to:", angle, "degrees")
            pwm.duty_u16(angle_to_duty(angle))
            time.sleep(STEP_SECONDS)
        print("Movement complete.")
    except KeyboardInterrupt:
        print("Demo stopped; returning to rest.")
    except Exception as exc:
        print("DEMO ERROR:", exc)
    finally:
        if pwm is not None:
            try:
                pwm.duty_u16(angle_to_duty(SERVO_REST_ANGLE))
                time.sleep(RETURN_SECONDS)
            finally:
                try:
                    pwm.deinit()
                finally:
                    Pin(SERVO_PIN, Pin.OUT, value=0)


if __name__ == "__main__":
    main()

