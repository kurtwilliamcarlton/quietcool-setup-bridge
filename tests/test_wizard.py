"""Verify the guided setup's LAN safety boundary and HTTP outcome."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch, MagicMock
from ipaddress import IPv4Address

module_path=pathlib.Path(__file__).resolve().parents[1]/"quietcool_bridge"/"server.py"
spec=importlib.util.spec_from_file_location("bridge_wizard",module_path)
bridge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
ETH={"interface":"end0","type":"ethernet","connected":True,"enabled":True,"primary":True,"ipv4":{"ready":True,"address":["192.168.33.202/24"]}}

class WizardTests(unittest.TestCase):
    def test_reject_out_of_subnet(self):
        with patch.object(bridge,"ethernet_guard",return_value=ETH):
            with self.assertRaises(ValueError):
                bridge.verify_lan_device("10.0.0.99")

    def test_reject_fallback_ap(self):
        with patch.object(bridge,"ethernet_guard",return_value=ETH):
            with self.assertRaises(ValueError):
                bridge.verify_lan_device("192.168.4.1")

    def test_reject_own_ethernet_address(self):
        with patch.object(bridge,"ethernet_guard",return_value=ETH):
            with self.assertRaises(ValueError):
                bridge.verify_lan_device("192.168.33.202")

    def test_lan_verification_requires_web_and_api(self):
        fake_socket=MagicMock()
        fake_conn=MagicMock()
        fake_conn.getresponse.return_value.status=200
        fake_conn.getresponse.return_value.read.return_value=b"<html>ESPHome</html>"
        with patch.object(bridge,"ethernet_guard",return_value=ETH), \
             patch.object(bridge.socket,"create_connection",return_value=fake_socket) as tcp, \
             patch.object(bridge.http.client,"HTTPConnection",return_value=fake_conn):
            result=bridge.verify_lan_device("192.168.33.167")
        self.assertTrue(result["verified"])
        tcp.assert_called_once_with(("192.168.33.167",6053),timeout=2.5)
        self.assertIn("Add the ESPHome integration",result["message"])

    def test_web_server_failure_blocks_success(self):
        fake_conn=MagicMock()
        fake_conn.getresponse.return_value.status=404
        with patch.object(bridge,"ethernet_guard",return_value=ETH), \
             patch.object(bridge.socket,"create_connection"), \
             patch.object(bridge.http.client,"HTTPConnection",return_value=fake_conn):
            with self.assertRaises(ValueError):
                bridge.verify_lan_device("192.168.33.167")

if __name__=="__main__":
    unittest.main()
