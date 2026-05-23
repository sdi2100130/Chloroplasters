# XRP Tower Garden Control System
# Chloroplasters

from machine import Pin, I2C, PWM
import time
import onewire
import ds18x20

# ============================================
# 1. PIN SETUP - Ρυθμίσεις Θυρών
# ============================================

# --- I2C bus configuration (Για ADS1015 και SHT31) ---
I2C_SDA_PIN = 4    # IO4 -> Qwiic 0 SDA
I2C_SCL_PIN = 5    # IO5 -> Qwiic 0 SCL
ADS1015_ADDR = 0x48   
SHT31_ADDR   = 0x44   

# --- Analog sensor channels on ADS1015 (Κανάλια Αναλογικών Αισθητήρων) ---
PH_CHANNEL            = 0    # A0 -> pH sensor
EC_CHANNEL            = 1    # A1 -> TDS Sensor 
TURBIDITY_CHANNEL     = 2    # A2 -> Turbidity

# --- Digital sensors (Ψηφιακοί Αισθητήρες) ---
FLOW_SENSOR_PIN = 2    # IO2 -> Flow sensor 
WATER_TEMP_PIN  = 20   # IO20 -> DS18B20 αδιάβροχος αισθητήρας (Με 4.7kΩ αντίσταση!)

# --- Outputs: SERVOS for Syringe Pumps (Σερβοκινητήρες Σύριγγας) ---
PH_ACID_SERVO_PIN  = 6    # IO6  (Servo 1) -> Κιτρικό Οξύ (pH down)
PH_BASE_SERVO_PIN  = 7    # IO7  (Servo 3) -> Διττανθρακικό (pH up)
NUTRIENT_SERVO_PIN = 8   # IO8 (Servo 4) -> Θρεπτικό (EC up)

# --- Outputs: PUMPS & FAN (Αντλίες Νερού και Ανεμιστήρας) ---
WATER_PUMP_PIN       = 12   # IO12 -> Relay 1 (Κεντρική αντλία)
FRESH_WATER_PUMP_PIN = 18   # IO18 -> Relay 2 (Αντλία καθαρού νερού)
FAN_PIN              = 19   # IO19 -> Relay 3 (Ανεμιστήρας)

# --- Outputs: LEDs ---
RED_LIGHT_PIN    = 22   # IO22 -> Red LED (Πρόβλημα!)
ORANGE_LIGHT_PIN = 23   # IO23 -> Orange LED (Βρώμικο νερό)

# --- Stop button ---
STOP_BUTTON_PIN = 36    # IO16 -> USER button

# =========================================================
# 2. THRESHOLD VALUES - Όρια Λειτουργίας
# =========================================================

PH_MIN            = 5.5    # pH - Πολύ χαμηλό (Χρειάζεται Base)
PH_MAX            = 6.5    # pH - Πολύ υψηλό (Χρειάζεται Acid)
EC_MIN            = 1.0    # mS/cm - Λίγα θρεπτικά
EC_MAX            = 2.0    # mS/cm - Πολλά θρεπτικά
TURBIDITY_MAX     = 30     # NTU - Πολύ βρώμικο
WATER_TEMP_MAX    = 30     # °C - Άναψε ανεμιστήρα
WATER_TEMP_MIN    = 26     # °C - Σβήσε ανεμιστήρα
TANK_HUMIDITY_MIN = 5      # % - Άδεια δεξαμενή

# --- Πότισμα με βάση τη ροή νερού (αντί για χρόνο) ---
# Ο YF-S201 δίνει περίπου 450 παλμούς ανά λίτρο νερού
PULSES_PER_LITER = 450

# Στόχοι ποσότητας ανάλογα με τις συνθήκες (σε λίτρα)
WATER_TARGET_HOT    = 2.5   # Ζεστή/Ξηρή ημέρα -> πιο πολύ νερό
WATER_TARGET_NORMAL = 2.0   # Κανονική ημέρα
WATER_TARGET_COLD   = 1.5   # Κρύα/Υγρή ημέρα -> λιγότερο νερό

# Ξεκινάει με κανονικό στόχο
WATER_TARGET_PULSES = int(WATER_TARGET_NORMAL * PULSES_PER_LITER)

# Διαστήματα μεταξύ ποτισμάτων (σε δευτερόλεπτα)
IRRIGATION_INTERVAL = 1800  # Ξεκινάει με 30 λεπτά

