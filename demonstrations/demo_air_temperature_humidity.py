"""SHT31 air temperature and humidity demonstration with cooling fan control."""
from machine import Pin, I2C
import time

I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
SHT31_ADDR = 0x44
INTERVAL_MS = 1000
FAN_PIN = 19
FAN_ACTIVE_HIGH = True
FAN_ON_TEMP_C = 28.0
FAN_OFF_TEMP_C = 27.0


def crc8(data):
    crc = 0xFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 255 if crc & 0x80 else (crc << 1) & 255
    return crc


def read_sensor(i2c):
    i2c.writeto(SHT31_ADDR, b'\x24\x00')
    time.sleep_ms(20)
    data = i2c.readfrom(SHT31_ADDR, 6)
    if len(data) != 6 or crc8(data[:2]) != data[2] or crc8(data[3:5]) != data[5]:
        raise ValueError("Incomplete or corrupt SHT31 reading")
    temperature = -45 + 175 * ((data[0] << 8) | data[1]) / 65535
    humidity = 100 * ((data[3] << 8) | data[4]) / 65535
    return temperature, humidity


def main():
    fan = None
    fan_is_on = False
    off = 0 if FAN_ACTIVE_HIGH else 1
    on = 1 - off
    print("AIR TEMPERATURE / HUMIDITY DEMO | Pump disconnected")
    print("Cup a hand near the sensor and watch the readings change; keep it dry.")
    print("Fan IO{}: ON at {} C, OFF at {} C. Ctrl+C stops the fan.".format(
        FAN_PIN, FAN_ON_TEMP_C, FAN_OFF_TEMP_C))
    try:
        fan = Pin(FAN_PIN, Pin.OUT, value=off)
        if FAN_OFF_TEMP_C >= FAN_ON_TEMP_C:
            raise ValueError("Fan OFF temperature must be below ON temperature")
        i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=100000)
        if SHT31_ADDR not in i2c.scan():
            print("ERROR: SHT31 missing at 0x44; check Qwiic wiring and power.")
            return
        while True:
            start = time.ticks_ms()
            try:
                temperature, humidity = read_sensor(i2c)
                if temperature >= FAN_ON_TEMP_C:
                    fan_is_on = True
                elif temperature <= FAN_OFF_TEMP_C:
                    fan_is_on = False
                fan.value(on if fan_is_on else off)
                print("Air temperature: {:.2f} C | Humidity: {:.1f} % | Fan: {}".format(
                    temperature, humidity, "ON" if fan_is_on else "OFF"))
            except Exception as exc:
                fan.value(off)
                fan_is_on = False
                print("READ ERROR:", exc, "| no measurement available | Fan: OFF")
            remaining = INTERVAL_MS - time.ticks_diff(time.ticks_ms(), start)
            if remaining > 0:
                time.sleep_ms(remaining)
    except KeyboardInterrupt:
        print("Demo stopped.")
    except Exception as exc:
        print("DEMO ERROR:", exc)
    finally:
        if fan is not None:
            fan.value(off)
        print("Fan OFF.")


if __name__ == "__main__":
    main()
