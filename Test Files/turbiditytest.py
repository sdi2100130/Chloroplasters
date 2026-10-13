from machine import I2C, Pin
import time

# =========================================================
# Turbidity Sensor Test - Calibrated for Chloroplasters
# =========================================================

# --- Qwiic / ADS1015 setup ---
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
ADS1015_ADDR = 0x48
TURBIDITY_CHANNEL = 2   # ADS1015 A2 -> αναλογική έξοδος (Aout) του SEN0189

# --- ADS1015 settings ---
ADS1015_REG_CONVERSION = 0x00
ADS1015_REG_CONFIG = 0x01
ADS1015_CONFIG_BASE = 0x8583
ADS1015_MUX = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}

# --- Calibration Constants ---
# Τάση αναφοράς καθαρού/διαυγούς νερού (βάσει των μετρήσεών σου ~2.95V - 3.10V)
V_CLEAR = 3.00

# Τάση πλήρους συσκότισης / μέγιστης θολότητας
V_DARK = 0.80

# Μέγιστη κλίμακα NTU
MAX_NTU = 3000.0

# --- Reading settings ---
SAMPLES = 20
SAMPLE_DELAY = 0.02
INTERVAL = 1.0

i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)


def read_ads1015_channel(channel):
    """Read one ADS1015 channel and return voltage."""
    config = ADS1015_CONFIG_BASE | ADS1015_MUX[channel]
    config_bytes = bytes([ADS1015_REG_CONFIG, (config >> 8) & 0xFF, config & 0xFF])
    i2c.writeto(ADS1015_ADDR, config_bytes)
    time.sleep(0.005)

    i2c.writeto(ADS1015_ADDR, bytes([ADS1015_REG_CONVERSION]))
    data = i2c.readfrom(ADS1015_ADDR, 2)

    raw = (data[0] << 8) | data[1]
    raw = raw >> 4
    if raw > 2047:
        raw = raw - 4096

    return raw * 4.096 / 2048


def read_average_voltage():
    """Take several ADS1015 readings and return the average voltage."""
    total = 0.0
    for _ in range(SAMPLES):
        total += read_ads1015_channel(TURBIDITY_CHANNEL)
        time.sleep(SAMPLE_DELAY)
    return total / SAMPLES


def voltage_to_ntu(voltage):
    """Μετατροπή τάσης σε NTU με βάση τη βαθμονόμηση καθαρού νερού (V_CLEAR)."""
    if voltage is None:
        return 0.0

    # Τάση ίση ή μεγαλύτερη από το καθαρό νερό θεωρείται 0 NTU
    if voltage >= V_CLEAR:
        return 0.0

    # Τάση χαμηλότερη από το κατώφλι μέγιστου σκότους τερματίζει στο MAX_NTU
    if voltage <= V_DARK:
        return MAX_NTU

    # Γραμμική αναγωγή: όσο πέφτει η τάση, τόσο αυξάνεται η θολότητα
    ntu = ((V_CLEAR - voltage) / (V_CLEAR - V_DARK)) * MAX_NTU
    return ntu


def main():
    print("=" * 50)
    print("TURBIDITY SENSOR TEST - CALIBRATED")
    print("=" * 50)
    print("Qwiic ADS1015 address: 0x{:02X}".format(ADS1015_ADDR))
    print("Sensor connected to ADS1015 A" + str(TURBIDITY_CHANNEL))
    print("Baseline V_CLEAR: {:.2f} V (0 NTU)".format(V_CLEAR))
    print("Baseline V_DARK:  {:.2f} V ({:.0f} NTU)".format(V_DARK, MAX_NTU))
    print()
    print("Press CTRL+C to stop")
    print("=" * 50)
    print()

    try:
        while True:
            voltage = read_average_voltage()
            ntu = voltage_to_ntu(voltage)

            print("Voltage: {:.3f} V | Turbidity: {:.1f} NTU".format(voltage, ntu))
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\nTest stopped by user.")


main()