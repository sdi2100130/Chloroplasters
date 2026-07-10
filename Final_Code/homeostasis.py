# =========================================================
# Chloroplasters - Homeostasis mechanisms
# =========================================================

import time

last_water_time      = 0
is_watering          = False
watering_start_time  = 0
flow_pulse_count     = 0
last_pulse_seen_time = 0
no_flow_alarm        = False
dirty_water_alarm    = False
combined_warning_blue = True
current_irrigation_interval = 1800
current_water_target_pulses = 0

last_ph_dose_time = 0
last_ec_dose_time = 0


def reset_state():
    """Reset watering and warning state after entering safe/off mode."""
    global is_watering, no_flow_alarm, dirty_water_alarm, combined_warning_blue
    is_watering = False
    no_flow_alarm = False
    dirty_water_alarm = False
    combined_warning_blue = True


def set_last_water_time(value):
    """Set the irrigation timer reference."""
    global last_water_time
    last_water_time = value


def record_flow_pulse():
    """Record one pulse from the flow sensor interrupt."""
    global flow_pulse_count, last_pulse_seen_time
    flow_pulse_count += 1
    last_pulse_seen_time = time.time()


def update_status_light(controls):
    """Show normal, warning, or combined warning state on the RGB LED."""
    global combined_warning_blue
    if no_flow_alarm and dirty_water_alarm:
        if combined_warning_blue:
            controls["show_no_flow_state"]()
        else:
            controls["show_dirty_water_state"]()
        combined_warning_blue = not combined_warning_blue
    elif no_flow_alarm:
        combined_warning_blue = True
        controls["show_no_flow_state"]()
    elif dirty_water_alarm:
        combined_warning_blue = True
        controls["show_dirty_water_state"]()
    else:
        combined_warning_blue = True
        controls["show_normal_state"]()


def ph_homeostasis(readings, controls, config):
    """Maintain pH between PH_MIN and PH_MAX."""
    global last_ph_dose_time
    ph = readings["ph"]
    print("pH level:", ph)
    if ph == -999:
        return
    if time.time() - last_ph_dose_time < config["DOSE_MIXING_WAIT"]:
        return
    if ph > config["PH_MAX"]:
        print(">>> pH HIGH - dosing citric acid")
        controls["push_syringe"](config["PH_ACID_SERVO_PIN"])
        last_ph_dose_time = time.time()
    elif ph < config["PH_MIN"]:
        print(">>> pH LOW - dosing potassium bicarbonate")
        controls["push_syringe"](config["PH_BASE_SERVO_PIN"])
        last_ph_dose_time = time.time()


def conductivity_homeostasis(readings, controls, config):
    """Maintain EC between EC_MIN and EC_MAX."""
    global last_ec_dose_time
    ec = readings["ec"]
    print("EC level:", ec, "mS/cm")
    if ec == -999:
        return
    if time.time() - last_ec_dose_time < config["DOSE_MIXING_WAIT"]:
        return
    if ec < config["EC_MIN"]:
        print(">>> EC LOW - lowering nutrient straw")
        controls["feed_nutrients_with_straw"](config["NUTRIENT_SERVO_PIN"])
        last_ec_dose_time = time.time()
    elif ec > config["EC_MAX"]:
        if not config["FRESH_WATER_PUMP_ENABLED"]:
            print(">>> EC HIGH - fresh water pump disabled")
            last_ec_dose_time = time.time()
            return
        print(">>> EC HIGH - adding fresh water")
        controls["set_output"](config["FRESH_WATER_PUMP_PIN"], 1)
        time.sleep(5)
        controls["set_output"](config["FRESH_WATER_PUMP_PIN"], 0)
        last_ec_dose_time = time.time()


def turbidity_check(readings, controls, config):
    """Set orange warning LED if water is too cloudy."""
    global dirty_water_alarm
    ntu = readings["turbidity"]
    if ntu == -999:
        update_status_light(controls)
        return
    if ntu > config["TURBIDITY_MAX"]:
        dirty_water_alarm = True
        print(">>> Water cloudy:", ntu, "NTU")
    else:
        dirty_water_alarm = False
    update_status_light(controls)


def temperature_protection(readings, controls, config):
    """Switch fan based on water temperature."""
    water_temp = readings["water_temp"]
    if water_temp == -999:
        return
    if water_temp > config["WATER_TEMP_MAX"]:
        controls["set_output"](config["FAN_PIN"], 1)
        print(">>> Water hot (", water_temp, "C) - fan ON")
    elif water_temp < config["WATER_TEMP_MIN"]:
        controls["set_output"](config["FAN_PIN"], 0)


