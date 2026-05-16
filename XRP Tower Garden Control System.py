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
PH_ACID_SERVO_PIN  = 6    # IO6  (Servo 1) -> Κιτρικό Οξύ (pH↓)
PH_BASE_SERVO_PIN  = 7    # IO7  (Servo 3) -> Διττανθρακικό (pH↑)
NUTRIENT_SERVO_PIN = 8   # IO8 (Servo 4) -> Θρεπτικό (EC↑)

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

# --- Χρονοδιακόπτης Ποτίσματος ---
IRRIGATION_DURATION = 180   # Σταθερό: 3 λεπτά για να γεμίζουν τα πιατάκια

# Ξεκινάει ως κανονικό (30 λεπτά)
IRRIGATION_INTERVAL = 1800  

# Μεταβλητές ελέγχου
last_water_time = 0
is_watering = False

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

# =========================================================
# 4. SERVO CONTROL FUNCTIONS - Έλεγχος Σύριγγας
# =========================================================
# "Βήμα 10"

# Ρυθμίστε εδώ πόσες μοίρες πρέπει να γυρίσει για να βγάλει 1mL
SERVO_1ML_ANGLE = 20  # ΑΛΛΑΞΤΕ ΑΥΤΟ ΤΟ ΝΟΥΜΕΡΟ ΜΕΤΑ ΤΗ ΒΑΘΜΟΝΟΜΗΣΗ

def set_servo_angle(pin_num, angle):
    """
    Γυρίζει το Servo σε συγκεκριμένη γωνία (0-180).
    Moves the Servo to a specific angle (0-180).
    """
    pwm = PWM(Pin(pin_num))
    pwm.freq(50) # Τα Servos δουλεύουν στα 50Hz
    
    # Μετατροπή μοιρών (0-180) σε duty cycle (περίπου 1000-9000 για MicroPython)
    min_duty = 1000  # 0 μοίρες
    max_duty = 9000  # 180 μοίρες
    duty = min_duty + int((angle / 180) * (max_duty - min_duty))
    pwm.duty_u16(duty)
    time.sleep(0.5) # Περίμενε να φτάσει το servo
    pwm.deinit() # Κλείσε το σήμα για να μην τρέμει (jitter)

def push_syringe(servo_pin):
    """
    Πατάει τη σύριγγα κατά 'SERVO_1ML_ANGLE' μοίρες για να βγάλει 1 δόση.
    Pushes the syringe to dispense 1 dose (~1mL).
    """
    # Σημείωση: Στην πραγματικότητα η σύριγγα πρέπει να κρατάει "μνήμη" της θέσης της.
    # Για τώρα, κάνουμε μια απλή κίνηση: Πάτα και γύρνα πίσω (ή απλά προχώρα).
    # Βάση του manual σας, θέλετε να προχωράει 1 δόση κάθε φορά.
    
    print(f"Ενεργοποίηση Σύριγγας (Pin {servo_pin}). Παροχή 1mL...")
    # Υποθέτουμε ότι το servo ξεκινάει από το 0. Πατάει 20 μοίρες, και μένει εκεί.
    # ΠΡΟΣΟΧΗ: Αν το κάνετε έτσι, μετά από 9 δόσεις (9*20=180) το servo τερματίζει
    # και θα χρειαστεί να το γυρίσετε στο 0 χειροκίνητα γεμίζοντας τη σύριγγα!
    set_servo_angle(servo_pin, SERVO_1ML_ANGLE)
    time.sleep(1)
    # Προαιρετικά: Επιστροφή στο 0. (Ανάλογα πώς έχετε φτιάξει το 3D print)
    set_servo_angle(servo_pin, 0)

# =========================================================
# 5. ADS1015 & SENSORS FUNCTIONS - Διάβασμα Αισθητήρων
# =========================================================

ADS1015_REG_CONVERSION = 0x00
ADS1015_REG_CONFIG     = 0x01
ADS1015_CONFIG_BASE = 0x8583
ADS1015_MUX = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}

def ads1015_read_channel(channel):
    """Reads voltage from ADS1015."""
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
    """
    Reads the waterproof DS18B20 sensor.
    """
    if not roms: return -999
    try:
        ds_sensor.convert_temp()
        time.sleep_ms(750) # Ο αισθητήρας θέλει 750ms να σκεφτεί
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

# SHT31 TEMPERATURE & HUMIDITY SENSOR (I2C)
def read_sht31():
    """
    Read temperature and humidity from SHT31.
    Returns tuple: (temperature_C, humidity_percent)
    Returns (None, None) on read failure.
    """
    try:
        # Send measurement command (high repeatability, no clock stretching)
        i2c.writeto(SHT31_ADDR, b'\x24\x00')
        time.sleep(0.02)  # Wait ~20ms for measurement
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
# 6. HELPER FUNCTIONS - Βοηθητικές
# =========================================================

