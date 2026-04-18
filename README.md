# Chloroplasters
Code for the tower garden

from xrp import *
import time

# SETUP

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