# Ασφάλεια: μέγιστος χρόνος που μπορεί να τρέχει η αντλία
PUMP_TIMEOUT_SECONDS = 300   # 5 λεπτά μέγιστο
# Αν δεν περάσει νερό σε αυτό το χρόνο, υπάρχει πρόβλημα
NO_FLOW_TIMEOUT      = 60    # 1 λεπτό χωρίς ροή = πρόβλημα

# Μεταβλητές ελέγχου
last_water_time = 0
is_watering = False
watering_start_time = 0       # Πότε ξεκίνησε η τρέχουσα άρδευση
pulses_this_watering = 0      # Παλμοί που μετρήθηκαν σε αυτή την άρδευση
last_pulse_seen_time = 0      # Πότε εμφανίστηκε ο τελευταίος παλμός

# =========================================================
# 3. INITIALIZATION - Αρχικοποίηση Επικοινωνίας
# =========================================================

# I2C (Για ADS1015 και SHT31)
i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)

# OneWire & DS18B20 (Για τον αδιάβροχο αισθητήρα νερού)
ds_pin = Pin(WATER_TEMP_PIN)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
roms = ds_sensor.scan()
if not roms:
    print("ΠΡΟΣΟΧΗ: Δεν βρέθηκε ο αισθητήρας DS18B20! Ελέγξτε την αντίσταση 4.7kΩ.")

# --- Flow sensor με interrupt για μέτρηση παλμών ---
flow_pulse_count = 0

def flow_pulse_handler(pin):
    """Καλείται αυτόματα σε κάθε παλμό του αισθητήρα ροής."""
    global flow_pulse_count, last_pulse_seen_time
    flow_pulse_count += 1
    last_pulse_seen_time = time.time()

flow_pin = Pin(FLOW_SENSOR_PIN, Pin.IN, Pin.PULL_UP)
flow_pin.irq(trigger=Pin.IRQ_RISING, handler=flow_pulse_handler)

# =========================================================
# 4. SERVO CONTROL FUNCTIONS - Έλεγχος Σύριγγας
# =========================================================

SERVO_1ML_ANGLE = 20  # ΑΛΛΑΞΤΕ ΑΥΤΟ ΤΟ ΝΟΥΜΕΡΟ ΜΕΤΑ ΤΗ ΒΑΘΜΟΝΟΜΗΣΗ

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

# =========================================================
# 5. ADS1015 & SENSORS FUNCTIONS
# =========================================================

ADS1015_REG_CONVERSION = 0x00
ADS1015_REG_CONFIG     = 0x01
ADS1015_CONFIG_BASE = 0x8583
ADS1015_MUX = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}

def ads1015_read_channel(channel):
    if channel not in ADS1015_MUX: return None
    try:
        config = ADS1015_CONFIG_BASE | ADS1015_MUX[channel]
        config_bytes = bytes([ADS1015_REG_CONFIG, (config >> 8) & 0xFF, config & 0xFF])
        i2c.writeto(ADS1015_ADDR, config_bytes)
        time.sleep(0.005)
        i2c.writeto(ADS1015_ADDR, bytes([ADS1015_REG_CONVERSION]))
        data = i2c.readfrom(ADS1015_ADDR, 2)
        raw = (data[0] << 8) | data[1]
        raw = raw >> 4 
        if raw > 2047: raw = raw - 4096
        return raw * 4.096 / 2048
    except Exception as e:
        print("ADS1015 error:", e)
        return None

def get_water_temp():
    if not roms: return -999
    try:
        ds_sensor.convert_temp()
        time.sleep_ms(750)
        return ds_sensor.read_temp(roms[0])
    except:
        return -999

def get_ph():
    voltage = ads1015_read_channel(PH_CHANNEL)
    if voltage is None: return -999
    return 7 + (2.5 - voltage) / 0.18 

def get_ec():
    voltage = ads1015_read_channel(EC_CHANNEL)
    if voltage is None: return -999
    return voltage * 2.0 

def get_turbidity():
    voltage = ads1015_read_channel(TURBIDITY_CHANNEL)
    if voltage is None: return -999
    actual_voltage = voltage * 1.5 
    if actual_voltage < 0.1: return 3000 
    return 3000 / actual_voltage 

