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
