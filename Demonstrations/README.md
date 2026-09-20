# Chloroplasters video demonstrations

Run one of these 13 standalone MicroPython files on the XRP board at a time. Each file initializes its component and the shared I2C bus where needed. Both temperature demos also control the cooling fan, and the pH demo moves the acid/base syringes in response to readings. No demo initializes or writes either pump pin, IO12 or IO18. There is no automatic irrigation, Wi-Fi, dashboard, or simulated sensor data. Use empty syringes or water for the demonstration movements; no dose volume is assumed.

## Prepare and run

1. Keep both pumps disconnected. Stop the existing controller with Ctrl+C in the board's serial/REPL console before running a demo. If the controller is installed as `main.py`, prevent it from automatically starting again before reconnecting or resetting the board. Preserve a copy of that program.
2. Start from a powered-off setup with the unused actuators disconnected or their power off. These demos do not reset outputs left active by another program. Restore power only to the hardware needed for the shot.
3. Open the selected `.py` file with your MicroPython editor (for example, the existing MicroPico setup), select the connected board, and use its run-current-file action. Alternatively, upload just that file to the board, then run it from the REPL, for example:

   ```python
   import demo_ph
   demo_ph.main()
   ```

   Re-run `demo_ph.main()` for another take. After editing an uploaded file, reset the interpreter without restarting the production controller so that the revised module is loaded. No other demonstration files need uploading. Do not upload the `tests` directory to the board.
4. Open the serial console in the recording. Sensor demos continue until Ctrl+C; standalone actuator demos run once and finish. Standalone actuator demos and pH syringe movements have a three-second countdown; temperature demos switch the fan as soon as a valid reading crosses the threshold. Wait for cleanup to finish before starting another script.
5. Review the editable constants at the top of each file for your wiring and mechanical travel. These scripts require MicroPython's `machine` and `time` modules; the DS18B20 demo also uses `onewire` and `ds18x20`.

## Shot list and wiring

| File | Connection | Prepare, film, and observe |
| --- | --- | --- |
| `demo_ph.py` | ADS1015 A0, acid IO9, base IO8 | Use empty syringes or water. Above pH 6.5 the acid servo moves; below pH 5.5 the base servo moves. Each performs 0 -> 45 -> 0 degrees once, then waits for pH to return to 5.5-6.5 before another movement. Rinse the probe between samples. Show voltage, the labeled pH estimate, and the selected action. |
| `demo_tds.py` | ADS1015 A1 | Compare separate samples of low-mineral and mineral/nutrient-containing water. Rinse between samples and let the reading settle. Show voltage and estimated ppm; the displayed temperature is an assumption. |
| `demo_turbidity.py` | ADS1015 A2 | Place the sensing area in clean water **before starting**. The first valid reading becomes the baseline. Move to a separate cloudy sample, such as water with a small amount of suspended soil. Show voltage change, then return to clean water. Restart to capture a new baseline. |
| `demo_water_temperature.py` | DS18B20 IO16, fan IO19 | Use cooler and comfortably warm water in separate cups. The fan turns ON above 30 C and OFF below 26 C, retaining its state between those thresholds. With multiple probes, the hottest controls the fan after all readings validate. Sensor errors and Ctrl+C turn it off. Adjust `FAN_ON_TEMP_C` and `FAN_OFF_TEMP_C` before filming. The probe bus requires an external 4.7k pull-up to 3.3 V. |
| `demo_air_temperature_humidity.py` | SHT31 `0x44`, fan IO19 | Record room conditions, then cup a hand near the sensor and observe changes in temperature and humidity. The fan turns ON at 28 C and OFF at 27 C; its state appears beside each reading. Adjust `FAN_ON_TEMP_C` and `FAN_OFF_TEMP_C` for the room before filming, keeping OFF below ON. Keep this sensor dry. Sensor errors and Ctrl+C turn the fan off. |
| `demo_flow.py` | IO2 | Film the stationary sensor and real zero-pulse output. Explain: “This sensor detects moving water. Our pump is disconnected, so this shot shows its input monitoring; a flowing-water test is not being demonstrated.” Zero alone does not verify sensor function. |
| `demo_rgb_led.py` | Red IO22, green IO21, blue IO23 | Film green (normal), red (safe/problem), blue (no flow), orange (cloudy water), and off, each for three seconds. These are illustrative statuses, not responses to connected sensors. |
| `demo_fan.py` | IO19 | Film three seconds off, five seconds running, then off. This demo directly operates the fan; no temperature sensor is involved. |
| `demo_acid_servo.py` | IO9 | Use an empty syringe or water. Film rest → 45° → rest. |
| `demo_base_servo.py` | IO8 | Use an empty syringe or water. Film rest → 45° → rest. |
| `demo_nutrient_servo_1.py` | IO7 | Use an empty syringe or water. Film rest → 45° → 90° → 45° → rest. |
| `demo_nutrient_servo_2.py` | IO6 | Film the same motion on the second actuator independently. |
| `demo_stop_button.py` | IO36 | Press and release the built-in USER button several times. Film one debounced event per transition. This script reports input only; it is not a global emergency-stop service for other demos. |

