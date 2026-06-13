from machine import Pin, PWM
import time

PH_ACID_SERVO_PIN  = 6
PH_BASE_SERVO_PIN  = 7
NUTRIENT_SERVO_PIN = 8

SERVO_1ML_ANGLE = 20

def set_servo_angle(pin_num, angle):
    """Γυρίζει το Servo σε συγκεκριμένη γωνία (0-180)."""
    pwm = PWM(Pin(pin_num))
    pwm.freq(50)
    min_duty = 1000
    max_duty = 9000
    duty = min_duty + int((angle / 180) * (max_duty - min_duty))
    pwm.duty_u16(duty)
    time.sleep(0.5)
    pwm.deinit()

def push_syringe(servo_pin):
    """Πατάει τη σύριγγα κατά SERVO_1ML_ANGLE μοίρες για 1 δόση."""
    print("Ενεργοποίηση Σύριγγας (Pin", servo_pin, "). Παροχή 1mL...")
    set_servo_angle(servo_pin, SERVO_1ML_ANGLE)
    time.sleep(1)
    set_servo_angle(servo_pin, 0)

def main():
    #while True:
    print("\nTesting Servo 1")
    push_syringe(PH_ACID_SERVO_PIN)
    time.sleep(2)

    print("\nTesting Servo 2")
    push_syringe(PH_BASE_SERVO_PIN)
    time.sleep(2)

    print("\nTesting Servo 3")
    push_syringe(NUTRIENT_SERVO_PIN)
    time.sleep(2)

main()
