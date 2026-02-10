# only listens on 127.0.0.1

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os

from scanners.wifi import scanWifi
from scanners.ble import scanBle
from analyzers.anomalies import detectAnomalies
from analyzers.summary import generateSummary, generateBleSummary, explainNetwork
import config

staticDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class RequestHandler(BaseHTTPRequestHandler):

    def handle(self):
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        routes = {
            "/":              lambda: self.serveFile("index.html", "text/html"),
            "/index.html":    lambda: self.serveFile("index.html", "text/html"),
            "/api/scan":      self.apiScan,
            "/api/ble":       self.apiBle,
            "/api/anomalies": self.apiAnomalies,
            "/api/summary":   self.apiSummary,
            "/api/explain":   lambda: self.apiExplain(parsed),
        }

        handler = routes.get(path)
        if handler:
            handler()
        else:
            self.send404()

    # api stuff

    def apiScan(self):
        self.sendJson(scanWifi())

    def apiBle(self):
        devices = scanBle(config.bleScanSeconds)
        summary = generateBleSummary(devices)
        self.sendJson({"devices": devices, "summary": summary})

    def apiAnomalies(self):
        networks = scanWifi()
        anomalies = detectAnomalies(networks)
        self.sendJson({"networks": networks, "anomalies": anomalies})

    def apiSummary(self):
        networks = scanWifi()
        anomalies = detectAnomalies(networks)
        self.sendJson({"summary": generateSummary(networks, anomalies)})

    def apiExplain(self, parsed):
        params = parse_qs(parsed.query)
        ssid = params.get("ssid", [""])[0]
        if not ssid:
            self.sendJson({"explanation": "Tell me which network — example: explain MyWiFi"})
            return
        networks = scanWifi()
        anomalies = detectAnomalies(networks)
        self.sendJson({"explanation": explainNetwork(ssid, networks, anomalies)})

    # help stuff

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


def startWeb():
    port = config.webPort
    server = HTTPServer(("127.0.0.1", port), RequestHandler)
    print(f"\n  {config.appName}")
    print(f"  Web UI is live at http://localhost:{port}")
    print(f"  This only runs on your machine — nothing goes to the internet.")
    print(f"  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down. Stay safe out there.")
        server.server_close()
