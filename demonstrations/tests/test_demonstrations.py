"""Desktop-only checks. No MicroPython board or third-party modules required."""
import contextlib
import io
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PINS = {
    'demo_ph.py': {4, 5},
    'demo_tds.py': {4, 5},
    'demo_turbidity.py': {4, 5},
    'demo_water_temperature.py': {16, 19},
    'demo_air_temperature_humidity.py': {4, 5, 19},
    'demo_flow.py': {2},
    'demo_rgb_led.py': {21, 22, 23},
    'demo_fan.py': {19},
    'demo_acid_servo.py': {9},
    'demo_base_servo.py': {8},
    'demo_nutrient_servo_1.py': {7},
    'demo_nutrient_servo_2.py': {6},
    'demo_stop_button.py': {36},
}
ACTUATORS = [name for name in EXPECTED_PINS if 'servo' in name] + [
    'demo_fan.py', 'demo_rgb_led.py']


class Hardware:
    def __init__(self, stop_ms=2300, fail_sleep=None, failure=KeyboardInterrupt):
        self.now = 0
        self.stop_ms = stop_ms
        self.fail_sleep = fail_sleep
        self.failure = failure
        self.sleeps = 0
        self.pins = []
        self.levels = {}
        self.output_events = []
        self.pwms = []
        self.irqs = {}
        self.writes = []
        self.addresses = [0x48, 0x44]
        self.adc_data = b'\x20\x00'  # 512 counts -> 1.024 V.
        self.air_data = b'\xBE\xEF\x92\xBE\xEF\x92'  # Known CRC vector.
        self.roms = [b'probe']
        self.read_error = False
        self.locked = False
        env = self

        class Pin:
            IN, OUT, PULL_UP, PULL_DOWN = 0, 1, 2, 3
            IRQ_RISING, IRQ_FALLING = 1, 2

            def __init__(self, number, mode=None, pull=None, value=None):
                if number in (12, 18):
                    raise AssertionError('Pump pin accessed')
                self.number = number
                env.pins.append(number)
                if value is not None:
                    env.levels[number] = value
                    env.output_events.append((env.now, number, value))

            def value(self, value=None):
                if value is not None:
                    env.levels[self.number] = value
                    env.output_events.append((env.now, self.number, value))
                if self.number == 36:
                    # Bounce on press, then stable press and release.
                    return 0 if 100 <= env.now < 110 or 120 <= env.now < 300 else 1
                return env.levels.get(self.number, 1)

            def irq(self, trigger=None, handler=None):
                env.irqs[self.number] = (trigger, handler)

        class PWM:
            def __init__(self, pin, freq=0, duty_u16=0):
                self.pin = pin.number
                self.frequency = freq
                self.duties = [duty_u16]
                self.released = False
                env.pwms.append(self)

            def duty_u16(self, value):
                if not 0 <= value <= 65535:
                    raise AssertionError('Invalid duty')
                self.duties.append(value)

            def deinit(self):
                self.released = True

        class I2C:
            def __init__(self, bus, scl, sda, freq):
                if (bus, scl.number, sda.number, freq) != (0, 5, 4, 100000):
                    raise AssertionError('Unexpected I2C configuration')

            def scan(self):
                return env.addresses

            def writeto(self, address, data):
                env.writes.append((address, data))

            def readfrom(self, address, size):
                if env.read_error:
                    raise OSError('Disconnected sensor')
                return env.adc_data if address == 0x48 else env.air_data

        class DS18X20:
            def __init__(self, bus):
                pass

            def scan(self):
                return env.roms

            def convert_temp(self):
                if env.read_error:
                    raise OSError('Disconnected probe')

            def read_temp(self, rom):
                return 23.5

        self.modules = {
            'machine': types.SimpleNamespace(Pin=Pin, PWM=PWM, I2C=I2C,
                                            disable_irq=self.disable_irq,
                                            enable_irq=self.enable_irq),
            'time': types.SimpleNamespace(sleep=lambda seconds: self.sleep_ms(seconds * 1000),
                                          sleep_ms=self.sleep_ms,
                                          ticks_ms=lambda: self.now,
                                          ticks_diff=lambda a, b: a - b),
            'onewire': types.SimpleNamespace(OneWire=lambda pin: pin),
            'ds18x20': types.SimpleNamespace(DS18X20=DS18X20),
        }

    def disable_irq(self):
        previous = self.locked
        self.locked = True
        return previous

    def enable_irq(self, state):
        self.locked = state

    def sleep_ms(self, milliseconds):
        self.sleeps += 1
        self.now += milliseconds
        if self.sleeps == self.fail_sleep:
            raise self.failure('Injected interruption/error')
        if self.stop_ms is not None and self.now >= self.stop_ms:
            self.stop_ms = None  # Only interrupt once, allowing cleanup to run.
            raise KeyboardInterrupt

    def load(self, name):
        with patch.dict(sys.modules, self.modules):
            module = runpy.run_path(str(ROOT / name), run_name='demo_under_test')
        if self.pins:
            raise AssertionError('Hardware initialized during import')
        return module

    def run(self, name, overrides=None):
        module = self.load(name)
        module['main'].__globals__.update(overrides or {})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            module['main']()
        return module, output.getvalue()


