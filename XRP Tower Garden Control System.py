# XRP Tower Garden Control System
# Chloroplasters - EcoSmart Circular Tower Garden

from xrp import *
import time


# PIN SETUP - (Adjust)


# Sensors (analog/digital inputs)
SOIL_MOISTURE_PIN = 0      # Capacitive soil moisture sensor
PH_SENSOR_PIN = 1          # pH sensor (analog)
EC_SENSOR_PIN = 2          # Conductivity sensor (analog)
TURBIDITY_SENSOR_PIN = 3   # Turbidity sensor (analog)
WATER_TEMP_PIN = 4         # Water temperature sensor
FLOW_SENSOR_PIN = 5        # Flow sensor (digital or analog)
HUMIDITY_SENSOR_PIN = 6    # Humidity sensor (for tank empty check)

# Outputs (pumps, lights, fan)
WATER_PUMP_PIN = 0         # Main irrigation pump
PH_PUMP_ACID_PIN = 1       # Pump for citric acid (pH too high)
PH_PUMP_BASE_PIN = 2       # Pump for potassium bicarbonate (pH too low)
NUTRIENT_PUMP_PIN = 3      # Pump for nutrient solution
FRESH_WATER_PUMP_PIN = 4   # Pump for fresh water (dilution)
FAN_PIN = 5                # Cooling fan for water
RED_LIGHT_PIN = 6          # Red LED - tank empty warning
ORANGE_LIGHT_PIN = 7       # Orange LED - replace water warning

# Button to stop the system
STOP_BUTTON_PIN = 8

# THRESHOLD VALUES - From  flowcharts


MOISTURE_MIN = 35          # % - turn pump ON below this
MOISTURE_TARGET = 60       # % - turn pump OFF at this
PH_MIN = 5.5               # pH too low
PH_MAX = 6.5               # pH too high
EC_MIN = 1.0               # mS/cm - too little nutrients
EC_MAX = 2.0               # mS/cm - too many nutrients
TURBIDITY_MAX = 30         # NTU - water too dirty
WATER_TEMP_MAX = 30        # °C - turn fan ON
WATER_TEMP_MIN = 26        # °C - turn fan OFF

# HELPER FUNCTIONS - Simple sensor reading


def read_sensor(pin):
    """Read analog sensor value (0-1023)"""
    return analogRead(pin)

def read_digital(pin):
    """Read digital sensor value"""
    return digitalRead(pin)

def is_button_pressed():
    """Check if stop button is pressed"""
    return read_digital(STOP_BUTTON_PIN) == 1

def set_output(pin, state):
    """Turn output pin ON (1) or OFF (0)"""
    digitalWrite(pin, state)

# ============================================
# SENSOR READING FUNCTIONS
# ============================================

def get_moisture():
    """Read soil moisture percentage"""
    raw = read_sensor(SOIL_MOISTURE_PIN)
    # Convert to percentage (calibrate these values!)
    # Usually 0 = wet, 1023 = dry for capacitive sensors
    # So we invert: higher number = more moisture
    percent = 100 - (raw / 1023 * 100)
    return percent

def get_ph():
    """Read pH value from sensor"""
    raw = read_sensor(PH_SENSOR_PIN)
    # Convert raw reading to pH (calibrate this!)
    # pH sensors usually output voltage proportional to pH
    # Typical: pH 7 = ~2.5V, pH 0-14 maps to 0-5V
    voltage = raw / 1023 * 3.3  # XRP uses 3.3V
    ph = 7 + (2.5 - voltage) * 3.5  # Adjust formula based on your sensor
    return ph

def get_ec():
    """Read electrical conductivity in mS/cm"""
    raw = read_sensor(EC_SENSOR_PIN)
    # Convert to EC value (calibrate this!)
    # Formula depends on your specific sensor
    voltage = raw / 1023 * 3.3
    ec = voltage * 2  # Example conversion - adjust!
    return ec

def get_turbidity():
    """Read turbidity in NTU"""
    raw = read_sensor(TURBIDITY_SENSOR_PIN)
    # Higher raw usually means clearer water (lower turbidity)
    # Calibrate: clear water = ~0 NTU, dirty = higher
    voltage = raw / 1023 * 3.3
    # Typical formula: NTU decreases as voltage increases
    ntu = 3000 / voltage  # Example - adjust based on sensor specs!
    return ntu

def get_water_temp():
    """Read water temperature in Celsius"""
    raw = read_sensor(WATER_TEMP_PIN)
    # Convert to temperature (calibrate!)
    # For LM35: 10mV per degree
    voltage = raw / 1023 * 3.3
    temp = voltage * 100  # For LM35 sensor
    return temp

