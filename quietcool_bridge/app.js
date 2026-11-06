'use strict';
const $ = id => document.getElementById(id);
let currentNetworks = [];
async function refreshDevice() {
  $('checkBtn').disabled = true;
  $('statusBadge').className = 'pill waiting';
  $('statusBadge').textContent = 'Checking…';
  try {
    const res = await fetch('status', {cache: 'no-store'});
    const data = await res.json();
    if (!data.connected) throw new Error(data.message || 'No response');
    $('statusBadge').className = 'pill online';
    $('statusBadge').textContent = 'Device reachable';
    $('deviceName').textContent = data.device.name || '—';
    $('deviceMac').textContent = data.device.mac || '—';
    $('statusText').textContent = 'ESPHome captive portal is responding. Ready for Wi-Fi setup.';
    currentNetworks = data.device.aps || [];
    const selector = $('networks');
    selector.replaceChildren(new Option('Select network (optional)', ''));
    const unique = new Set();
    for (const net of currentNetworks) {
      if (!net.ssid || unique.has(net.ssid)) continue;
      unique.add(net.ssid);
      const strength = typeof net.rssi === 'number' ? ` (${net.rssi} dBm)` : '';
      selector.add(new Option(net.ssid + strength, net.ssid));
    }
  } catch (err) {
    $('statusBadge').className = 'pill offline';
    $('statusBadge').textContent = 'Not reachable';
    $('deviceName').textContent = '—';
    $('deviceMac').textContent = '—';
    $('statusText').textContent = 'Check that Home Assistant Yellow is joined to QuietCool Fallback and has a 192.168.4.x Wi-Fi address.';
  } finally {
    $('checkBtn').disabled = false;
  }
}
$('checkBtn').addEventListener('click', refreshDevice);
$('networks').addEventListener('change', e => { if (e.target.value) $('ssid').value = e.target.value; });
$('showPassword').addEventListener('change', e => { $('psk').type = e.target.checked ? 'text' : 'password'; });
$('setupForm').addEventListener('submit', async e => {
  e.preventDefault();
  const ssid = $('ssid').value;
  const psk = $('psk').value;
  const msg = $('saveResult');
  if (!ssid.trim()) return;
  const ok = window.confirm(`Send Wi-Fi credentials for “${ssid}” to the QuietCool device? The fallback network may disconnect.`);
  if (!ok) return;
  $('submitBtn').disabled = true;
  msg.className = 'result';
  try {
    const res = await fetch('provision', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ssid, psk}), cache:'no-store'});
    const data = await res.json();
    msg.className = data.ok ? 'result ok' : 'result error';
    msg.textContent = data.message || 'No response';
    if (data.ok) $('psk').value = '';
  } catch (err) {
    msg.className = 'result error';
    msg.textContent = 'Could not confirm the change. Check whether the ESP32 has already joined your home Wi-Fi.';
  } finally {
    $('submitBtn').disabled = false;
  }
});
refreshDevice();

async function refreshYellowWifi() {
  try {
    const response = await fetch('wifi-status', {cache:'no-store'});
    const data = await response.json();
    $('yellowWifiStatus').textContent = data.ok
      ? ('Yellow wlan0: ' + (data.wifi_enabled ? (data.wifi_connected ? ('Connected to ' + (data.ssid || 'unknown network')) : 'Enabled, not connected') : 'Disabled — automatic reconnection prevented'))
      : (data.message || 'Network information unavailable');
  } catch (_) {
    $('yellowWifiStatus').textContent = 'Unable to read Yellow network status';
  }
}
function wifiMessage(message, good) {
  const el = $('wifiActionResult');
  el.className = good ? 'result ok' : 'result error';
  el.textContent = message;
}
async function wifiPost(path, payload) {
  try {
    const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload), cache:'no-store'});
    const data = await response.json();
    wifiMessage(data.message || (data.ok ? 'Operation requested' : 'Operation failed'), !!data.ok);
  } catch (_) {
    wifiMessage('Wi-Fi operation failed; check Home Assistant Network settings.', false);
  }
  await refreshYellowWifi();
}
$('scanFallback').addEventListener('click', async () => {
  $('scanResult').textContent = 'Scanning…';
  try {
    const response = await fetch('wifi-scan', {cache:'no-store'});
    const data = await response.json();
    $('scanResult').textContent = data.ok ? (data.found ? 'QuietCool Fallback found' : 'Not found nearby') : (data.message || 'Scan failed');
  } catch (_) {
    $('scanResult').textContent = 'Scan failed';
  }
});
$('connectFallback').addEventListener('click', async () => {
  const password = $('fallbackPassword').value;
  if (!password) return wifiMessage('Enter the temporary fallback Wi-Fi password.', false);
  if (!window.confirm('Connect Yellow wlan0 to QuietCool Fallback? Ethernet will remain primary.')) return;
  await wifiPost('wifi-connect', {password});
  $('fallbackPassword').value = '';
});
$('disconnectFallback').addEventListener('click', async () => {
  if (!window.confirm('Have you verified QuietCool is reachable on the normal home network? Disable Yellow wlan0 and prevent future automatic reconnection?')) return;
  await wifiPost('wifi-disconnect', {confirm:true});
});
refreshYellowWifi();

let ethernetReady = false;
function applyEthernetLock(ready, message) {
  ethernetReady = ready;
  $('ethernetGuard').textContent = ready
    ? '✓ ' + message
    : '⚠ ' + message + '. Plug Ethernet into the Yellow, then click Recheck Ethernet.';
  for (const id of ['scanFallback', 'connectFallback', 'disconnectFallback', 'submitBtn']) {
    $(id).disabled = !ready;
  }
  $('ethernetGuard').style.color = ready ? '#12682e' : '#9a4718';
}
async function refreshEthernet() {
  // Fail closed while checking; no action is permitted on stale Ethernet state.
  applyEthernetLock(false, 'Checking Ethernet connection');
  try {
    const response = await fetch('ethernet-status', {cache: 'no-store'});
    const data = await response.json();
    applyEthernetLock(!!data.ethernet_ready, data.ethernet_message +
      (data.ethernet_ip ? ' (' + data.ethernet_ip + ')' : ''));
  } catch (_) {
    applyEthernetLock(false, 'Ethernet status unavailable');
  }
}
$('ethernetRefresh').addEventListener('click', refreshEthernet);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshEthernet(); });
setInterval(refreshEthernet, 10000);
refreshEthernet();
