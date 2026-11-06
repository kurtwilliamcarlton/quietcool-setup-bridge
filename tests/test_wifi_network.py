"""Wi-Fi changes must be manual and restricted to secondary wlan0."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch

module_path = pathlib.Path(__file__).resolve().parents[1] / "quietcool_bridge" / "server.py"
spec = importlib.util.spec_from_file_location("quietcool_bridge_test", module_path)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

ETHERNET = {"interface": "end0", "type": "ethernet", "connected": True, "primary": True}
WIFI = {"interface": "wlan0", "type": "wireless", "enabled": True, "primary": False,
        "connected": False, "wifi": None}

class WifiBehaviorTests(unittest.TestCase):
    def test_status_never_attempts_connect(self):
        with patch.object(bridge, "network_info", return_value={"interfaces": [ETHERNET, WIFI]}), patch.object(bridge, "supervisor_request") as sup:
            status = bridge.wifi_status()
            self.assertFalse(status["fallback_connected"])
            sup.assert_not_called()

    def test_refuses_missing_ethernet(self):
        with patch.object(bridge, "network_info", return_value={"interfaces": [WIFI]}):
            with self.assertRaises(ValueError):
                bridge.connect_fallback("quietcool123")

    def test_scans_exact_ssid(self):
        with patch.object(bridge, "network_info", return_value={"interfaces": [ETHERNET, WIFI]}), patch.object(bridge, "supervisor_request", return_value={"accesspoints": [{"ssid": "Not QuietCool"}, {"ssid": "QuietCool Fallback"}]}) as sup:
            self.assertTrue(bridge.scan_fallback()["found"])
            sup.assert_called_once_with("GET", "/network/interface/wlan0/accesspoints")

    def test_manual_connect_only_changes_wlan0(self):
        with patch.object(bridge, "network_info", return_value={"interfaces": [ETHERNET, WIFI]}), patch.object(bridge, "supervisor_request", return_value={}) as sup:
            bridge.connect_fallback("examplepass123")
            method, path, payload = sup.call_args.args
            self.assertEqual((method, path), ("POST", "/network/interface/wlan0/update"))
            self.assertEqual(payload["wifi"]["ssid"], "QuietCool Fallback")
            self.assertEqual(payload["wifi"]["psk"], "examplepass123")
            self.assertTrue(payload["enabled"])

    def test_disable_is_persistent_and_does_not_touch_ethernet(self):
        connected = dict(WIFI, connected=True, wifi={"ssid": "QuietCool Fallback"})
        with patch.object(bridge, "network_info", return_value={"interfaces": [ETHERNET, connected]}), patch.object(bridge, "supervisor_request", return_value={}) as sup:
            bridge.disable_fallback()
            sup.assert_called_once_with("POST", "/network/interface/wlan0/update", {"enabled": False})

    def test_does_not_disable_other_wifi(self):
        connected = dict(WIFI, connected=True, wifi={"ssid": "Another Wi-Fi"})
        with patch.object(bridge, "network_info", return_value={"interfaces": [ETHERNET, connected]}), patch.object(bridge, "supervisor_request") as sup:
            with self.assertRaises(ValueError):
                bridge.disable_fallback()
            sup.assert_not_called()

if __name__ == "__main__":
    unittest.main()
