# only listens on 127.0.0.1

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import platform
import threading
import time
import webbrowser

from scanners.wifi import scanWifi
from scanners.ble import scanBle
from scanners.known import getKnownWifi, getKnownBle, tagNetworks, tagDevices
from scanners.connect import connectWifi
from scanners.traffic import getTrafficStats
from analyzers.anomalies import detectAnomalies
from analyzers.summary import generateSummary, generateBleSummary, explainNetwork
import config

staticDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# ── Traffic logger ─────────────────────────────────────────────────────────
# Samples once per second; keeps up to 3600 entries (~1 hour).
# Each entry: {t, ssid, rx_bytes, tx_bytes, rx_bps, tx_bps}

_trafficLog      = []
_trafficLogLock  = threading.Lock()
_LOG_MAX         = 3600
_loggerStartedAt = None


def _trafficLoggerThread():
    global _loggerStartedAt
    _loggerStartedAt = time.time()
    prev = None
    while True:
        try:
            stats = getTrafficStats()
            now   = time.time()
            rx_bps = 0
            tx_bps = 0
            if prev is not None:
                dt = now - prev["t"]
                if dt > 0:
                    rx_bps = max(0, int((stats["rx_bytes"] - prev["rx_bytes"]) / dt))
                    tx_bps = max(0, int((stats["tx_bytes"] - prev["tx_bytes"]) / dt))
            entry = {
                "t":        now,
                "ssid":     stats.get("ssid"),
                "rx_bytes": stats.get("rx_bytes", 0),
                "tx_bytes": stats.get("tx_bytes", 0),
                "rx_bps":   rx_bps,
                "tx_bps":   tx_bps,
            }
            prev = entry
            with _trafficLogLock:
                _trafficLog.append(entry)
                if len(_trafficLog) > _LOG_MAX:
                    del _trafficLog[0]
        except Exception:
            pass
        time.sleep(1)


def _startTrafficLogger():
    t = threading.Thread(target=_trafficLoggerThread, daemon=True)
    t.start()


class RequestHandler(BaseHTTPRequestHandler):

    def handle(self):
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    # ── GET ────────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        routes = {
            "/":                  lambda: self.serveFile("index.html", "text/html"),
            "/index.html":        lambda: self.serveFile("index.html", "text/html"),
            "/oui.json":          lambda: self.serveFile("oui.json", "application/json"),
            "/api/version":       self.apiVersion,
            "/api/scan":          self.apiScan,
            "/api/ble":           self.apiBle,
            "/api/anomalies":     self.apiAnomalies,
            "/api/summary":       self.apiSummary,
            "/api/explain":       lambda: self.apiExplain(parsed),
            "/api/traffic":       self.apiTraffic,
            "/api/traffic/log":   lambda: self.apiTrafficLog(parsed),
            "/api/status":        self.apiStatus,
        }

        handler = routes.get(path)
        if handler:
            handler()
        else:
            self.send404()

    # ── POST ───────────────────────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if path == "/api/connect":
            self.apiConnect(data)
        else:
            self.send404()

    # ── API handlers ───────────────────────────────────────────────────────

    def apiVersion(self):
        self.sendJson({
            "version":        config.version,
            "app":            config.appName,
            "bleScanSeconds": config.bleScanSeconds,
            "os":             platform.system(),
        })

    def apiScan(self):
        networks = scanWifi()
        knownSsids = getKnownWifi()
        tagNetworks(networks, knownSsids)
        self.sendJson(networks)

    def apiBle(self):
        devices = scanBle(config.bleScanSeconds)
        knownAddrs = getKnownBle()
        tagDevices(devices, knownAddrs)
        summary = generateBleSummary(devices)
        self.sendJson({
            "devices":     devices,
            "summary":     summary,
            "scanSeconds": config.bleScanSeconds,
        })

    def apiAnomalies(self):
        networks = scanWifi()
        knownSsids = getKnownWifi()
        tagNetworks(networks, knownSsids)
        anomalies = detectAnomalies(networks)
        self.sendJson({"networks": networks, "anomalies": anomalies})

    def apiSummary(self):
        networks = scanWifi()
        knownSsids = getKnownWifi()
        tagNetworks(networks, knownSsids)
        anomalies = detectAnomalies(networks)
        self.sendJson({"summary": generateSummary(networks, anomalies)})

    def apiExplain(self, parsed):
        params = parse_qs(parsed.query)
        ssid = params.get("ssid", [""])[0]
        if not ssid:
            self.sendJson({"explanation": "Tell me which network — example: explain MyWiFi"})
            return
        networks = scanWifi()
        knownSsids = getKnownWifi()
        tagNetworks(networks, knownSsids)
        anomalies = detectAnomalies(networks)
        self.sendJson({"explanation": explainNetwork(ssid, networks, anomalies)})

    def apiTraffic(self):
        self.sendJson(getTrafficStats())

    def apiTrafficLog(self, parsed):
        params = parse_qs(parsed.query)
        try:
            limit = int(params.get("limit", [300])[0])
        except (ValueError, IndexError):
            limit = 300
        with _trafficLogLock:
            entries = list(_trafficLog[-limit:])
        self.sendJson({
            "started_at": _loggerStartedAt,
            "entries":    entries,
        })

    def apiStatus(self):
        stats = getTrafficStats()
        self.sendJson({
            "connected": bool(stats.get("ssid")),
            "ssid":      stats.get("ssid"),
            "ip":        stats.get("ip"),
            "interface": stats.get("interface"),
        })

    def apiConnect(self, data):
        ssid     = (data.get("ssid") or "").strip()
        password = (data.get("password") or "").strip() or None
        if not ssid:
            self.sendJson({"success": False, "message": "No SSID provided."})
            return
        success, message = connectWifi(ssid, password)
        self.sendJson({"success": success, "message": message})

    # ── Static file serving ────────────────────────────────────────────────

    def serveFile(self, filename, contentType):
        filepath = os.path.join(staticDir, filename)
        if not os.path.isfile(filepath):
            self.send404()
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", contentType)
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def sendJson(self, data):
        body = json.dumps(data, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send404(self):
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not found")

    def log_message(self, format, *args):
        pass  # thankyou google...


def startWeb(openBrowser=True):
    _startTrafficLogger()
    port = config.webPort
    server = HTTPServer(("127.0.0.1", port), RequestHandler)
    url = f"http://localhost:{port}"
    print(f"\n  {config.appName}")
    print(f"  Web UI is live at {url}")
    print(f"  This only runs on your machine — nothing goes to the internet.")
    print(f"  Press Ctrl+C to stop.\n")
    if openBrowser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down. Stay safe out there.")
        server.server_close()
