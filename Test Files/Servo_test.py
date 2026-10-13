from machine import Pin, PWM
import time


# =========================================================
# Chloroplasters servo actuator test
# =========================================================
# This test exercises syringe actuators using positional servos:
# - pH acid servo: move to dosing angle, hold, return to rest
# - pH base servo: move to dosing angle, hold, return to rest
# - nutrient syringe 1 and 2: move together, hold, return to rest
#
# This file does not require XRPLib.
# Press CTRL+C at any time to return all tested servos to rest.


# --- Servo pins ---
PH_ACID_SERVO_PIN = 9
PH_BASE_SERVO_PIN = 8
NUTRIENT_SERVO_PIN = 7
NUTRIENT_2_SERVO_PIN = 6

ACTIVE_SERVO_PINS = (
    PH_ACID_SERVO_PIN,
    PH_BASE_SERVO_PIN,
    NUTRIENT_SERVO_PIN,
    NUTRIENT_2_SERVO_PIN,
)

# --- Test calibration: adjust angles to your syringe linkage ---
SERVO_REST_ANGLE = 0
SERVO_1ML_ANGLE = 45  # TRIAL-AND-ERROR: increased test dose angle for clearer movement
ACID_BASE_HOLD_S = 1.0

NUTRIENT_SYRINGE_ANGLE_STEP = 45  # TRIAL-AND-ERROR: nutrient syringe motor/servo step size
NUTRIENT_SYRINGE_MAX_ANGLE = 90  # TRIAL-AND-ERROR: nutrient syringe max dosing angle
NUTRIENT_SYRINGE_HOLD_SECONDS = 1.0
NUTRIENT_SYRINGE_STEP_SECONDS = 0.8  # Time for each forward/return step
NUTRIENT_SYRINGE_RETURN_SECONDS = 1.0  # Time to reach rest before releasing PWM

SETTLE_S = 0.5
PAUSE_BETWEEN_TESTS_S = 2
FULL_TEST_CYCLES = 1
RUN_RANGE_CHECKS = False  # Enable only when checking the servo's free movement


def angle_to_duty(angle):
    """Convert a servo angle to a 16-bit PWM duty value."""
    angle = max(0, min(180, angle))
    min_pulse_us = 500
    max_pulse_us = 2500
    pulse_us = min_pulse_us + int((angle / 180) * (max_pulse_us - min_pulse_us))
    return int(pulse_us * 65535 / 20000)


def set_servo_angle(pin_num, angle, hold_s=SETTLE_S):
    """Move one servo to an angle, hold briefly, then release PWM."""
    pwm = PWM(Pin(pin_num))
    pwm.freq(50)
    pwm.duty_u16(angle_to_duty(angle))
    time.sleep(hold_s)
    pwm.deinit()


def set_all_to_rest():
    """Return all active servos to their safe rest angle."""
    print("Returning all active servos to rest.")
    for servo_pin in ACTIVE_SERVO_PINS:
        set_servo_angle(servo_pin, SERVO_REST_ANGLE)


def test_single_servo_range(servo_pin, label):
    """Small movement test to confirm the servo responds before full actuator tests."""
    print()
    print("[Range check]", label, "on IO" + str(servo_pin))
    for angle in (SERVO_REST_ANGLE, 45, 90, 135, 90, 45, SERVO_REST_ANGLE):
        print(label, "angle:", angle)
        set_servo_angle(servo_pin, angle, hold_s=0.8)


def push_syringe(servo_pin, label):
    """Test acid/base syringe behavior: dose angle, hold, return to rest."""
    print()
    print("[Acid/Base test]", label, "on IO" + str(servo_pin))
    print("Move to dose angle:", SERVO_1ML_ANGLE)
    set_servo_angle(servo_pin, SERVO_1ML_ANGLE)
    print("Holding dose position for", ACID_BASE_HOLD_S, "s")
    time.sleep(ACID_BASE_HOLD_S)
    print("Return to rest:", SERVO_REST_ANGLE)
    set_servo_angle(servo_pin, SERVO_REST_ANGLE)