class DemoTests(unittest.TestCase):
    def test_syntax_and_inventory(self):
        files = list(ROOT.glob('demo_*.py'))
        self.assertEqual({file.name for file in files}, set(EXPECTED_PINS))
        for file in files:
            compile(file.read_text(encoding='utf-8'), str(file), 'exec')

    def test_component_isolation_and_no_pumps(self):
        for name, expected in EXPECTED_PINS.items():
            with self.subTest(name=name):
                env = Hardware(stop_ms=None if name in ACTUATORS else 2300)
                _, output = env.run(name)
                self.assertEqual(set(env.pins), expected)
                self.assertNotIn('ERROR', output)
                expected_address = 0x44 if 'air_temperature' in name else 0x48
                self.assertTrue(all(addr == expected_address for addr, _ in env.writes))

    def test_adc_configuration_and_signed_conversion(self):
        for name, channel in [('demo_ph.py', 0), ('demo_tds.py', 1), ('demo_turbidity.py', 2)]:
            env = Hardware()
            module = env.load(name)
            self.assertAlmostEqual(module['decode_voltage'](b'\x20\x00'), 1.024)
            self.assertAlmostEqual(module['decode_voltage'](b'\xFF\xF0'), -0.002)
            self.assertEqual(module['decode_voltage'](b'\x00\x00'), 0)
            module['read_voltage'](env.modules['machine'].I2C(
                0, env.modules['machine'].Pin(5), env.modules['machine'].Pin(4), 100000))
            config = env.writes[0][1]
            value = (config[1] << 8) | config[2]
            self.assertEqual((value >> 9) & 7, 1)  # +/-4.096 V gain.
            self.assertEqual((value >> 12) & 7, 4 + channel)
            env.adc_data = b'\x7F\xF0'
            with self.assertRaisesRegex(ValueError, 'saturated'):
                module['read_voltage'](env.modules['machine'].I2C(
                    0, env.modules['machine'].Pin(5), env.modules['machine'].Pin(4), 100000))

    def test_analog_output_labels_and_baseline(self):
        for name in ('demo_ph.py', 'demo_tds.py'):
            _, output = Hardware().run(name)
            readings = [line for line in output.splitlines() if line.startswith('Voltage:')]
            self.assertGreaterEqual(len(readings), 2)
            self.assertTrue(all('UNCALIBRATED ESTIMATE' in line for line in readings))
        _, output = Hardware().run('demo_turbidity.py')
        self.assertEqual(output.count('baseline captured'), 1)
        self.assertIn('change from baseline: +0.000 V', output)

    def test_missing_devices_and_read_errors(self):
        names = ['demo_ph.py', 'demo_tds.py', 'demo_turbidity.py',
                 'demo_air_temperature_humidity.py', 'demo_water_temperature.py']
        for name in names:
            with self.subTest(name=name):
                env = Hardware()
                env.addresses = []
                env.roms = []
                _, output = env.run(name)
                self.assertIn('ERROR:', output)
                self.assertNotIn('Voltage:', output)
                env = Hardware()
                env.read_error = True
                _, output = env.run(name)
                self.assertIn('READ ERROR:', output)
                self.assertNotIn('baseline captured', output)

    def test_sht31_crc_rejects_corruption(self):
        env = Hardware()
        module = env.load('demo_air_temperature_humidity.py')
        self.assertEqual(module['crc8'](b'\xBE\xEF'), 0x92)
        env.air_data = b'\xBE\xEF\x00\xBE\xEF\x92'
        _, output = env.run('demo_air_temperature_humidity.py')
        self.assertIn('corrupt SHT31', output)
        self.assertNotIn('Air temperature:', output)

    def test_air_fan_thresholds_and_cleanup(self):
        for active_high in (True, False):
            env = Hardware(stop_ms=6000)
            readings = iter([26.0, 27.5, 28.0, 27.5, 27.0, 29.0])
            _, output = env.run('demo_air_temperature_humidity.py', {
                'FAN_ACTIVE_HIGH': active_high,
                'read_sensor': lambda i2c: (next(readings), 50.0),
            })
            on, off = (1, 0) if active_high else (0, 1)
            self.assertEqual([level for _, pin, level in env.output_events if pin == 19],
                             [off, off, off, on, on, off, on, off])
            self.assertIn('Fan: ON', output)

    def test_air_fan_turns_off_after_sensor_failure(self):
        env = Hardware(stop_ms=3000)
        readings = iter([(29.0, 50.0), OSError('Disconnected sensor'),
                         (27.5, 50.0)])

        def read_sensor(i2c):
            reading = next(readings)
            if isinstance(reading, Exception):
                raise reading
            return reading

        _, output = env.run('demo_air_temperature_humidity.py',
                            {'read_sensor': read_sensor})
        self.assertEqual([level for _, pin, level in env.output_events if pin == 19],
                         [0, 1, 0, 0, 0])
        self.assertIn('READ ERROR:', output)

    def test_flow_real_edges_atomic_snapshot_and_detachment(self):
        env = Hardware()
        module = env.load('demo_flow.py')
        for _ in range(7):
            module['pulse_handler'](None)
        self.assertEqual(module['take_pulses'](), 7)
        self.assertEqual(module['take_pulses'](), 0)
        self.assertFalse(env.locked)
        original_sleep = env.sleep_ms
        observed_triggers = []

        def inject_pulse(milliseconds):
            trigger, handler = env.irqs[2]
            observed_triggers.append(trigger)
            handler(None)
            original_sleep(milliseconds)

        env.modules['time'].sleep_ms = inject_pulse
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            module['main']()
        self.assertEqual(set(observed_triggers), {env.modules['machine'].Pin.IRQ_RISING})
        self.assertIn('interval: 1 | total: 2', output.getvalue())
        self.assertIsNone(env.irqs[2][1])
        _, output = Hardware().run('demo_flow.py')
        self.assertIn('expected with pump disconnected', output)
        self.assertNotIn('Real input pulses |', output)

    def test_water_fan_thresholds_and_polarity(self):
        for active_high in (True, False):
            env = Hardware(stop_ms=6000)
            readings = iter([25.0, 30.0, 31.0, 30.0, 26.0, 25.0])
            env.modules['ds18x20'].DS18X20.read_temp = lambda self, rom: next(readings)
            _, output = env.run('demo_water_temperature.py',
                                {'FAN_ACTIVE_HIGH': active_high})
            on, off = (1, 0) if active_high else (0, 1)
            self.assertEqual([level for _, pin, level in env.output_events if pin == 19],
                             [off, off, off, on, on, on, off, off])
            self.assertIn('Fan: ON', output)

    def test_water_fan_hottest_probe_and_interruption(self):
        env = Hardware(stop_ms=1000)
        env.roms = [b'hot', b'cool']
        env.modules['ds18x20'].DS18X20.read_temp = (
            lambda self, rom: 31.0 if rom == b'hot' else 20.0)
        env.run('demo_water_temperature.py')
        self.assertEqual([level for _, pin, level in env.output_events if pin == 19],
                         [0, 1, 0])

    def test_water_fan_sensor_failure_and_missing_probe(self):
        for failure in (OSError('Disconnected probe'), float('nan'), 126.0):
            env = Hardware(stop_ms=3000)
            readings = iter([31.0, failure, 29.0])

            def read_temp(self, rom):
                value = next(readings)
                if isinstance(value, Exception):
                    raise value
                return value

            env.modules['ds18x20'].DS18X20.read_temp = read_temp
            _, output = env.run('demo_water_temperature.py')
            self.assertEqual([level for _, pin, level in env.output_events if pin == 19],
                             [0, 1, 0, 0, 0])
            self.assertIn('READ ERROR:', output)
        env = Hardware()
        env.roms = []
        env.run('demo_water_temperature.py')
        self.assertEqual(env.levels[19], 0)

    def run_ph_readings(self, readings):
        env = Hardware(stop_ms=None)
        values = iter(list(readings) + [KeyboardInterrupt()])

        def read_voltage(i2c):
            value = next(values)
            if isinstance(value, BaseException):
                raise value
            return value

        module, output = env.run('demo_ph.py', {
            'read_voltage': read_voltage,
            'voltage_to_ph': lambda voltage: voltage,
        })
        return env, module, output

    def test_ph_servo_selection_and_rearming(self):
        env, module, output = self.run_ph_readings(
            [7.0, 7.0, 6.5, 5.0, 5.0, 5.5, 7.0])
        self.assertEqual([pwm.pin for pwm in env.pwms], [9, 8, 9])
        for pwm in env.pwms:
            self.assertEqual(pwm.duties[1:],
                             [module['angle_to_duty'](angle) for angle in (0, 45, 0)])
            self.assertTrue(pwm.released)
        self.assertTrue(all(level == 0 for level in env.levels.values()))
        self.assertIn('pH HIGH', output)
        self.assertIn('pH LOW', output)

    def test_ph_invalid_readings_do_not_move_or_rearm(self):
        failures = [OSError('Disconnected ADC'), float('nan'), -1.0, 15.0]
        env, _, output = self.run_ph_readings(failures + [5.5, 6.5])
        self.assertEqual(env.pwms, [])
        self.assertEqual(output.count('READ ERROR:'), 4)
        env, _, _ = self.run_ph_readings([7.0] + failures + [7.0, 5.0])
        self.assertEqual([pwm.pin for pwm in env.pwms], [9])

    def test_ph_movement_interruptions_and_errors(self):
        baseline = Hardware(stop_ms=None)
        module = baseline.load('demo_ph.py')
        with contextlib.redirect_stdout(io.StringIO()):
            module['move_servo'](9)
        for index in range(1, baseline.sleeps + 1):
            for error in (KeyboardInterrupt, OSError):
                with self.subTest(sleep=index, error=error):
                    env = Hardware(stop_ms=None, fail_sleep=index, failure=error)
                    module = env.load('demo_ph.py')
                    with contextlib.redirect_stdout(io.StringIO()):
                        with self.assertRaises(error):
                            module['move_servo'](9)
                    for pwm in env.pwms:
                        self.assertEqual(pwm.duties[-1], module['angle_to_duty'](0))
                        self.assertTrue(pwm.released)
                    self.assertTrue(all(level == 0 for level in env.levels.values()))

    def test_ph_invalid_settings_do_not_move(self):
        for overrides in ({'PH_MIN': 7.0}, {'SERVO_MAX_ANGLE': 181},
                          {'VOLTS_PER_PH': 0}, {'HOLD_SECONDS': 0}):
            env = Hardware()
            _, output = env.run('demo_ph.py', overrides)
            self.assertIn('DEMO ERROR:', output)
            self.assertEqual(env.pins, [])

    def test_actuator_sequences_and_cleanup(self):
        for name in ACTUATORS:
            with self.subTest(name=name):
                env = Hardware(stop_ms=None)
                module, _ = env.run(name)
                if 'servo' in name:
                    angles = [0, 45, 90, 45, 0, 0] if 'nutrient' in name else [0, 45, 0, 0]
                    self.assertEqual(env.pwms[0].duties[1:],
                                     [module['angle_to_duty'](angle) for angle in angles])
                elif name == 'demo_fan.py':
                    self.assertEqual(env.output_events, [(0, 19, 0), (3000, 19, 1),
                                                         (8000, 19, 0)])
                else:
                    expected_colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255),
                                       (255, 120, 0), (0, 0, 0)]
                    for channel, pwm in enumerate(env.pwms):
                        self.assertEqual(pwm.duties[1:-1], [int(color[channel] * 65535 / 255)
                                                           for color in expected_colors])
                    self.assertEqual(env.now, 18000)
                self.assert_clean(env, module, name)

    def assert_clean(self, env, module, name):
        self.assertTrue(all(pwm.released for pwm in env.pwms))
        self.assertTrue(all(level == 0 for level in env.levels.values()))
        if 'servo' in name and env.pwms:
            self.assertEqual(env.pwms[0].duties[-1], module['angle_to_duty'](0))
        if name == 'demo_rgb_led.py':
            self.assertTrue(all(pwm.duties[-1] == 0 for pwm in env.pwms))

    def test_actuator_interruptions_and_errors(self):
        for name in ACTUATORS:
            baseline = Hardware(stop_ms=None)
            baseline.run(name)
            for index in range(1, baseline.sleeps + 1):
                for error in (KeyboardInterrupt, OSError):
                    with self.subTest(name=name, sleep=index, error=error):
                        env = Hardware(stop_ms=None, fail_sleep=index, failure=error)
                        module = env.load(name)
                        with contextlib.redirect_stdout(io.StringIO()):
                            try:
                                module['main']()
                            except (KeyboardInterrupt, OSError):
                                # A failure during cleanup may propagate, but must release PWM.
                                pass
                        self.assert_clean(env, module, name)

    def test_alternate_output_polarities(self):
        env = Hardware(stop_ms=None)
        env.run('demo_fan.py', {'FAN_ACTIVE_HIGH': False})
        self.assertEqual(env.levels[19], 1)
        env = Hardware(stop_ms=None)
        env.run('demo_rgb_led.py', {'RGB_COMMON_ANODE': True})
        self.assertTrue(all(level == 1 for level in env.levels.values()))
        self.assertTrue(all(pwm.duties[-1] == 65535 for pwm in env.pwms))

    def test_servo_invalid_configuration_never_moves(self):
        env = Hardware(stop_ms=None)
        _, output = env.run('demo_acid_servo.py', {'SERVO_MAX_ANGLE': 200})
        self.assertIn('DEMO ERROR:', output)
        self.assertEqual(env.pins, [])

    def test_button_debounce(self):
        _, output = Hardware(stop_ms=500).run('demo_stop_button.py')
        self.assertEqual(output.count('Button PRESSED'), 1)
        self.assertEqual(output.count('Button RELEASED'), 2)  # Initial plus release.


if __name__ == '__main__':
    unittest.main()
