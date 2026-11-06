"""HA Ingress bridge for the ESPHome QuietCool captive portal.

The upstream device is fixed at 192.168.4.1 and access is restricted to
Home Assistant Supervisor Ingress. No passwords are stored or logged.
"""
from __future__ import annotations

import gzip
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
PORT = int(os.getenv("PORT", "8099"))
DEVICE = "http://192.168.4.1"
EXPECTED_NAME = "quietcool"
# App ingress requests originate from the Supervisor proxy.
ALLOWED_CLIENTS = {"172.30.32.2", "127.0.0.1", "::1"}
MAX_BODY = 2048
MAX_UPSTREAM = 65536


def device_request(path: str, timeout: float = 5.0):
    if path != "/config.json" and not path.startswith("/wifisave?"):
        raise ValueError("Upstream path not permitted")
    request = Request(DEVICE + path, headers={"Accept-Encoding": "gzip", "User-Agent": "QuietCoolSetupBridge/1.0"})
    with urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_UPSTREAM + 1)
        if len(data) > MAX_UPSTREAM:
            raise ValueError("Oversized device reply")
        return response.status, dict(response.headers), data


def get_config():
    status, headers, raw = device_request("/config.json")
    if status != 200:
        raise ValueError("Unexpected device status")
    if headers.get("Content-Encoding", "").lower() == "gzip":
        raw = gzip.decompress(raw)
        if len(raw) > 262144:
            raise ValueError("Oversized decompressed reply")
    info = json.loads(raw)
    if not isinstance(info, dict) or not isinstance(info.get("aps"), list):
        raise ValueError("Unexpected ESPHome captive portal response")
    name = info.get("name")
    if not isinstance(name, str) or name.lower() != EXPECTED_NAME:
        raise ValueError("Unexpected device name")
    mac = info.get("mac", "")
    if not isinstance(mac, str) or not re.fullmatch(r"[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}", mac):
        raise ValueError("Unexpected device MAC")
    aps = []
    for ap in info["aps"][:100]:
        if not isinstance(ap, dict):
            continue
        ssid = ap.get("ssid")
        if isinstance(ssid, str) and ssid and len(ssid.encode("utf-8")) <= 32:
            strength = ap.get("rssi")
            aps.append({"ssid": ssid, "rssi": strength if type(strength) in (int, float) else None,
                        "lock": bool(ap.get("lock"))})
    return {"name": name, "mac": mac.upper(), "aps": aps[:50]}


class Handler(BaseHTTPRequestHandler):
    server_version = "QuietCoolSetupBridge/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # A Wi-Fi password must never appear in app logs.
        pass

    def reply(self, status: int, data: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def json(self, status: int, payload: dict):
        self.reply(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def allowed(self) -> bool:
        if self.client_address[0] not in ALLOWED_CLIENTS:
            self.reply(403, b"Use Home Assistant Ingress.", "text/plain; charset=utf-8")
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        path = urlsplit(self.path).path
        files = {"/": ("dashboard.html", "text/html; charset=utf-8"),
                 "/index.html": ("dashboard.html", "text/html; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/app.css": ("app.css", "text/css; charset=utf-8")}
        if path in files:
            name, kind = files[path]
            return self.reply(200, (ROOT / name).read_bytes(), kind)
        if path == "/healthz":
            return self.json(200, {"ok": True})
        if path == "/status":
            try:
                info = get_config()
                return self.json(200, {"connected": True, "device": info})
            except (URLError, HTTPError, OSError, ValueError, UnicodeError, json.JSONDecodeError):
                return self.json(200, {"connected": False, "message": "QuietCool captive portal not reachable or not recognized at 192.168.4.1"})
        return self.reply(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if not self.allowed():
            return
        if urlsplit(self.path).path != "/provision":
            return self.json(405, {"ok": False, "message": "Endpoint not available"})
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            return self.json(415, {"ok": False, "message": "Expected JSON request"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.json(400, {"ok": False, "message": "Invalid request length"})
        if length < 1 or length > MAX_BODY:
            return self.json(413, {"ok": False, "message": "Invalid request length"})
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Invalid JSON body")
            ssid = payload.get("ssid")
            psk = payload.get("psk")
            if not isinstance(ssid, str) or not (1 <= len(ssid.encode("utf-8")) <= 32):
                return self.json(400, {"ok": False, "message": "SSID must be between 1 and 32 bytes"})
            if not isinstance(psk, str) or (psk and not (8 <= len(psk.encode("utf-8")) <= 63)):
                return self.json(400, {"ok": False, "message": "Password must be 8-63 bytes, or blank for an open network"})
            # Recheck identity at the instant of provisioning so we do not send
            # credentials to an unrelated device that also uses 192.168.4.1.
            get_config()
            query = urlencode({"ssid": ssid, "psk": psk})
            status, _, _ = device_request("/wifisave?" + query, timeout=7)
            if status != 200:
                raise ValueError("Unexpected ESPHome save response")
            return self.json(200, {"ok": True, "message": "Wi-Fi details sent. The ESP32 may leave its fallback Wi-Fi now. Check for quietcool.local on your home network."})
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
            return self.json(400, {"ok": False, "message": "Invalid settings or unexpected device at 192.168.4.1"})
        except (URLError, HTTPError, OSError):
            return self.json(502, {"ok": False, "message": "Unable to reach the ESP32; it may have started switching networks. Check the home network before retrying."})


if __name__ == "__main__":
    print("QuietCool Setup Bridge listening for Home Assistant Ingress", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