def adjust_watering_by_weather(readings, config):
    """Calculate interval and target volume from room conditions."""
    air_temp = readings["air_temp"]
    air_hum = readings["air_humidity"]
    if air_temp is None or air_hum is None:
        return (
            1800,
            int(config["WATER_TARGET_NORMAL"] * config["PULSES_PER_LITER"]),
        )
    print("[Weather] Air:", air_temp, "C,", air_hum, "%")
    if air_temp > 28 or air_hum < 40:  # TRIAL-AND-ERROR: tune hot/dry trigger from room tests.
        target_pulses = int(config["WATER_TARGET_HOT"] * config["PULSES_PER_LITER"])
        print("[Weather] HOT/DRY -> 15 min, target", config["WATER_TARGET_HOT"], "L")
        return (900, target_pulses)  # TRIAL-AND-ERROR: tune hot/dry watering interval.
    if air_temp < 18 or air_hum > 75:  # TRIAL-AND-ERROR: tune cold/humid trigger from room tests.
        target_pulses = int(config["WATER_TARGET_COLD"] * config["PULSES_PER_LITER"])
        print("[Weather] COLD/HUMID -> 45 min, target", config["WATER_TARGET_COLD"], "L")
        return (2700, target_pulses)  # TRIAL-AND-ERROR: tune cold/humid watering interval.
    target_pulses = int(config["WATER_TARGET_NORMAL"] * config["PULSES_PER_LITER"])
    print("[Weather] NORMAL -> 30 min, target", config["WATER_TARGET_NORMAL"], "L")
    return (1800, target_pulses)  # TRIAL-AND-ERROR: tune normal watering interval.


def check_and_water(readings, controls, config):
    """Flow-based irrigation: pump until target liters delivered or safety triggers."""
    global last_water_time, is_watering, watering_start_time, no_flow_alarm
    global flow_pulse_count, last_pulse_seen_time
    global current_irrigation_interval, current_water_target_pulses
    current_time = time.time()

    if not is_watering:
        current_irrigation_interval, current_water_target_pulses = (
            adjust_watering_by_weather(readings, config)
        )
        if current_time - last_water_time >= current_irrigation_interval:
            print("-> Starting pump. Target:", current_water_target_pulses, "pulses")
            flow_pulse_count = 0
            watering_start_time = current_time
            last_pulse_seen_time = current_time
            no_flow_alarm = False
            update_status_light(controls)
            controls["set_output"](config["WATER_PUMP_PIN"], 1)
            is_watering = True
        else:
            time_left = current_irrigation_interval - (current_time - last_water_time)
            print("-> Next watering in", int(time_left / 60), "min")
        return None

    liters_so_far = flow_pulse_count / config["PULSES_PER_LITER"]
    elapsed = current_time - watering_start_time
    print("-> Watering:", flow_pulse_count, "pulses (", round(liters_so_far, 2),
          "L) in", int(elapsed), "s")

    if flow_pulse_count >= current_water_target_pulses:
        print("-> Target reached. Stopping pump.")
        controls["set_output"](config["WATER_PUMP_PIN"], 0)
        no_flow_alarm = False
        update_status_light(controls)
        is_watering = False
        last_water_time = current_time
        return None

    if current_time - last_pulse_seen_time > config["NO_FLOW_TIMEOUT"]:
        print("!!! NO FLOW for", config["NO_FLOW_TIMEOUT"], "s - entering safe state!")
        controls["set_output"](config["WATER_PUMP_PIN"], 0)
        no_flow_alarm = True
        controls["show_safe_state"]()
        is_watering = False
        last_water_time = current_time
        return controls["safe_state"]

    if elapsed > config["PUMP_TIMEOUT_SECONDS"]:
        print("!!! Pump timeout exceeded - entering safe state!")
        controls["set_output"](config["WATER_PUMP_PIN"], 0)
        controls["show_safe_state"]()
        is_watering = False
        last_water_time = current_time
        return controls["safe_state"]

    return None


def homeostasis(readings, controls, config):
    """Run one normal-control cycle and return a next state if safety triggers."""
    next_state = check_and_water(readings, controls, config)
    if next_state is not None:
        return next_state

    ph_homeostasis(readings, controls, config)
    conductivity_homeostasis(readings, controls, config)
    turbidity_check(readings, controls, config)
    temperature_protection(readings, controls, config)
    return None