def get_flow():
    """Read water flow rate"""
    # Could be digital (flow present/absent) or analog
    raw = read_sensor(FLOW_SENSOR_PIN)
    # If using simple flow switch: 0 = no flow, >0 = flow
    return raw

def get_humidity():
    """Read humidity in tank area"""
    raw = read_sensor(HUMIDITY_SENSOR_PIN)
    # Convert to percentage
    percent = raw / 1023 * 100
    return percent

# ============================================
# HOMESTASIS FUNCTIONS - From your flowcharts
# ============================================

def ph_homeostasis():
    """
    Flowchart page 38: pH homeostasis
    - If pH > 6.5: add citric acid (make more acidic)
    - If pH < 5.5: add potassium bicarbonate (make more basic)
    """
    ph = get_ph()
    print("pH level:", ph)
    
    if ph > PH_MAX:
        print("pH too HIGH - adding citric acid")
        # Dose citric acid for 1-3 seconds
        set_output(PH_PUMP_ACID_PIN, 1)
        time.sleep(2)  # 2 seconds dosing
        set_output(PH_PUMP_ACID_PIN, 0)
        print("Citric acid added")
        
    elif ph < PH_MIN:
        print("pH too LOW - adding potassium bicarbonate")
        # Dose potassium bicarbonate
        set_output(PH_PUMP_BASE_PIN, 1)
        time.sleep(2)  # 2 seconds dosing
        set_output(PH_PUMP_BASE_PIN, 0)
        print("Potassium bicarbonate added")
        
    else:
        print("pH is OK (5.5 - 6.5)")

def conductivity_homeostasis():
    """
    Flowchart page 38: EC homeostasis
    - If EC < 1: add nutrient solution
    - If EC > 2: add fresh water (dilute)
    """
    ec = get_ec()
    print("EC level:", ec, "mS/cm")
    
    if ec < EC_MIN:
        print("EC too LOW - adding nutrient solution")
        set_output(NUTRIENT_PUMP_PIN, 1)
        time.sleep(3)  # Add nutrients
        set_output(NUTRIENT_PUMP_PIN, 0)
        print("Nutrients added")
        
    elif ec > EC_MAX:
        print("EC too HIGH - adding fresh water to dilute")
        set_output(FRESH_WATER_PUMP_PIN, 1)
        time.sleep(5)  # Add fresh water
        set_output(FRESH_WATER_PUMP_PIN, 0)
        print("Fresh water added")
        
    else:
        print("EC is OK (1.0 - 2.0 mS/cm)")

def turbidity_homeostasis():
    """
    Flowchart page 39: Turbidity homeostasis
    - If turbidity > 30 NTU: turn on orange light to warn students
    """
    turbidity = get_turbidity()
    print("Turbidity:", turbidity, "NTU")
    
    if turbidity > TURBIDITY_MAX:
        print("Water is DIRTY - turn on ORANGE warning light")
        set_output(ORANGE_LIGHT_PIN, 1)
        # Keep light on until water is changed (manual reset)
    else:
        print("Water clarity is OK")
        set_output(ORANGE_LIGHT_PIN, 0)

def flow_homeostasis():
    """
    Flowchart page 39: Flow homeostasis
    - If flow = 0: check if humidity = 0% (tank empty) or pump problem
    - If tank empty: red light warning
    - If pump problem: attempt restart
    """
    flow = get_flow()
    print("Flow rate:", flow)
    
    if flow == 0:
        print("NO WATER FLOW detected!")
        humidity = get_humidity()
        print("Tank humidity:", humidity, "%")
        
        if humidity == 0 or humidity < 5:
            # Tank is empty - need to add water
            print("TANK IS EMPTY - turn on RED warning light")
            set_output(RED_LIGHT_PIN, 1)
            # Light stays on until water is added
            
        else:
            # Tank has water but pump not working
            print("Pump may be broken - attempting restart")
            set_output(WATER_PUMP_PIN, 0)  # Turn off first
            time.sleep(2)
            set_output(WATER_PUMP_PIN, 1)  # Turn back on
            time.sleep(3)
            
            # Check if flow restored
            new_flow = get_flow()
            if new_flow > 0:
                print("Pump restart SUCCESSFUL")
                set_output(RED_LIGHT_PIN, 0)
            else:
                print("Pump restart FAILED - needs manual check")
                set_output(RED_LIGHT_PIN, 1)  # Also red light for pump failure

def watertemp_homeostasis():
    """
    Flowchart page 40: Water temperature homeostasis
    - If temp > 30°C: activate fan
    - If temp < 26°C: close fan
    """
    temp = get_water_temp()
    print("Water temperature:", temp, "°C")
    
    if temp > WATER_TEMP_MAX:
        print("Water too HOT - activating cooling fan")
        set_output(FAN_PIN, 1)
        
    elif temp < WATER_TEMP_MIN:
        print("Water cooled down - turning off fan")
        set_output(FAN_PIN, 0)
        
    else:
        print("Water temperature is OK")

