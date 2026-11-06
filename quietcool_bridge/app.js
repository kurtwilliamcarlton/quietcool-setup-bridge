'use strict';
const $=id=>document.getElementById(id),pages=[...document.querySelectorAll('.wizard-page')];
let step=0,ethernet=false,wifi=false,identified=false,sent=false,verified=false,disabled=false,busy=false;
async function call(url,options={}){const r=await fetch(url,{cache:'no-store',...options});let d=await r.json();if(!r.ok||d.ok===false)throw Error(d.message||'Request failed');return d}
function msg(id,text,kind='neutral'){const x=$(id);x.hidden=false;x.textContent=text;x.className=['globalError','wifiActionResult','saveResult','cleanupResult'].includes(id)?'result '+(kind==='success'?'ok':'error'):'notice '+kind}
function buttons(){const ok=ethernet&&!busy;
for(const id of ['scanFallback','connectFallback','wifiRefresh','verifyLan'])$(id).disabled=!ok;
$('checkBtn').disabled=!ok||!wifi;
$('submitBtn').disabled=!ok||!wifi||!identified;
$('disconnectFallback').disabled=!ok||!verified||disabled;
$('nextBtn').disabled=busy||[false,!ethernet,!wifi,!identified,!sent,!(verified&&disabled)][step];
$('nextBtn').textContent=step===0?'Get started':step===5?'Finish':'Next';
$('backBtn').disabled=busy||step===0}
async function checkEthernet(){ethernet=false;buttons();try{const d=await call('ethernet-status');ethernet=!!d.ethernet_ready;msg('ethernetGuard',(ethernet?'✓ ':'⚠ ')+(d.ethernet_message||'Ethernet unavailable')+(d.ethernet_ip?' · '+d.ethernet_ip:''),ethernet?'success':'error')}catch(e){msg('ethernetGuard','⚠ Cannot verify Ethernet: setup locked','error')}buttons()}
async function checkWifi(){try{const d=await call('wifi-status');wifi=!!d.fallback_connected;disabled=!d.wifi_enabled;msg('yellowWifiStatus',disabled?'Yellow wlan0 is disabled':wifi?'✓ Connected to QuietCool Fallback':d.wifi_connected?'Connected to '+(d.ssid||'another network'):'Not connected to QuietCool Fallback',wifi||disabled?'success':'neutral')}catch(e){wifi=false;msg('yellowWifiStatus',e.message,'error')}buttons()}
async function checkDevice(){identified=false;buttons();try{const d=await call('status');if(!d.connected)throw Error(d.message||'ESP32 not reachable');identified=true;$('deviceName').textContent=d.device.name;$('deviceMac').textContent=d.device.mac;$('statusBadge').className='pill online';$('statusBadge').textContent='Identified';msg('statusText','ESPHome captive portal identified. You can continue.','success');const select=$('networks');select.replaceChildren(new Option('Choose network (optional)',''));let seen=new Set();for(const ap of d.device.aps||[]){if(ap.ssid&&!seen.has(ap.ssid)){seen.add(ap.ssid);select.add(new Option(ap.ssid,ap.ssid))}}}catch(e){$('statusBadge').className='pill offline';$('statusBadge').textContent='Not found';msg('statusText',e.message,'error')}buttons()}
function page(n){step=n;pages.forEach((p,i)=>p.hidden=i!==n);$('progressText').textContent='Step '+(n+1)+' of 6';$('progressFill').style.width=((n+1)*100/6)+'%';buttons();if(n===1)checkEthernet();if(n===2)checkWifi();if(n===3&&wifi)checkDevice();scrollTo({top:0,behavior:'smooth'})}
$('nextBtn').onclick=()=>{if($('nextBtn').disabled)return;if(step===5){$('completed').hidden=false;$('nextBtn').disabled=true;$('nextBtn').textContent='Finished'}else page(step+1)};
$('backBtn').onclick=()=>page(Math.max(0,step-1));
$('ethernetRefresh').onclick=checkEthernet;$('wifiRefresh').onclick=checkWifi;$('checkBtn').onclick=checkDevice;
$('scanFallback').onclick=async()=>{try{msg('scanResult','Scanning…');const d=await call('wifi-scan');msg('scanResult',d.found?'✓ QuietCool Fallback found':'Not found. Put ESP32 in setup mode, then retry.',d.found?'success':'neutral')}catch(e){msg('scanResult',e.message,'error')}};
async function post(path,body){busy=true;buttons();try{return await call(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}finally{busy=false;buttons()}}
$('connectFallback').onclick=async()=>{const password=$('fallbackPassword').value;if(password.length<8)return msg('wifiActionResult','Enter the temporary setup password (at least 8 characters).','error');if(!confirm('Connect Yellow wlan0 to QuietCool Fallback?'))return;try{const d=await post('wifi-connect',{password});$('fallbackPassword').value='';msg('wifiActionResult',d.message,'success');await checkWifi()}catch(e){msg('wifiActionResult',e.message,'error')}};
$('networks').onchange=e=>{if(e.target.value)$('ssid').value=e.target.value};
$('showPassword').onchange=e=>$('psk').type=e.target.checked?'text':'password';
$('setupForm').onsubmit=async e=>{e.preventDefault();if(!ethernet||!wifi||!identified)return msg('saveResult','Complete the earlier checks first.','error');const ssid=$('ssid').value.trim();if(!ssid)return;if(!confirm('Send home Wi-Fi credentials for '+ssid+' to the ESP32?'))return;try{const d=await post('provision',{ssid,psk:$('psk').value});sent=true;$('psk').value='';msg('saveResult',d.message,'success');buttons()}catch(err){msg('saveResult',err.message,'error')}};
$('verifyLan').onclick=async()=>{try{msg('verifyResult','Checking ESP32 on the home network…');const d=await post('verify-lan',{ip:$('lanIp').value.trim()});verified=!!d.verified;msg('verifyResult',d.message+(d.ip?' ('+d.ip+')':''),verified?'success':'error')}catch(e){verified=false;msg('verifyResult',e.message,'error')}buttons()};
$('disconnectFallback').onclick=async()=>{if(!verified)return;if(!confirm('Disable the Yellow’s temporary wlan0 Wi-Fi connection?'))return;try{const d=await post('wifi-disconnect',{confirm:true});msg('cleanupResult',d.message,'success');await checkWifi();if(disabled)$('completed').hidden=false}catch(e){msg('cleanupResult',e.message,'error')}};
document.addEventListener('visibilitychange',()=>{if(!document.hidden){checkEthernet();if(step===2||step===5)checkWifi()}});
setInterval(()=>{if(!document.hidden)checkEthernet()},15000);
page(0);
