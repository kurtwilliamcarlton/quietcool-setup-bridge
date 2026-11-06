# Changelog

## 1.1.0 — experimental

- Add manual **Find QuietCool Fallback** scan from Home Assistant Yellow wlan0.
- Add explicit **Connect Yellow to QuietCool** action; never auto-connect on bridge startup.
- Add **Disconnect & Disable Yellow Wi-Fi** action that sets wlan0 enabled=false through the Supervisor API.
- Refuse Wi-Fi changes when the primary Ethernet (end0) connection is absent.
- The cleanup action must be invoked only **after** verifying that QuietCool is reachable on the normal home LAN. It does not run automatically.
- ESP32 factory reset does not trigger reconnection from the bridge; disabling wlan0 also prevents automatic reconnection by the host.
- Still requires real hardware validation on Home Assistant Yellow.

## 1.0.0

- Initial Home Assistant Ingress provisioning app.
- Identify the ESPHome captive portal, list networks, and submit Wi-Fi credentials.
