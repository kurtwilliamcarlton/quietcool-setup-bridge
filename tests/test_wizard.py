"""Automatic QuietCool LAN discovery: scoped probes, identity and safe failures."""
import importlib.util
import pathlib
import socket
import unittest
from unittest.mock import MagicMock, patch

path=pathlib.Path(__file__).resolve().parents[1]/"quietcool_bridge"/"server.py"
spec=importlib.util.spec_from_file_location("quietcool_auto_discovery",path)
bridge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
ETH={"interface":"end0","type":"ethernet","connected":True,"enabled":True,"primary":True,"ipv4":{"ready":True,"address":["192.168.33.202/24"]}}

class WizardDiscoveryTests(unittest.TestCase):
    def test_dns_candidate_found_without_manual_ip(self):
        dns=[(socket.AF_INET,socket.SOCK_STREAM,6,"",("192.168.33.167",80))]
        with patch.object(bridge,"ethernet_guard",return_value=ETH), \
             patch.object(bridge.socket,"getaddrinfo",return_value=dns), \
             patch.object(bridge,"_probe_quietcool",return_value="192.168.33.167") as probe:
            result=bridge.discover_lan_device()
        self.assertTrue(result["verified"])
        self.assertEqual(result["ip"],"192.168.33.167")
        probe.assert_called_once_with(bridge.ipaddress.IPv4Address("192.168.33.167"),trusted_hostname=True)

    def test_off_lan_dns_result_is_ignored(self):
        dns=[(socket.AF_INET,socket.SOCK_STREAM,6,"",("10.20.30.40",80))]
        with patch.object(bridge,"ethernet_guard",return_value=ETH), \
             patch.object(bridge.socket,"getaddrinfo",return_value=dns), \
             patch.object(bridge,"_probe_quietcool",return_value=None) as probe:
            result=bridge.discover_lan_device()
        self.assertFalse(result["verified"])
        self.assertNotIn("10.20.30.40",[str(c.args[0]) for c in probe.call_args_list])

    def test_multiple_matches_are_not_assumed_same_device(self):
        with patch.object(bridge,"ethernet_guard",return_value=ETH), \
             patch.object(bridge.socket,"getaddrinfo",side_effect=OSError()), \
             patch.object(bridge,"_probe_quietcool",side_effect=lambda ip, trusted_hostname=False: str(ip) if str(ip) in ("192.168.33.167","192.168.33.168") else None):
            result=bridge.discover_lan_device()
        self.assertFalse(result["verified"])
        self.assertIn("More than one",result["message"])

    def test_subnet_scan_rejected_above_256_addresses(self):
        big=dict(ETH,ipv4={"address":["192.168.32.202/23"],"ready":True})
        with patch.object(bridge,"ethernet_guard",return_value=big):
            with self.assertRaises(ValueError):
                bridge.discover_lan_device()

    def test_probe_requires_api_and_web(self):
        web=MagicMock()
        web.getresponse.return_value.status=200
        web.getresponse.return_value.getheader.return_value="text/html"
        web.getresponse.return_value.read.return_value=b"<html>QuietCool controller</html>"
        with patch.object(bridge.socket,"create_connection") as tcp, \
             patch.object(bridge.http.client,"HTTPConnection",return_value=web):
            self.assertEqual(bridge._probe_quietcool("192.168.33.167"),"192.168.33.167")
        tcp.assert_called_once_with(("192.168.33.167",6053),timeout=0.9)

    def test_nonquietcool_page_does_not_match(self):
        web=MagicMock()
        web.getresponse.return_value.status=200
        web.getresponse.return_value.getheader.return_value="text/html"
        web.getresponse.return_value.read.return_value=b"<html>Another device</html>"
        with patch.object(bridge.socket,"create_connection"), \
             patch.object(bridge.http.client,"HTTPConnection",return_value=web), \
             patch.object(bridge.socket,"gethostbyaddr",side_effect=OSError()):
            self.assertIsNone(bridge._probe_quietcool("192.168.33.168"))

if __name__=="__main__":
    unittest.main()
