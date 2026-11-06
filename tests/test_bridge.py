"""Local unit tests: fake upstream; no real network or ESP32 required."""
import importlib.util
import json
import pathlib
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "quietcool_bridge" / "server.py"
spec = importlib.util.spec_from_file_location("quietcool_setup_bridge", MODULE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

DEVICE_JSON = {
    "name": "quietcool",
    "mac": "AA:BB:CC:DD:EE:01",
    "aps": [{}, {"ssid": "ExampleHome", "rssi": -52, "lock": True}],
}


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:%d" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def fake_request(self, path, timeout=5):
        if path == "/config.json":
            return (200, {}, json.dumps(DEVICE_JSON).encode())
        if path.startswith("/wifisave?"):
            return (200, {}, b"Saved. Connecting...")
        raise ValueError("unexpected upstream path")

    def test_assets(self):
        for path in ("/", "/app.css", "/app.js", "/healthz"):
            with urlopen(self.url + path, timeout=5) as response:
                self.assertEqual(response.status, 200)

    def test_status(self):
        with patch.object(bridge, "ethernet_status", return_value={"ethernet_ready": True}), patch.object(bridge, "device_request", self.fake_request):
            with urlopen(self.url + "/status", timeout=5) as response:
                data = json.load(response)
        self.assertTrue(data["connected"])
        self.assertEqual(data["device"]["name"], "quietcool")
        self.assertEqual(data["device"]["aps"][0]["ssid"], "ExampleHome")

    def test_unexpected_device_is_rejected(self):
        fake = dict(DEVICE_JSON, name="other-device")
        with patch.object(bridge, "ethernet_status", return_value={"ethernet_ready": True}), patch.object(bridge, "device_request", return_value=(200, {}, json.dumps(fake).encode())):
            with urlopen(self.url + "/status", timeout=5) as response:
                self.assertFalse(json.load(response)["connected"])

    def post(self, obj):
        req = Request(self.url + "/provision", json.dumps(obj).encode(),
                      {"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_provision(self):
        calls = []
        def record(path, timeout=5):
            calls.append(path)
            return self.fake_request(path, timeout)
        with patch.object(bridge, "ethernet_status", return_value={"ethernet_ready": True}), patch.object(bridge, "ethernet_guard", return_value={}), patch.object(bridge, "device_request", record):
            status, data = self.post({"ssid": "ExampleHome", "psk": "samplepass123", "expected_mac": "AA:BB:CC:DD:EE:01"})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertIn("/wifisave?", calls[-1])
        self.assertIn("psk=samplepass123", calls[-1])
        self.assertNotIn("samplepass123", json.dumps(data))

    def test_mismatched_mac_blocks_password_submission(self):
        sent = []
        def record(path, timeout=5):
            sent.append(path)
            return self.fake_request(path, timeout)
        with patch.object(bridge, "ethernet_status", return_value={"ethernet_ready": True}), patch.object(bridge, "ethernet_guard", return_value={}), patch.object(bridge, "device_request", record):
            status, data = self.post({"ssid": "ExampleHome", "psk": "samplepass123", "expected_mac": "AA:BB:CC:DD:EE:02"})
        self.assertEqual(status, 409)
        self.assertFalse(data["ok"])
        self.assertFalse(any(p.startswith("/wifisave?") for p in sent))

    def test_missing_mac_requires_reidentify(self):
        with patch.object(bridge, "ethernet_status", return_value={"ethernet_ready": True}), patch.object(bridge, "ethernet_guard", return_value={}), patch.object(bridge, "device_request") as upstream:
            status, data = self.post({"ssid": "ExampleHome", "psk": "samplepass123"})
            self.assertEqual(status, 409)
            upstream.assert_not_called()

    def test_unplugged_ethernet_blocks_provision(self):
        with patch.object(bridge, "ethernet_status", return_value={"ethernet_ready": False}), patch.object(bridge, "device_request") as upstream:
            status, data = self.post({"ssid": "ExampleHome", "psk": "samplepass123"})
            self.assertEqual(status, 409)
            self.assertFalse(data["ok"])
            upstream.assert_not_called()

    def test_unplugged_ethernet_blocks_connect(self):
        with patch.object(bridge, "ethernet_status", return_value={"ethernet_ready": False}), patch.object(bridge, "supervisor_request") as upstream:
            req = Request(self.url + "/wifi-connect", json.dumps({"password":"samplepass123"}).encode(), {"Content-Type":"application/json"}, method="POST")
            with self.assertRaises(HTTPError) as e:
                urlopen(req, timeout=5)
            self.assertEqual(e.exception.code, 409)
            upstream.assert_not_called()

    def test_reject_short_psk(self):
        with patch.object(bridge, "ethernet_status", return_value={"ethernet_ready": True}):
            status, data = self.post({"ssid": "ExampleHome", "psk": "short"})
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    def test_existing_quietcool_esp_home_entry(self):
        entries = [
            {"domain": "esphome", "title": "QuietCool Attic", "state": "loaded"},
            {"domain": "esphome", "title": "Kitchen sensor", "state": "loaded"},
        ]
        with patch.object(bridge, "core_rest_get", return_value=entries):
            status = bridge.existing_quietcool()
        self.assertTrue(status["available"])
        self.assertTrue(status["configured"])
        self.assertEqual(len(status["entries"]), 1)
        self.assertEqual(status["entries"][0]["title"], "QuietCool Attic")

    def test_existing_device_unavailable_is_not_missing(self):
        with patch.object(bridge, "core_rest_get", side_effect=RuntimeError("No token")):
            status = bridge.existing_quietcool()
        self.assertFalse(status["available"])
        self.assertFalse(status["configured"])
        self.assertIn("unavailable", status["message"])

    def test_existing_device_endpoint(self):
        with patch.object(bridge, "existing_quietcool", return_value={"available": True, "configured": False, "entries": [], "message": "No matching device"}):
            with urlopen(self.url + "/existing-device", timeout=5) as response:
                status = json.load(response)
        self.assertFalse(status["configured"])
        self.assertTrue(status["ok"])

    def test_reject_other_path(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + "/provision", timeout=5)
        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
