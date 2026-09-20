# =========================================================
# garden_wifi.py  -  WiFi web server for the Chloroplasters dashboard
#
# The board becomes a tiny web server on your WiFi:
#   http://<board-ip>/            -> the dashboard page (dashboard.html on flash)
#   http://<board-ip>/data.json   -> the latest readings & actions as JSON
#
# It is COOPERATIVE: it never blocks. You call server.poll() from inside
# your main loop, and it answers any waiting browser request in that slice.
#
# Needs MicroPython firmware with WiFi (the Pico 2 W / RM2 build).
# If `import network` fails, flash that firmware first.
# =========================================================

import time

try:
    import network
    import socket
    try:
        import ujson as json
    except ImportError:
        import json
    _HAS_NET = True
except ImportError:
    _HAS_NET = False


def connect(ssid, password, timeout_s=20):
    """Connect to WiFi. Returns the IP string, or None on failure."""
    if not _HAS_NET:
        print("WiFi: this firmware has no 'network' module. Flash the Pico 2 W build.")
        return None
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("WiFi: connecting to", ssid, "...")
        wlan.connect(ssid, password)
        t0 = time.time()
        while not wlan.isconnected():
            if time.time() - t0 > timeout_s:
                print("WiFi: connection timed out.")
                return None
            time.sleep(0.5)
    ip = wlan.ifconfig()[0]
    print("WiFi: connected. Dashboard at  http://%s/" % ip)
    return ip


class Server:
    """Non-blocking HTTP server. Serves the dashboard and /data.json."""

    def __init__(self, logger, port=80, page="dashboard.html"):
        self.logger = logger
        self.page = page
        self.sock = None
        if not _HAS_NET:
            return
        try:
            addr = socket.getaddrinfo("0.0.0.0", port)[0][-1]
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(addr)
            s.listen(2)
            s.setblocking(False)
            self.sock = s
            print("WiFi: server listening on port", port)
        except Exception as e:
            print("WiFi: could not start server:", e)

    # ---- request handling -----------------------------------------
    def _send_json(self, cl):
        body = json.dumps({"records": self.logger.buffer})
        cl.send("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n")
        cl.send("Access-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n")
        cl.send(body)

    def _send_page(self, cl):
        try:
            cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n")
            with open(self.page, "r") as f:
                while True:
                    chunk = f.read(512)
                    if not chunk:
                        break
                    cl.send(chunk)
        except OSError:
            cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n")
            cl.send("<h3>Chloroplasters</h3><p>Upload dashboard.html to the board, "
                    "or open it locally and point WiFi mode at this board's IP.</p>"
                    "<p>Live data: <a href='/data.json'>/data.json</a></p>")

    def _handle(self, cl):
        try:
            cl.settimeout(1.5)
            req = cl.recv(256)
            path = "/"
            if req:
                try:
                    path = req.split(b" ")[1].decode()
                except Exception:
                    path = "/"
            if path.startswith("/data.json"):
                self._send_json(cl)
            else:
                self._send_page(cl)
        except Exception:
            pass
        finally:
            try:
                cl.close()
            except Exception:
                pass

    def poll(self, duration_s=0.0):
        """Answer any waiting requests for up to duration_s seconds.
        Call this instead of time.sleep() in your loop."""
        if self.sock is None:
            if duration_s:
                time.sleep(duration_s)
            return
        end = time.ticks_add(time.ticks_ms(), int(duration_s * 1000))
        first = True
        while first or time.ticks_diff(end, time.ticks_ms()) > 0:
            first = False
            try:
                cl, addr = self.sock.accept()
                self._handle(cl)
            except OSError:
                time.sleep(0.02)      # nothing waiting; yield briefly
