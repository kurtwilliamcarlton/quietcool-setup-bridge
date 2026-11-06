# QuietCool Setup Bridge

Experimental Home Assistant OS app to provision a **QuietCool ESPHome controller** over its **QuietCool Fallback** Wi-Fi network, without moving your phone or computer off the main LAN.

**Status: v1.0 prototype.** Validated with local simulated tests, but not yet verified by installing the app on a Home Assistant Yellow. Use with a device you control.

## What it does

- Shows whether an ESPHome captive portal named `quietcool` can be reached at `192.168.4.1`.
- Shows the ESP32 MAC address and networks detected by the ESP32.
- Accepts Wi-Fi credentials inside Home Assistant's authenticated app interface (Ingress).
- Sends credentials to the ESP32's built-in Wi-Fi setup endpoint without uploading firmware or changing its fan-control firmware.

This is a **purpose-built provisioning form**, not a pixel-for-pixel proxy of the ESPHome captive portal.

## Architecture

```text
Phone / computer --(Home Assistant login)--> Home Assistant Yellow
                                              | Ethernet: home LAN
                                              | Wi-Fi: QuietCool Fallback
                                              v
                                       ESP32 at 192.168.4.1
                                       /config.json, /wifisave
```

The app deliberately targets **one fixed address** and requires the captive portal to identify itself as `quietcool`. No arbitrary target URL can be supplied.

## Requirements

- Home Assistant OS on **aarch64** hardware (tested configuration target: Home Assistant Yellow).
- The host remains on the LAN via Ethernet and separately joins `QuietCool Fallback` via Wi-Fi.
- Host can reach `http://192.168.4.1/config.json` over that Wi-Fi connection.
- QuietCool ESPHome firmware exposes `captive_portal` and identifies itself as `quietcool`.

To verify the network from the Terminal & SSH app:

```sh
ha network info
curl -sS --compressed --max-time 10 http://192.168.4.1/config.json
```

## Install during private development

Private GitHub repositories cannot be cloned anonymously by Home Assistant's app store. For initial private testing, copy `quietcool_bridge/` into `/local_apps/` on the Home Assistant host, then refresh **Settings → Apps → Install app** and install **QuietCool Setup Bridge** under Local apps.

**Do not place the app folder inside `/config/esphome/`.** It is a Home Assistant app, not an ESPHome external component.

See [App documentation](quietcool_bridge/DOCS.md) for setup and troubleshooting.

## Install as a GitHub app repository (when made public)

1. In Home Assistant, go to **Settings → Apps → Install app**.
2. Use the upper-right **Repositories** menu.
3. Add `https://github.com/kurtwilliamcarlton/quietcool-setup-bridge`.
4. Select **QuietCool Setup Bridge**, install, start, and open its Web UI.

A root-level `repository.yaml` tells Home Assistant where to find this app. A private repo may need to stay in local-app development mode until you choose to make it publicly accessible.

## Security notes

- Browser-to-bridge provisioning uses **POST** and avoids putting Wi-Fi passwords in your browser URL; the upstream ESPHome `/wifisave` endpoint still receives credentials in a **GET query** over **unencrypted HTTP**. Keep this communication on a trusted local network.
- ESPHome device name and MAC are **not cryptographic authentication**. Verify the Yellow is connected to the intended fallback AP before sending credentials.
- The app does not retain Wi-Fi credentials; it suppresses HTTP access logs. Avoid sharing raw network traces or ESPHome logs that could contain sensitive information.
- Do not expose the bridge outside Home Assistant Ingress or expose the ESP32 fallback AP to untrusted users.
- The app intentionally does **not** provide firmware upload, general HTTP proxying, or QuietCool fan controls.

## Development

```sh
python3 -m unittest discover -s tests -v
```

The tests simulate the ESPHome captive portal; they do not replace on-device testing.

## Files

- `repository.yaml` — Home Assistant app repository metadata.
- `quietcool_bridge/config.yaml` — App definition for Home Assistant OS (aarch64).
- `quietcool_bridge/Dockerfile`, `quietcool_bridge/run.sh` — App runtime.
- `quietcool_bridge/server.py` — Small Ingress web server / ESPHome captive-portal client.
- `quietcool_bridge/dashboard.html`, `app.js`, `app.css` — Provisioning interface.
- `tests/` — Isolated tests.

**License:** No open-source license has been selected. All rights reserved by default until the repository owner chooses one.
## v1.1 development: temporary access-point connection

The Home Assistant Yellow remains on **primary Ethernet (end0)**. The bridge can scan Wi-Fi networks using the Supervisor API, then connect secondary Wi-Fi (wlan0) to the exact `QuietCool Fallback` SSID after an explicit button press. There is **no automatic reconnection or background auto-connect** code in the bridge.

**Finish setup:** After saving the ESP32's home Wi-Fi credentials and independently confirming the ESP32 is accessible on the home LAN, press **Disconnect & Disable Yellow Wi-Fi**. This uses the Supervisor network API to persistently set `wlan0.enabled=false`. It does **not** delete the adapter or remove Ethernet, but prevents the Yellow from automatically rejoining the fallback access point if the ESP32 is reset later. If you skip this step, a saved Wi-Fi profile could reconnect; the bridge does not claim to prevent this until the interface is disabled.

**To connect again later:** Re-enable wlan0 with the Connect button or in Home Assistant's Network settings. The app requires Supervisor manager-role networking permissions, so only trusted administrators should access it. This is experimental and has not been hardware-tested. Verify Ethernet connectivity before making Wi-Fi changes.

## v1.2 Ethernet safety interlock

The app checks the Supervisor network status for **end0**, requiring it to be the enabled, connected, primary Ethernet interface with a ready IPv4 address. The dashboard shows **Ethernet connected — Wi-Fi configuration permitted** when ready, and **Ethernet disconnected or unverified — Wi-Fi configuration locked** otherwise. Connecting to fallback Wi-Fi, scanning for it, disconnecting wlan0, and sending new ESP32 Wi-Fi settings are blocked while the lock is active. The server rechecks for each operation, independently of the dashboard; a disconnected cable or unavailable Supervisor API means **no Wi-Fi setup**. This does not change other Home Assistant services, only bridge functions.
