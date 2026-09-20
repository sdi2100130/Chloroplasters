from machine import Pin
import time
import onewire
import ds18x20

# ============================================
# 1. PIN SETUP - Ρυθμίσεις Θυρών
# ============================================

# --- Digital sensors ---
WATER_TEMP_PIN = 16   # IO16 -> DS18B20 αδιάβροχος αισθητήρας

# --- Outputs: FAN ---
FAN_PIN = 19          # IO19 -> Relay 3 (Ανεμιστήρας)

# =========================================================
# 2. THRESHOLD VALUES - Όρια Λειτουργίας
# =========================================================

WATER_TEMP_MAX = 30     # °C - Άναψε ανεμιστήρα
WATER_TEMP_MIN = 26     # °C - Σβήσε ανεμιστήρα

# =========================================================
# 3. INITIALIZATION - Αρχικοποίηση
# =========================================================

# OneWire & DS18B20 (Για τον αδιάβροχο αισθητήρα νερού)
ds_pin = Pin(WATER_TEMP_PIN)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
roms = ds_sensor.scan()

if not roms:
    print("ΠΡΟΣΟΧΗ: Δεν βρέθηκε ο αισθητήρας DS18B20! Ελέγξτε την αντίσταση 4.7kΩ.")
else:
    print(f"Βρέθηκε αισθητήρας DS18B20 με διεύθυνση: {roms[0]}")

# =========================================================
# 4. SENSORS & HELPER FUNCTIONS
# =========================================================

def get_water_temp():
    """Reads the waterproof DS18B20 sensor."""
    if not roms: 
        return -999
    try:
        ds_sensor.convert_temp()
        time.sleep_ms(750)  # Ο αισθητήρας θέλει 750ms για τη μετατροπή
        return ds_sensor.read_temp(roms[0])
    except Exception as e:
        print("Σφάλμα ανάγνωσης DS18B20:", e)
        return -999

def set_output(pin_num, state):
    """Turn output pin ON (1) or OFF (0)."""
    p = Pin(pin_num, Pin.OUT)
    p.value(state)

# =========================================================
# MAIN PROGRAM - ΔΟΚΙΜΗ (ΧΩΡΙΣ BUTTON)
# =========================================================
def main():
    print("=" * 50)
    print("Chloroplasters - Water Temp & Fan Test (No Button)...")
    print("=" * 50)
    
    # Αρχικοποίηση: Κλείσιμο ανεμιστήρα στην εκκίνηση
    set_output(FAN_PIN, 0)

    while True:
        # 1. Διάβασμα Θερμοκρασίας
        water_temp = get_water_temp()
        
        if water_temp != -999:
            print(f"Θερμοκρασία Νερού: {water_temp:.2f}°C")
            
            # 2. Λογική Ελέγχου Ανεμιστήρα
            if water_temp > WATER_TEMP_MAX:
                print(f"-> Θερμοκρασία > {WATER_TEMP_MAX}°C: Ενεργοποίηση Ανεμιστήρα (ON)")
                set_output(FAN_PIN, 1)
            elif water_temp < WATER_TEMP_MIN:
                print(f"-> Θερμοκρασία < {WATER_TEMP_MIN}°C: Απενεργοποίηση Ανεμιστήρα (OFF)")
                set_output(FAN_PIN, 0)
            else:
                print("-> Θερμοκρασία εντός ορίων (Hysteresis). Καμία αλλαγή στο Fan.")
        else:
            print("Αποτυχία λήψης θερμοκρασίας!")
        
        print("-" * 30)
        time.sleep(2)  # Έλεγχος κάθε 2 δευτερόλεπτα

main()