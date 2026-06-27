from machine import I2C, Pin
import time

# Λίστα με γνωστές I2C διευθύνσεις για να αναγνωρίζουμε τι συνδέθηκε
KNOWN_DEVICES = {
    0x48: "ADS1015 / ADS1115 (Analog-to-Digital Converter) <- Το pH σου!",
    0x49: "ADS1015 / ADS1115 (Εναλλακτική διεύθυνση)",
    0x3C: "OLED Οθόνη (SSD1306)",
    0x3D: "OLED Οθόνη (Εναλλακτική)",
    0x68: "RTC (Ρολόι DS3231) ή MPU6050 (Γυροσκόπιο)",
    0x76: "Βαρομετρικός Αισθητήρας (BMP280/BME280)",
    0x77: "Βαρομετρικός Αισθητήρας (BMP280/BME280 εναλλακτική)",
    0x27: "LCD Οθόνη 16x2 με I2C adapter",
    0x3F: "LCD Οθόνη 16x2 (Εναλλακτική)"
}

# Όλα τα πιθανά έγκυρα ζευγάρια Pins για I2C στο Raspberry Pi Pico
# (Bus_ID, SDA_Pin, SCL_Pin)
I2C_PAIRS = [
    # Bus 0 Pins
    (0, 0, 1),   (0, 4, 5),   (0, 8, 9),   (0, 12, 13), (0, 16, 17), (0, 20, 21),
    # Bus 1 Pins
    (1, 2, 3),   (1, 6, 7),   (1, 10, 11), (1, 14, 15), (1, 18, 19), (1, 26, 27)
]

print("=" * 60)
print("ΕΝΑΡΞΗ ΚΑΘΟΛΙΚΟΥ I2C SCANNER (ΟΛΑ ΤΑ PINS & BUSES)")
print("=" * 60)
print("Παρακαλώ βεβαιωθείτε ότι το XRP Board είναι στο ON (με μπαταρίες).\n")

any_found = False

for bus, sda_pin, scl_pin in I2C_PAIRS:
    try:
        # Δοκιμάζουμε την αρχικοποίηση με εσωτερικά Pull-Up ενεργοποιημένα
        # σε περίπτωση που η πλακέτα δεν έχει δικές της αντιστάσεις
        i2c = I2C(bus, sda=Pin(sda_pin, Pin.PULL_UP), scl=Pin(scl_pin, Pin.PULL_UP), freq=100000)
        
        devices = i2c.scan()
        
        if devices:
            any_found = True
            print(f"🎉 ΒΡΕΘΗΚΕ ΣΥΣΚΕΥΗ!")
            print(f"   -> Bus: {bus}")
            print(f"   -> Pins: SDA = GP{sda_pin}, SCL = GP{scl_pin}")
            
            for dev in devices:
                hex_addr = hex(dev)
                # Έλεγχος αν ξέρουμε τι είναι
                device_name = KNOWN_DEVICES.get(dev, "Άγνωστη Συσκευή (ή custom module)")
                print(f"   -> Διεύθυνση: {hex_addr} | Πιθανή Συσκευή: {device_name}")
            print("-" * 60)
            
    except Exception as e:
        # Αγνοούμε τα σφάλματα αρχικοποίησης (κάποια pins μπορεί να χρησιμοποιούνται αλλού)
        pass

if not any_found:
    print("❌ Αποτυχία: Δεν βρέθηκε καμία I2C συσκευή σε καμία θύρα.")
    print("Πιθανά προβλήματα:")
    print("1. Το XRP Board είναι κλειστό (Power Switch στο OFF) ή δεν έχει μπαταρίες.")
    print("2. Το καλώδιο Qwiic / Jumper wires έχει κοπεί ή δεν πατάει καλά.")
    print("3. Ο αισθητήρας/ADC έχει καεί ή δεν τροφοδοτείται με ρεύμα (VCC/GND).")
else:
    print("Η σάρωση ολοκληρώθηκε επιτυχώς!")
print("=" * 60)