def read_sht31():
    try:
        i2c.writeto(SHT31_ADDR, b'\x24\x00')
        time.sleep(0.02)
        data = i2c.readfrom(SHT31_ADDR, 6)
        temp_raw = (data[0] << 8) | data[1]
        hum_raw  = (data[3] << 8) | data[4]
        temperature = -45 + (175 * temp_raw / 65535)
        humidity    = 100 * hum_raw / 65535
        return (temperature, humidity)
    except Exception as e:
        print("SHT31 read error:", e)
        return (None, None)

# =========================================================
# 6. HELPER FUNCTIONS
# =========================================================

def is_button_pressed():
    p = Pin(STOP_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    return p.value() == 0

def set_output(pin_num, state):
    p = Pin(pin_num, Pin.OUT)
    p.value(state)

# =========================================================
# 7. HOMEOSTASIS FUNCTIONS
# =========================================================

def ph_homeostasis():
    ph = get_ph()
    print("pH level:", ph)
    if ph == -999: return

    if ph > PH_MAX:
        print("pH too HIGH - Pushing Citric Acid Syringe")
        push_syringe(PH_ACID_SERVO_PIN)
    elif ph < PH_MIN:
        print("pH too LOW - Pushing Potassium Bicarbonate Syringe")
        push_syringe(PH_BASE_SERVO_PIN)

def conductivity_homeostasis():
    ec = get_ec()
    print("EC level:", ec, "mS/cm")
    if ec == -999: return

    if ec < EC_MIN:
        print("EC too LOW - Pushing Nutrient Syringe")
        push_syringe(NUTRIENT_SERVO_PIN)
    elif ec > EC_MAX:
        print("EC too HIGH - Adding fresh water")
        set_output(FRESH_WATER_PUMP_PIN, 1)
        time.sleep(5)
        set_output(FRESH_WATER_PUMP_PIN, 0)

def adjust_watering_by_weather():
    """
    Διαβάζει τον SHT31 και προσαρμόζει ΚΑΙ το διάστημα ΚΑΙ την ποσότητα 
    νερού του ποτίσματος ανάλογα με τις συνθήκες.
    """
    global IRRIGATION_INTERVAL, WATER_TARGET_PULSES
    
    air_temp, air_hum = read_sht31()
    
    if air_temp is None or air_hum is None:
        # Ασφαλείς default τιμές
        IRRIGATION_INTERVAL = 1800
        WATER_TARGET_PULSES = int(WATER_TARGET_NORMAL * PULSES_PER_LITER)
        return

    print("[Smart Weather] Αέρας:", air_temp, "°C, Υγρασία:", air_hum, "%")

    # ΣΕΝΑΡΙΟ 1: Ζεστό/Ξηρό -> πιο συχνά ΚΑΙ πιο πολύ νερό
    if air_temp > 28 or air_hum < 40:
        IRRIGATION_INTERVAL = 900   # 15 λεπτά
        WATER_TARGET_PULSES = int(WATER_TARGET_HOT * PULSES_PER_LITER)
        print("[Smart Weather] ΖΕΣΤΗ/ΞΗΡΗ -> 15 λεπτά, στόχος", WATER_TARGET_HOT, "L")
        
    # ΣΕΝΑΡΙΟ 2: Κρύο/Υγρό -> πιο αραιά ΚΑΙ λιγότερο νερό
    elif air_temp < 18 or air_hum > 75:
        IRRIGATION_INTERVAL = 2700  # 45 λεπτά
        WATER_TARGET_PULSES = int(WATER_TARGET_COLD * PULSES_PER_LITER)
        print("[Smart Weather] ΚΡΥΑ/ΥΓΡΗ -> 45 λεπτά, στόχος", WATER_TARGET_COLD, "L")
        
    # ΣΕΝΑΡΙΟ 3: Κανονικές συνθήκες
    else:
        IRRIGATION_INTERVAL = 1800  # 30 λεπτά
        WATER_TARGET_PULSES = int(WATER_TARGET_NORMAL * PULSES_PER_LITER)
        print("[Smart Weather] ΚΑΝΟΝΙΚΗ -> 30 λεπτά, στόχος", WATER_TARGET_NORMAL, "L")


def check_and_water():
    """
    Έλεγχος ποτίσματος με βάση τη ΡΟΗ ΝΕΡΟΥ (μέσω flow sensor).
    Ποτίζει μέχρι να περάσει η ζητούμενη ποσότητα νερού, όχι για συγκεκριμένο χρόνο.
    """
    global last_water_time, is_watering, watering_start_time
    global pulses_this_watering, flow_pulse_count, last_pulse_seen_time
    
    current_time = time.time()
    
    # === ΦΑΣΗ 1: Δεν ποτίζει - έλεγχος αν είναι ώρα να ξεκινήσει ===
    if not is_watering:
        adjust_watering_by_weather()
        
        if current_time - last_water_time >= IRRIGATION_INTERVAL:
            print("-> Ξεκινάω αντλία! Στόχος:", WATER_TARGET_PULSES, "παλμοί (",
                  round(WATER_TARGET_PULSES / PULSES_PER_LITER, 1), "L)")
            # Μηδενίζουμε τον μετρητή για να μετράμε μόνο την τρέχουσα άρδευση
            flow_pulse_count = 0
            pulses_this_watering = 0
            watering_start_time = current_time
            last_pulse_seen_time = current_time
            set_output(WATER_PUMP_PIN, 1)
            is_watering = True
        else:
            time_left = IRRIGATION_INTERVAL - (current_time - last_water_time)
            print("-> Επόμενο πότισμα σε:", int(time_left / 60), "λεπτά")
        return
    
    # === ΦΑΣΗ 2: Ποτίζει - έλεγχος αν έφτασε ο στόχος ή υπάρχει πρόβλημα ===
    pulses_this_watering = flow_pulse_count
    liters_so_far = pulses_this_watering / PULSES_PER_LITER
    elapsed = current_time - watering_start_time
    
    print("-> Πότισμα... Παλμοί:", pulses_this_watering, 
          "(", round(liters_so_far, 2), "L) σε", int(elapsed), "δευτ.")
    
    # ΕΛΕΓΧΟΣ 1: Έφτασε στον στόχο -> κλείνει η αντλία
    if pulses_this_watering >= WATER_TARGET_PULSES:
        print("-> Στόχος επιτεύχθηκε! Κλείνω την αντλία. Παρασχέθηκαν",
              round(liters_so_far, 2), "L")
        set_output(WATER_PUMP_PIN, 0)
        is_watering = False
        last_water_time = current_time
        return
    
    # ΕΛΕΓΧΟΣ 2: Δεν περνά νερό -> πρόβλημα! Άδεια δεξαμενή ή χάλασε αντλία
    if current_time - last_pulse_seen_time > NO_FLOW_TIMEOUT:
        print("-> ΠΡΟΒΛΗΜΑ! Δεν περνά νερό για", NO_FLOW_TIMEOUT, "δευτ. - Σταματάω αντλία!")
        set_output(WATER_PUMP_PIN, 0)
        set_output(RED_LIGHT_PIN, 1)   # Κόκκινο LED ON
        is_watering = False
        last_water_time = current_time
        return
    
    # ΕΛΕΓΧΟΣ 3: Ασφάλεια - μέγιστος χρόνος λειτουργίας
    if elapsed > PUMP_TIMEOUT_SECONDS:
        print("-> Υπέρβαση μέγιστου χρόνου (", PUMP_TIMEOUT_SECONDS, "δευτ). Κλείνω αντλία.")
        set_output(WATER_PUMP_PIN, 0)
        is_watering = False
        last_water_time = current_time
        return

            
# =========================================================
# MAIN PROGRAM
# =========================================================
def main():
    global last_water_time
    
    print("=" * 50)
    print("Chloroplasters Tower Garden - Starting...")
    print("=" * 50)
    
    set_output(WATER_PUMP_PIN, 0)
    set_output(FRESH_WATER_PUMP_PIN, 0)
    set_output(FAN_PIN, 0)
    
    last_water_time = time.time()

    while True:
        if is_button_pressed():
            print("STOP BUTTON PRESSED! Shutting down...")
            set_output(WATER_PUMP_PIN, 0)
            set_output(FAN_PIN, 0)
            break
            
        # 1. Έξυπνο Πότισμα (βάσει ροής)
        check_and_water()

        # 2. Έλεγχος pH & EC
        ph_homeostasis()
        conductivity_homeostasis()
        
        # 3. Έλεγχος θερμοκρασίας νερού
        water_temp = get_water_temp()
        if water_temp != -999:
            if water_temp > WATER_TEMP_MAX:
                set_output(FAN_PIN, 1)
            elif water_temp < WATER_TEMP_MIN:
                set_output(FAN_PIN, 0)
        
        time.sleep(2) 

main()