# ============================================
# MAIN IRRIGATION FUNCTION
# ============================================

def check_and_water():
    """
    Main irrigation control from page 25
    - If moisture < 35%: turn pump ON
    - If moisture >= 60%: turn pump OFF
    """
    moisture = get_moisture()
    print("Soil moisture:", moisture, "%")
    
    if moisture < MOISTURE_MIN:
        print("Soil too DRY - starting water pump")
        set_output(WATER_PUMP_PIN, 1)
        
    elif moisture >= MOISTURE_TARGET:
        print("Soil moist enough - stopping water pump")
        set_output(WATER_PUMP_PIN, 0)

# ============================================
# MAIN PROGRAM - Matches flowchart page 36
# ============================================

def main():
    """
    Main loop following the flowchart exactly:
    1. Check if button pressed (stop)
    2. If not, read all sensors
    3. Check each parameter and call homeostasis if needed
    4. Continue monitoring
    """
    print("=" * 40)
    print("Chloroplasters Tower Garden Starting...")
    print("=" * 40)
    
    # Initialize all outputs to OFF
    set_output(WATER_PUMP_PIN, 0)
    set_output(PH_PUMP_ACID_PIN, 0)
    set_output(PH_PUMP_BASE_PIN, 0)
    set_output(NUTRIENT_PUMP_PIN, 0)
    set_output(FRESH_WATER_PUMP_PIN, 0)
    set_output(FAN_PIN, 0)
    set_output(RED_LIGHT_PIN, 0)
    set_output(ORANGE_LIGHT_PIN, 0)
    
    time.sleep(2)  # Startup delay
    
    while True:
        print("\n" + "=" * 40)
        print("New monitoring cycle")
        print("=" * 40)
        
        # STEP 1: Check if stop button pressed (Page 36)
        if is_button_pressed():
            print("STOP BUTTON PRESSED - Shutting down system")
            # Turn everything off safely
            set_output(WATER_PUMP_PIN, 0)
            set_output(FAN_PIN, 0)
            break  # Exit the loop
        
        # STEP 2: Read inputs from sensors (Page 36)
        print("\n--- Reading Sensors ---")
        
        # Always check irrigation first
        check_and_water()
        
        # STEP 3: Check pH (Page 36 diamond: pH < 5.5 OR pH > 6.5)
        ph = get_ph()
        if ph < PH_MIN or ph > PH_MAX:
            print("pH out of range! Calling ph_homeostasis()")
            ph_homeostasis()
        else:
            print("pH is within range (5.5 - 6.5)")
        
        # STEP 4: Check EC (Page 36 diamond: EC < 1 OR EC > 2)
        ec = get_ec()
        if ec < EC_MIN or ec > EC_MAX:
            print("EC out of range! Calling conductivity_homeostasis()")
            conductivity_homeostasis()
        else:
            print("EC is within range (1.0 - 2.0 mS/cm)")
        
        # STEP 5: Check Turbidity (Page 36 diamond: Turbidity > 30)
        turbidity = get_turbidity()
        if turbidity > TURBIDITY_MAX:
            print("Turbidity too high! Calling turbidity_homeostasis()")
            turbidity_homeostasis()
        else:
            print("Turbidity is OK (< 30 NTU)")
            set_output(ORANGE_LIGHT_PIN, 0)  # Ensure orange light is off
        
        # STEP 6: Check Water Temperature (Page 37 diamond: Water temp > 26)
        temp = get_water_temp()
        if temp > WATER_TEMP_MAX:
            print("Water too hot! Calling watertemp_homeostasis()")
            watertemp_homeostasis()
        else:
            print("Water temperature OK or fan already handled")
            # Check if we need to turn fan off
            if temp < WATER_TEMP_MIN:
                set_output(FAN_PIN, 0)
        
        # STEP 7: Check Flow (Page 37 diamond: Flow = 0)
        flow = get_flow()
        if flow == 0:
            print("No flow detected! Calling flow_homeostasis()")
            flow_homeostasis()
        else:
            print("Water flow is OK")
            set_output(RED_LIGHT_PIN, 0)  # Ensure red light is off if flow OK
        
        # STEP 8: Continue monitoring (Page 36)
        print("\n--- Cycle complete. Waiting before next check ---")
        time.sleep(10)  # Wait 10 seconds between cycles
    
    print("System stopped. Goodbye!")

# ============================================
# START THE PROGRAM
# ============================================

# Run the main function
main()