def push_nutrient_syringes_parallel(servo_pins):
    """Push both plungers, hold, then move both servos back to their start angle."""
    if not 0 <= SERVO_REST_ANGLE < NUTRIENT_SYRINGE_MAX_ANGLE <= 180:
        raise ValueError("Nutrient angles must satisfy 0 <= rest < maximum <= 180")
    if NUTRIENT_SYRINGE_ANGLE_STEP <= 0:
        raise ValueError("Nutrient angle step must be positive")
    if min(NUTRIENT_SYRINGE_STEP_SECONDS, NUTRIENT_SYRINGE_RETURN_SECONDS) <= 0 or NUTRIENT_SYRINGE_HOLD_SECONDS < 0:
        raise ValueError("Movement times must be positive and hold time nonnegative")
    print()
    print("[Nutrient syringe test] Nutrient syringes on IO pins", servo_pins)
    pwms = []
    try:
        for servo_pin in servo_pins:
            pwm = PWM(Pin(servo_pin))
            pwms.append(pwm)
            pwm.freq(50)

        for pwm in pwms:
            pwm.duty_u16(angle_to_duty(SERVO_REST_ANGLE))
        time.sleep(NUTRIENT_SYRINGE_RETURN_SECONDS)

        angle = SERVO_REST_ANGLE
        while angle < NUTRIENT_SYRINGE_MAX_ANGLE:
            angle = min(angle + NUTRIENT_SYRINGE_ANGLE_STEP, NUTRIENT_SYRINGE_MAX_ANGLE)
            print("Nutrient syringes angle:", angle)
            duty = angle_to_duty(angle)
            for pwm in pwms:
                pwm.duty_u16(duty)
            time.sleep(NUTRIENT_SYRINGE_STEP_SECONDS)

        print("Holding nutrient syringes for", NUTRIENT_SYRINGE_HOLD_SECONDS, "s")
        time.sleep(NUTRIENT_SYRINGE_HOLD_SECONDS)

        print("Returning nutrient syringes to rest:", SERVO_REST_ANGLE)
        while angle > SERVO_REST_ANGLE:
            angle = max(angle - NUTRIENT_SYRINGE_ANGLE_STEP, SERVO_REST_ANGLE)
            for pwm in pwms:
                pwm.duty_u16(angle_to_duty(angle))
            time.sleep(NUTRIENT_SYRINGE_STEP_SECONDS)
    finally:
        # Command rest even if the push or hold is interrupted.
        try:
            for pwm in pwms:
                pwm.duty_u16(angle_to_duty(SERVO_REST_ANGLE))
            if pwms:
                time.sleep(NUTRIENT_SYRINGE_RETURN_SECONDS)
        finally:
            for pwm in pwms:
                pwm.deinit()


def test_final_actuator_sequence():
    """Run the same actuator types used by the final tower garden code."""
    print()
    print("=================================================")
    print("Final actuator sequence test")
    print("=================================================")

    push_syringe(PH_ACID_SERVO_PIN, "pH acid syringe")
    time.sleep(PAUSE_BETWEEN_TESTS_S)

    push_syringe(PH_BASE_SERVO_PIN, "pH base syringe")
    time.sleep(PAUSE_BETWEEN_TESTS_S)

    push_nutrient_syringes_parallel((NUTRIENT_SERVO_PIN, NUTRIENT_2_SERVO_PIN))
    time.sleep(PAUSE_BETWEEN_TESTS_S)

    set_all_to_rest()
    print("Sequence complete.")


def main():
    print("Chloroplasters servo test")
    print("Active servos:")
    print("- pH acid syringe: IO" + str(PH_ACID_SERVO_PIN))
    print("- pH base syringe: IO" + str(PH_BASE_SERVO_PIN))
    print("- nutrient syringe 1: IO" + str(NUTRIENT_SERVO_PIN))
    print("- nutrient syringe 2: IO" + str(NUTRIENT_2_SERVO_PIN))
    print("Press CTRL+C to stop and return servos to rest.")

    try:
        set_all_to_rest()

        if RUN_RANGE_CHECKS:
            test_single_servo_range(PH_ACID_SERVO_PIN, "pH acid syringe")
            test_single_servo_range(PH_BASE_SERVO_PIN, "pH base syringe")
            test_single_servo_range(NUTRIENT_SERVO_PIN, "nutrient syringe 1")
            test_single_servo_range(NUTRIENT_2_SERVO_PIN, "nutrient syringe 2")

        for cycle in range(FULL_TEST_CYCLES):
            print()
            print("Full sequence cycle", cycle + 1, "of", FULL_TEST_CYCLES)
            test_final_actuator_sequence()

        print()
        print("All servo tests completed successfully.")
        set_all_to_rest()
    except KeyboardInterrupt:
        print()
        print("Interrupted by user.")
        set_all_to_rest()


main()
