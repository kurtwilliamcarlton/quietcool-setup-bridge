"""HA Ingress bridge for the ESPHome QuietCool captive portal.

The upstream device is fixed at 192.168.4.1 and access is restricted to
Home Assistant Supervisor Ingress. No passwords are stored or logged.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit

SUPERVISOR = "http://supervisor"
WLAN = "wlan0"
FALLBACK_SSID = "QuietCool Fallback"
NETWORK_BUSY = threading.Lock()


def supervisor_request(method, path, payload=None, timeout=10):
    token = os.getenv("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("Supervisor token not available")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    raw = None
    if payload is not None:
        raw = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(SUPERVISOR + path, headers=headers, data=raw, method=method)
    with urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read(131072))
    if result.get("result") != "ok":
        raise ValueError("Supervisor network request failed")
    return result.get("data", {})


def network_info():
    return supervisor_request("GET", "/network/info")


def ethernet_guard():
    """Require active, primary Ethernet with a configured IPv4 address."""
    interfaces = network_info().get("interfaces", [])
    ethernet = next((x for x in interfaces if x.get("interface") == "end0" and x.get("type") == "ethernet"), None)
    if not ethernet or not ethernet.get("connected") or not ethernet.get("enabled") or not ethernet.get("primary"):
        raise ValueError("Ethernet safety interlock: connect end0 Ethernet before configuring Wi-Fi")
    ipv4 = ethernet.get("ipv4") or {}
    if not ipv4.get("address") or not ipv4.get("ready"):
        raise ValueError("Ethernet safety interlock: end0 requires a ready IPv4 address")
    return ethernet


def ethernet_status():
    try:
        eth = ethernet_guard()
        return {"ethernet_ready": True, "ethernet_ip": (eth.get("ipv4") or {}).get("address", [""])[0], "ethernet_message": "Ethernet connected — Wi-Fi configuration permitted"}
    except (ValueError, RuntimeError, URLError, HTTPError, OSError):
        return {"ethernet_ready": False, "ethernet_ip": None, "ethernet_message": "Ethernet disconnected or unverified — Wi-Fi configuration locked"}


def checked_interfaces():
    ethernet = ethernet_guard()
    interfaces = network_info().get("interfaces", [])
    wifi = next((x for x in interfaces if x.get("interface") == WLAN and x.get("type") == "wireless" and not x.get("primary")), None)
    if not ethernet or not wifi:
        raise ValueError("Require active primary end0 Ethernet and secondary wlan0 Wi-Fi")
    return ethernet, wifi


def wifi_status():
    ethernet, wifi = checked_interfaces()
    active_ssid = (wifi.get("wifi") or {}).get("ssid") if wifi.get("connected") else None
    return {"ethernet": bool(ethernet.get("connected")), "wifi_enabled": bool(wifi.get("enabled")), "wifi_connected": bool(wifi.get("connected")), "ssid": active_ssid, "fallback_connected": active_ssid == FALLBACK_SSID}


def scan_fallback():
    checked_interfaces()
    data = supervisor_request("GET", "/network/interface/wlan0/accesspoints")
    accesspoints = data.get("accesspoints", [])
    return {"found": any(p.get("ssid") == FALLBACK_SSID for p in accesspoints if isinstance(p, dict))}


def connect_fallback(psk):
    _, wifi = checked_interfaces()
    if wifi.get("connected") and (wifi.get("wifi") or {}).get("ssid") not in (None, FALLBACK_SSID):
        raise ValueError("Wi-Fi currently uses another SSID; refusing to replace it")
    # Change only wlan0; keep end0 and the existing primary route untouched.
    supervisor_request("POST", "/network/interface/wlan0/update", {"enabled": True, "wifi": {"mode": "infrastructure", "auth": "wpa-psk", "ssid": FALLBACK_SSID, "psk": psk}, "ipv4": {"method": "auto"}, "ipv6": {"method": "disabled"}})
    return {"message": "Connection requested. Check status after several seconds."}


def disable_fallback():
    _, wifi = checked_interfaces()
    active_ssid = (wifi.get("wifi") or {}).get("ssid")
    if active_ssid not in (FALLBACK_SSID, None):
        raise ValueError("Refusing to disable wlan0 on an unrelated Wi-Fi network")
    # Disable wlan0 persistently: do not delete hardware and do not reconnect
    # to a later ESP32 fallback broadcast until explicitly re-enabled.
    supervisor_request("POST", "/network/interface/wlan0/update", {"enabled": False})
    return {"message": "Yellow wlan0 disabled. It will not rejoin QuietCool Fallback until you explicitly connect again."}

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
        if path == "/ethernet-status":
            return self.json(200, ethernet_status())
        if path == "/wifi-status":
            try:
                return self.json(200, {"ok": True, **wifi_status()})
            except (RuntimeError, ValueError, OSError, URLError, HTTPError):
                return self.json(503, {"ok": False, "message": "Supervisor Wi-Fi status unavailable"})
        if path == "/wifi-scan":
            try:
                return self.json(200, {"ok": True, **scan_fallback()})
            except (RuntimeError, ValueError, OSError, URLError, HTTPError):
                return self.json(503, {"ok": False, "message": "Unable to scan wlan0"})
        if path == "/status":
            if not ethernet_status()["ethernet_ready"]:
                return self.json(503, {"connected": False, "message": "Ethernet must be connected before device configuration"})
            try:
                info = get_config()
                return self.json(200, {"connected": True, "device": info})
            except (URLError, HTTPError, OSError, ValueError, UnicodeError, json.JSONDecodeError):
                return self.json(200, {"connected": False, "message": "QuietCool captive portal not reachable or not recognized at 192.168.4.1"})
        return self.reply(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if not self.allowed():
            return
        path = urlsplit(self.path).path
        if path not in ("/provision", "/wifi-connect", "/wifi-disconnect"):
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
            if path in ("/wifi-connect", "/wifi-disconnect", "/provision"):
                if not ethernet_status()["ethernet_ready"]:
                    return self.json(409, {"ok": False, "message": "Ethernet safety lock: plug Ethernet into the Yellow and wait for a valid Ethernet IP before using Wi-Fi setup."})
            if path in ("/wifi-connect", "/wifi-disconnect"):
                if not NETWORK_BUSY.acquire(blocking=False):
                    return self.json(409, {"ok": False, "message": "A Wi-Fi operation is already running"})
                try:
                    if path == "/wifi-disconnect":
                        if payload.get("confirm") is not True:
                            return self.json(400, {"ok": False, "message": "Confirm disconnect explicitly"})
                        result = disable_fallback()
                    else:
                        psk_fallback = payload.get("password")
                        if not isinstance(psk_fallback, str) or not (8 <= len(psk_fallback.encode("utf-8")) <= 63):
                            return self.json(400, {"ok": False, "message": "Fallback password must be 8-63 bytes"})
                        result = connect_fallback(psk_fallback)
                    return self.json(200, {"ok": True, **result})
                finally:
                    NETWORK_BUSY.release()
            ssid = payload.get("ssid")
            psk = payload.get("psk")
            if not isinstance(ssid, str) or not (1 <= len(ssid.encode("utf-8")) <= 32):
                return self.json(400, {"ok": False, "message": "SSID must be between 1 and 32 bytes"})
            if not isinstance(psk, str) or (psk and not (8 <= len(psk.encode("utf-8")) <= 63)):
                return self.json(400, {"ok": False, "message": "Password must be 8-63 bytes, or blank for an open network"})
            ethernet_guard()
            # Recheck identity at the instant of provisioning so we do not send
            # credentials to an unrelated device that also uses 192.168.4.1.
            get_config()
            ethernet_guard()
            query = urlencode({"ssid": ssid, "psk": psk})
            status, _, _ = device_request("/wifisave?" + query, timeout=7)
            if status != 200:
                raise ValueError("Unexpected ESPHome save response")
            return self.json(200, {"ok": True, "message": "Wi-Fi details sent. The ESP32 may leave its fallback Wi-Fi now. Check for quietcool.local on your home network."})
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
            return self.json(400, {"ok": False, "message": "Invalid settings or unexpected device at 192.168.4.1"})
        except (URLError, HTTPError, OSError, RuntimeError):
            return self.json(502, {"ok": False, "message": "Unable to reach the ESP32; it may have started switching networks. Check the home network before retrying."})


if __name__ == "__main__":
    print("QuietCool Setup Bridge listening for Home Assistant Ingress", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
