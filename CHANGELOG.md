# Changelog

## 1.3.0 — guided setup wizard

- Replace the single-page tool with six guided screens: introduction, Ethernet safety, fallback connection, ESP32 identity, Wi-Fi provisioning, and LAN verification/cleanup.
- Gate Next until each prerequisite completes.
- Final step verifies a device at a numeric IPv4 address on the Ethernet subnet via web port 80 and ESPHome native API port 6053.
- Explain that network checks are not equivalent to registering the ESPHome integration in Home Assistant.
- Maintain manual-only fallback connection and persistent wlan0 disable to avoid automatic reconnection.
- Keep credentials in transient form data, not in browser URLs or storage.

## 1.2.0 — Ethernet safety interlock

- Require primary Ethernet end0 connected and enabled with a ready IPv4 address before scanning for fallback Wi-Fi, connecting, disabling Wi-Fi, or provisioning ESP32 credentials.
- Show Ethernet readiness and lock the setup buttons if disconnected.
- Recheck on page focus and every 10 seconds; server rejects bypassed requests with HTTP 409.
- Fail closed if Supervisor's Ethernet status cannot be confirmed.
- Manual-only Wi-Fi behavior from v1.1 is unchanged.

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