The I2C demos use bus 0, SDA IO4, SCL IO5, at 100 kHz. The ADS1015 address is `0x48`. Another device on that shared bus need not be present. Defaults are a common-cathode RGB LED, an active-high fan driver, and an active-low button with a pull-up. Servo pins follow `Test Files/Servo_test.py`, which differs from the production controller's mapping.

## Calibration and interpretation

- **pH servo response:** `PH_MIN = 5.5` and `PH_MAX = 6.5` are editable demo thresholds. High pH selects acid IO9 to lower pH; low pH selects base IO8 to raise pH. These are pH adjustment syringes; the nutrient servos are separate. This uses the standalone demo wiring, which differs from the production controller. A movement locks out both servos until a valid in-range reading rearms the demo, even if the next sample crosses directly to the opposite extreme. Missing, failed, or invalid readings do not trigger or rearm movement. Ctrl+C or a movement error returns the active servo to rest and releases PWM. Readings outside pH 0-14 are reported as errors. Calibrate the pH conversion before relying on the thresholds, and check the editable angle/pulse limits against your linkage.
- **ADC:** All three analog demos use configuration base `0x8383`, including the ±4.096 V gain setting, and the matching 2 mV/count conversion for signed 12-bit data. This resolves the gain/scaling mismatch in some older tests. The configured measurement range does not increase the allowable electrical input voltage: verify sensor interface outputs and any voltage divider against the actual ADC supply and wiring. See the [ADS1015 gain definitions](https://github.com/adafruit/Adafruit_ADS1X15/blob/master/Adafruit_ADS1X15.h).
- **pH:** Defaults (`NEUTRAL_PH = 7`, `NEUTRAL_VOLTAGE = 1.1`, `VOLTS_PER_PH = 0.12`) are placeholders from the individual pH test. Measure stable voltages in two known buffers. Set the reference pH/voltage to the first pair and the signed slope to `(voltage2 - voltage1) / (pH2 - pH1)`. Calibration measured with an incorrect ADC scale must be repeated. The demo deliberately retains the `UNCALIBRATED ESTIMATE` label and does not hide implausible estimates by clamping them.
- **TDS:** Uses the existing SEN0244 polynomial, an editable assumed `WATER_TEMPERATURE_C = 25.0`, and `CALIBRATION_FACTOR = 1.0`. These are estimates, not validated EC measurements. Compare with a known TDS standard before interpreting ppm quantitatively; do not claim a direct calibrated EC measurement from this demo.
- **Turbidity:** Reports voltage at the ADC input and signed voltage change from the initial sample. It does not guess NTU, divider scaling, or a clean/dirty threshold. Keep immersion depth and lighting consistent between shots; immerse only the sensor's intended sensing area, keeping its electronics dry.
- **Servos:** Defaults use the existing test mapping of 500–2500 microseconds across 0–180° at 50 Hz, bounded to the demo's configured travel. Confirm your linkage's rest and maximum positions before fitting a loaded syringe. Motion does not establish a dose volume. A cleanup command returns the selected servo to rest and then releases PWM; the hardware must remain powered and responsive for that return to occur.
- **Flow:** Only rising edges are counted. Unexpected pulses in stationary water are reported as actual input events to investigate, not converted into a claimed delivered volume. No values are synthesized.

## Verification

Desktop verification (no board required): from the repository root, run:

```text
python -m unittest discover -s Demonstrations/tests -v
```

The suite syntax-checks all 13 files and uses mocked hardware to check intended pin usage, no pump access, ADC gain/conversion, real pulse counting, sensor failures, button debounce, temperature-triggered fan control, pH servo selection and rearming, and actuator cleanup during interruption or errors. It does not establish electrical compatibility, calibration accuracy, or physical movement.

Before filming, perform these checks on the board:

- Run each sensor script with only its required sensor/interface available. Confirm real readings change with the prepared samples and missing/disconnected devices produce errors rather than plausible replacement values. An unplugged analog probe is not always detectable from an ADC voltage alone.
- Verify green/red/blue/orange match the wiring, the fan switches off when the script finishes, and the button produces one event per stable press/release.
- Run each servo separately with an empty syringe or water; confirm the correct servo moves within its mechanical limits and returns to rest.
- In the water-temperature demo, verify the fan starts above 30 C and stops below 26 C. In the pH demo, verify the acid/base selection using separate samples and return to an in-range sample to rearm between movements. Use empty syringes or water.
- Interrupt the fan, LED, and servo demos with Ctrl+C while active; confirm off/rest and successful reruns. Power removal cannot execute software cleanup.
- Confirm the flow demo shows expected zero pulses with stationary water. This shot intentionally leaves actual flowing-water performance unverified.

Existing controller and test files are unchanged by this demonstration suite.
