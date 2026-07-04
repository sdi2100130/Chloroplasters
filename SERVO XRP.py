"""
MG995 Servo Test - 30 degree rotation (XRP Controller / MicroPython)
--------------------------------------------------------------------
Plug the servo into a SERVO port on the XRP Controller.
  - Servo index 1 -> SERVO_1 port, index 2 -> SERVO_2, etc.
  - Beta boards only have ports 1 and 2.

Note on units: XRPLib's set_angle() maps 0..200 to a 500..2500 us pulse
(10 us per unit + 500 us offset). On an MG995 these units are only
APPROXIMATELY physical degrees, so measure with a protractor and adjust
STEP/positions if you need true 30 deg moves.

Power warning: the MG995 can pull ~1A under load. The XRP servo port is
fed from the battery/regulator, so avoid holding it against a stall for
long. Use a fresh/charged battery for reliable motion.
"""

from XRPLib.servo import Servo
import time

STEP     = 30     # units per step (see note above)
HOLD_S   = 1.0    # pause at each position so you can read the angle
SETTLE_S = 0.4    # time for a 30-unit move to finish (MG995 ~0.13-0.17s/60deg)

# Use SERVO_1 port. Change index to 2/3/4 for other ports.
servo = Servo.get_default_servo(index=1)


def go_to(angle):
    servo.set_angle(angle)
    print("Commanded angle:", angle)
    time.sleep(SETTLE_S)


def test_full_sweep():
    print("\n[Test 1] Stepping 0 -> 180 in 30-unit increments")
    for a in range(0, 181, STEP):
        go_to(a)
        time.sleep(HOLD_S)

    print("[Test 1] Stepping 180 -> 0 in 30-unit increments")
    for a in range(180, -1, -STEP):
        go_to(a)
        time.sleep(HOLD_S)


def test_back_and_forth():
    print("\n[Test 2] 30-unit back-and-forth x5")
    for _ in range(5):
        go_to(60)    # reference position
        time.sleep(HOLD_S)
        go_to(90)    # +30 units
        time.sleep(HOLD_S)


def main():
    print("MG995 30-degree rotation test (XRP)")
    servo.set_angle(0)
    time.sleep(1.0)
    try:
        while True:
            test_full_sweep()
            test_back_and_forth()
            print("\nCycle complete. Restarting in 3s...")
            time.sleep(3.0)
    except KeyboardInterrupt:
        servo.free()   # release the servo so it stops holding
        print("Stopped, servo released.")


main()