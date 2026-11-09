# Changelog

## 1.7.0 — fail-closed bridge hardening

- Require an active secondary wlan0 connection to QuietCool Fallback before identifying the ESP32 or sending Wi-Fi credentials, in addition to the existing primary Ethernet safety check.
- Reject Wi-Fi provisioning with a clear HTTP 409 response when fallback is disconnected.
- Recheck fallback immediately before sending credentials, reducing the risk of routing to an unrelated device.
- Isolate individual LAN discovery probe failures so a single faulty or unreachable LAN host cannot abort the scan.
- Preserve manual connection, MAC comparison, and explicit Wi-Fi cleanup.

## 1.6.0 — recognize existing QuietCool devices

- Step 3 checks Home Assistant for existing ESPHome integration entries named QuietCool and displays their status.
- The wizard separately searches for the ESP32's fallback Wi-Fi and offers Connect & Reconfigure after explicit user approval.
- If the Core API is inaccessible or the device has been renamed, the UI states that status is unknown rather than claiming the device is absent.
- Existing configuration checks are read-only; device changes require the usual intentional connection and provisioning steps.
- Enable the required Home Assistant Core API permission for this optional integration-status feature.

## 1.5.0 — reliability and safety

- Record ESP32 MAC during the identification step and recheck its captive-portal MAC immediately before sending home Wi-Fi credentials. Reject changed/missing identities with HTTP 409.
- Improve troubleshooting text when home-network discovery fails.
- Add a polished completion view showing discovered LAN IP, recorded setup MAC, and temporary Wi-Fi cleanup status.
- Add a **Set up another device** button that resets wizard state without reconnecting the Yellow's Wi-Fi automatically.
- Preserve manual confirmation before disabling temporary Yellow wlan0 Wi-Fi.
- Do not claim that port checks prove the same ESP32 MAC or that Home Assistant has registered the ESPHome integration.

## 1.4.0 — automatic home-network verification

- Remove the manual IP-address field from the final wizard step.
- Automatically retry discovery after saving the ESP32's new home Wi-Fi settings.
- Try quietcool.local and scan only the Yellow Ethernet IPv4 subnet (up to /24).
- Require ESPHome API and web-server responses, plus QuietCool web/hostname identification.
- Display the discovered IP automatically or a helpful retry message.
- Retain the explicit secondary Wi-Fi disable step and all Ethernet safety interlocks.

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
