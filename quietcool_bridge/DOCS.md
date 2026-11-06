# QuietCool Setup Bridge — Home Assistant App

This app is a **prototype** for configuring ESPHome's captive-portal Wi-Fi on a QuietCool controller from within Home Assistant Yellow.

## Before starting

1. Connect the Yellow to the home network over Ethernet.
2. Connect its separate Wi-Fi interface to **QuietCool Fallback**.
3. Confirm the Yellow's Wi-Fi interface has an address in `192.168.4.0/24` and `curl -i http://192.168.4.1/config.json` returns an ESPHome JSON response for `quietcool`.
4. Launch this app through **Open Web UI** in Home Assistant (Ingress).

## Provisioning

1. Select **Check connection**. Confirm the device is reachable and that the displayed device MAC matches your QuietCool controller.
2. Select a 2.4 GHz Wi-Fi network the ESP32 sees, or enter its name.
3. Enter that network's password and select **Save Wi-Fi to ESP32**.
4. The ESP32 will attempt to connect. Its fallback Wi-Fi may disappear as part of normal setup.
5. Confirm the ESP32 is reachable on the home network, e.g. `quietcool.local` or its new router-assigned IP.

## Troubleshooting

- **Device not reachable:** Check `ha network info`; verify `wlan0` joins `QuietCool Fallback` and that the Home Assistant host reaches `192.168.4.1`.
- **Host reaches ESP32 but app does not:** App containers can have different routing. Check app logs and whether Docker container traffic can reach the ESP32 AP subnet.
- **Wrong device identity:** Only `name: quietcool` in `/config.json` is accepted; the MAC is displayed for visual verification.
- **Disconnected after saving:** The ESP32 likely switched to the home network. Check your router and Home Assistant's ESPHome integration.

## Security / constraints

The browser submits credentials to the app using POST, but the ESPHome captive portal requires credentials via HTTP GET and the AP link is not HTTPS. **No credentials are persisted by this app**. Treat device identity as unverified until you confirm the physical AP and MAC. Avoid exposing the fallback AP beyond trusted users.

This version is limited to Home Assistant Yellow / aarch64 and one ESPHome QuietCool device at `192.168.4.1`.