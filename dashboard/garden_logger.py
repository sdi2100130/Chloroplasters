# =========================================================
# garden_logger.py  -  Chloroplasters event & sensor logger
# Drop this file next to main.py on the XRP board.
# It writes every reading and action to garden_log.csv on the
# board's flash, and also echoes each row over USB as "LOG,..."
# so the dashboard can read it live.
# =========================================================

import time

# Real-time clock is optional. If it's set, rows get a human
# timestamp; if not, the dashboard falls back to uptime seconds.
try:
    from machine import RTC
    _rtc = RTC()
except Exception:
    _rtc = None

_HEADER = "time_iso,uptime_s,kind,label,value,unit,detail\n"


def _clean(s):
    # Keep the CSV honest: no stray commas or newlines in a field.
    return str(s).replace(",", ";").replace("\n", " ").replace("\r", " ")


class Logger:
    """Append-only logger for the tower garden.

    sensor(...) rows are throttled (one per label every sensor_period_s)
    so the flash isn't hammered. action/alarm/state rows are written
    immediately, because they're rare and matter.
    """

    def __init__(self, filename="garden_log.csv", sensor_period_s=30,
                 echo=True, max_bytes=200000, buffer_max=300):
        self.filename = filename
        self.sensor_period = sensor_period_s
        self.echo = echo
        self.max_bytes = max_bytes
        self._last = {}                 # label -> ticks_ms of last sensor row
        self._boot = time.ticks_ms()
        self.buffer = []                # recent records, served over WiFi
        self.buffer_max = buffer_max
        self._ensure_header()

    # ---- internals -------------------------------------------------
    def _ensure_header(self):
        try:
            f = open(self.filename, "r")
            f.close()
        except OSError:
            try:
                with open(self.filename, "w") as f:
                    f.write(_HEADER)
            except OSError as e:
                print("Logger: cannot create file:", e)

    def _uptime(self):
        return time.ticks_diff(time.ticks_ms(), self._boot) // 1000

    def _now_iso(self):
        if _rtc is None:
            return ""
        try:
            y, mo, d, wd, h, mi, s, us = _rtc.datetime()
            if y < 2021:                # clock never set -> skip
                return ""
            return "%04d-%02d-%02dT%02d:%02d:%02d" % (y, mo, d, h, mi, s)
        except Exception:
            return ""

    def _rotate_if_needed(self):
        try:
            import os
            size = os.stat(self.filename)[6]
            if size > self.max_bytes:
                try:
                    os.remove(self.filename + ".1")
                except OSError:
                    pass
                os.rename(self.filename, self.filename + ".1")
                with open(self.filename, "w") as f:
                    f.write(_HEADER)
                self._last = {}
        except Exception:
            pass

    def _write(self, kind, label, value, unit, detail):
        iso = self._now_iso()
        up = self._uptime()
        kind = _clean(kind); label = _clean(label)
        value = _clean(value); unit = _clean(unit); detail = _clean(detail)
        row = "%s,%d,%s,%s,%s,%s,%s\n" % (iso, up, kind, label, value, unit, detail)
        if self.echo:
            print("LOG," + row.rstrip())
        # in-memory buffer for the WiFi server
        try:
            num = float(value)
        except (ValueError, TypeError):
            num = None
        self.buffer.append({"iso": iso, "uptime": up, "kind": kind, "label": label,
                            "value": num, "unit": unit, "detail": detail})
        if len(self.buffer) > self.buffer_max:
            self.buffer = self.buffer[-self.buffer_max:]
        try:
            self._rotate_if_needed()
            with open(self.filename, "a") as f:
                f.write(row)
        except OSError as e:
            print("Logger: write failed:", e)

    # ---- public API ------------------------------------------------
    def sensor(self, label, value, unit=""):
        """Log a sensor reading (throttled per label). Ignores -999 / None."""
        if value is None or value == -999:
            return
        now = time.ticks_ms()
        last = self._last.get(label)
        if last is not None and time.ticks_diff(now, last) < self.sensor_period * 1000:
            return
        self._last[label] = now
        try:
            value = round(value, 2)
        except Exception:
            pass
        self._write("sensor", label, value, unit, "")

    def action(self, label, detail="", value="", unit=""):
        """Log something the system DID (a dose, watering, fan, etc.)."""
        self._write("action", label, value, unit, detail)

    def alarm(self, label, detail=""):
        """Log a problem the system detected."""
        self._write("alarm", label, "", "", detail)

    def state(self, label, detail=""):
        """Log a state change (normal / safe)."""
        self._write("state", label, "", "", detail)

    def set_time(self, year, month, day, hour, minute, second):
        """Optional: set the clock once from the REPL for real timestamps.
        e.g.  logger.set_time(2026, 7, 4, 15, 30, 0)
        """
        if _rtc is None:
            print("No RTC available on this board.")
            return
        _rtc.datetime((year, month, day, 0, hour, minute, second, 0))
        print("Clock set.")