def is_button_pressed():
    """Check if STOP button is pressed."""
    p = Pin(STOP_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    return p.value() == 0 # 0 σημαίνει ότι πατήθηκε (λόγω PULL_UP)

def set_output(pin_num, state):
    """Turn output pin ON (1) or OFF (0). (Χρησιμοποιείται για LEDs)"""
    p = Pin(pin_num, Pin.OUT)
    p.value(state)

# =========================================================
# 7. HOMEOSTASIS FUNCTIONS - Ομοιόσταση (Με Servo πλέον)
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

def adjust_interval_by_weather():
    """
    Διαβάζει τον αισθητήρα SHT31 (αέρα) και προσαρμόζει 
    δυναμικά το χρόνο αναμονής μεταξύ των ποτισμάτων.
    """
    global IRRIGATION_INTERVAL
    
    # Διαβάζουμε θερμοκρασία και υγρασία αέρα από τον SHT31
    air_temp, air_hum = read_sht31()
    
    # Αν ο αισθητήρας έχει πρόβλημα, κρατάμε τον κανονικό χρόνο για ασφάλεια
    if air_temp is None or air_hum is None:
        IRRIGATION_INTERVAL = 1800 # 30 λεπτά
        return

    print(f"[Smart Weather] Αέρας: {air_temp:.1f}°C, Υγρασία: {air_hum:.1f}%")

    # ΣΕΝΑΡΙΟ 1: Ζεστό ή Ξηρό περιβάλλον (Το νερό εξατμίζεται γρήγορα)
    # Αν η θερμοκρασία είναι πάνω από 28°C Ή η υγρασία κάτω από 40%
    if air_temp > 28 or air_hum < 40:
        IRRIGATION_INTERVAL = 900  # 15 λεπτά αναμονή (Ποτίζει πιο συχνά)
        print("[Smart Weather] Κατάσταση: ΖΕΣΤΗ/ΞΗΡΗ -> Μείωση αναμονής στα 15 λεπτά.")
        
    # ΣΕΝΑΡΙΟ 2: Κρύο ή πολύ Υγρό περιβάλλον (Το νερό μένει στα πιατάκια)
    # Αν η θερμοκρασία είναι κάτω από 18°C Ή η υγρασία πάνω από 75%
    elif air_temp < 18 or air_hum > 75:
        IRRIGATION_INTERVAL = 2700 # 45 λεπτά αναμονή (Ποτίζει πιο αραιά)
        print("[Smart Weather] Κατάσταση: ΚΡΥΑ/ΥΓΡΗ -> Αυξηση αναμονής στα 45 λεπτά.")
        
    # ΣΕΝΑΡΙΟ 3: Ιδανικές/Κανονικές συνθήκες
    else:
        IRRIGATION_INTERVAL = 1800 # 30 λεπτά αναμονή
        print("[Smart Weather] Κατάσταση: ΚΑΝΟΝΙΚΗ -> Αναμονή στα 30 λεπτά.")


def check_and_water():
    """
    Έλεγχος ποτίσματος με βάση το χρόνο ΚΑΙ τον καιρό περιβάλλοντος.
    """
    global last_water_time, is_watering
    current_time = time.time()
    
    # Πριν ελέγξουμε αν ήρθε η ώρα, προσαρμόζουμε το Interval βάσει καιρού
    if not is_watering:
        adjust_interval_by_weather()
        
        if current_time - last_water_time >= IRRIGATION_INTERVAL:
            print("-> Ξεκινάω την αντλία νερού!")
            set_output(WATER_PUMP_PIN, 1)
            is_watering = True
            last_water_time = current_time 
        else:
            time_left = IRRIGATION_INTERVAL - (current_time - last_water_time)
            print(f"-> Επόμενο πότισμα σε: {int(time_left / 60)} λεπτά (Interval: {int(IRRIGATION_INTERVAL/60)}μ)")
            
    elif is_watering:
        if current_time - last_water_time >= IRRIGATION_DURATION:
            print("-> Το πότισμα ολοκληρώθηκε. Κλείνω την αντλία.")
            set_output(WATER_PUMP_PIN, 0)
            is_watering = False
            last_water_time = current_time 
        else:
            time_left = IRRIGATION_DURATION - (current_time - last_water_time)
            print(f"-> Πότισμα σε εξέλιξη... Απομένουν {int(time_left)} δευτερόλεπτα.")
            
# =========================================================
# MAIN PROGRAM
# =========================================================
def main():
    print("=" * 50)
    print("Chloroplasters Tower Garden - Starting...")
    print("=" * 50)
    
    # Initialize all DC Pumps to OFF
    set_output(WATER_PUMP_PIN, 0)
    set_output(FRESH_WATER_PUMP_PIN, 0)
    set_output(FAN_PIN, 0)

    while True:
        if is_button_pressed():
            print("STOP BUTTON PRESSED! Shutting down...")
            set_output(WATER_PUMP_PIN, 0)
            set_output(FAN_PIN, 0)
            break
            
        # 1. Έξυπνο Πότισμα
        check_and_water()

        # 2. Έλεγχος pH & EC
        ph_homeostasis()
        conductivity_homeostasis()
        
        # 3. Έλεγχος θερμοκρασίας νερού (για τον ανεμιστήρα)
        water_temp = get_water_temp()
        if water_temp != -999:
            if water_temp > WATER_TEMP_MAX:
                set_output(FAN_PIN, 1) # Άναψε ανεμιστήρα
            elif water_temp < WATER_TEMP_MIN:
                set_output(FAN_PIN, 0) # Σβήσε ανεμιστήρα
        
        # Προτείνω μικρότερο sleep (π.χ. 2 δευτερόλεπτα) 
        # ώστε το Stop Button να ανταποκρίνεται πιο άμεσα.
        time.sleep(2) 

main()