'use strict';
const $=id=>document.getElementById(id),pages=[...document.querySelectorAll('.wizard-page')];
let step=0,ethernet=false,wifi=false,identified=false,sent=false,verified=false,disabled=false,busy=false;
let discoveryActive=false,discoveryGeneration=0,expectedMac=null,discoveredIp=null;
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
async function checkExistingDevice(){
  msg('existingDeviceStatus','Checking Home Assistant ESPHome integrations…');
  try {
    const data=await call('existing-device');
    if(!data.available){
      msg('existingDeviceStatus',data.message+' You can still scan for QuietCool Fallback.','neutral');
    }else if(data.configured){
      const details=(data.entries||[]).map(x=>x.title+' ('+x.state+')').join(', ');
      msg('existingDeviceStatus','✓ QuietCool already has an ESPHome integration: '+details+'. You can reconfigure its Wi-Fi below if fallback mode is active.','success');
    }else{
      msg('existingDeviceStatus','No ESPHome integration named QuietCool found. It may have been renamed, or this may be a new controller.','neutral');
    }
  }catch(err){
    msg('existingDeviceStatus','Home Assistant device check unavailable. You may continue with fallback Wi-Fi discovery.','neutral');
  }
}
$('refreshExisting').onclick=checkExistingDevice;
async function checkWifi(){try{const d=await call('wifi-status');wifi=!!d.fallback_connected;disabled=!d.wifi_enabled;msg('yellowWifiStatus',disabled?'Yellow wlan0 is disabled':wifi?'✓ Connected to QuietCool Fallback':d.wifi_connected?'Connected to '+(d.ssid||'another network'):'Not connected to QuietCool Fallback',wifi||disabled?'success':'neutral')}catch(e){wifi=false;msg('yellowWifiStatus',e.message,'error')}buttons()}
async function checkDevice(){identified=false;expectedMac=null;buttons();try{const d=await call('status');if(!d.connected)throw Error(d.message||'ESP32 not reachable');identified=true;expectedMac=d.device.mac;$('deviceName').textContent=d.device.name;$('deviceMac').textContent=d.device.mac;$('statusBadge').className='pill online';$('statusBadge').textContent='Identified';msg('statusText','ESPHome captive portal identified. You can continue.','success');const select=$('networks');select.replaceChildren(new Option('Choose network (optional)',''));let seen=new Set();for(const ap of d.device.aps||[]){if(ap.ssid&&!seen.has(ap.ssid)){seen.add(ap.ssid);select.add(new Option(ap.ssid,ap.ssid))}}}catch(e){$('statusBadge').className='pill offline';$('statusBadge').textContent='Not found';msg('statusText',e.message,'error')}buttons()}
function page(n){step=n;pages.forEach((p,i)=>p.hidden=i!==n);$('progressText').textContent='Step '+(n+1)+' of 6';$('progressFill').style.width=((n+1)*100/6)+'%';buttons();if(n===1)checkEthernet();if(n===2){checkExistingDevice();checkWifi();}if(n===3&&wifi)checkDevice();if(n===5)autoDiscoverLan();else discoveryGeneration++;scrollTo({top:0,behavior:'smooth'})}
$('nextBtn').onclick=()=>{if($('nextBtn').disabled)return;if(step===5){displayCompletion();$('nextBtn').disabled=true;$('nextBtn').textContent='Finished'}else page(step+1)};
$('backBtn').onclick=()=>page(Math.max(0,step-1));
$('ethernetRefresh').onclick=checkEthernet;$('wifiRefresh').onclick=checkWifi;$('checkBtn').onclick=checkDevice;
$('scanFallback').onclick=async()=>{try{msg('scanResult','Scanning for a controller in fallback mode…');const d=await call('wifi-scan');msg('scanResult',d.found?'✓ QuietCool Fallback found. You can connect and reconfigure its home Wi-Fi.':'Not found. Put ESP32 in setup mode, then retry.',d.found?'success':'neutral')}catch(e){msg('scanResult',e.message,'error')}};
async function post(path,body){busy=true;buttons();try{return await call(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}finally{busy=false;buttons()}}
$('connectFallback').onclick=async()=>{const password=$('fallbackPassword').value;if(password.length<8)return msg('wifiActionResult','Enter the temporary setup password (at least 8 characters).','error');if(!confirm('Connect Yellow wlan0 to QuietCool Fallback?'))return;try{const d=await post('wifi-connect',{password});$('fallbackPassword').value='';msg('wifiActionResult',d.message,'success');await checkWifi()}catch(e){msg('wifiActionResult',e.message,'error')}};
$('networks').onchange=e=>{if(e.target.value)$('ssid').value=e.target.value};
$('showPassword').onchange=e=>$('psk').type=e.target.checked?'text':'password';
$('setupForm').onsubmit=async e=>{e.preventDefault();if(!ethernet||!wifi||!identified||!expectedMac)return msg('saveResult','Complete the earlier checks first.','error');const ssid=$('ssid').value.trim();if(!ssid)return;if(!confirm('Send home Wi-Fi credentials for '+ssid+' to the ESP32?'))return;try{const d=await post('provision',{ssid,psk:$('psk').value,expected_mac:expectedMac});sent=true;$('psk').value='';msg('saveResult',d.message,'success');buttons()}catch(err){msg('saveResult',err.message,'error')}};
async function autoDiscoverLan(){
  if(discoveryActive || verified || step!==5)return;
  const generation=++discoveryGeneration;
  discoveryActive=true;
  $('verifyLan').disabled=true;
  try {
    // Allow the ESP32 to reboot, obtain DHCP, and advertise mDNS.
    for(let attempt=1;attempt<=5;attempt++){
      if(generation!==discoveryGeneration || step!==5)return;
      await checkEthernet();
      if(!ethernet){msg('verifyResult','Ethernet is not available. Plug it in, then choose Retry automatic discovery.','error');return}
      msg('verifyResult','Looking for QuietCool on the home network… (attempt '+attempt+' of 5)');
      try{
        const d=await post('discover-lan',{});
        if(d.verified){
          verified=true;discoveredIp=d.ip||null;
          msg('verifyResult',d.message+' Home network IP: '+d.ip,'success');
          buttons();
          return;
        }
        if(attempt===5)msg('verifyResult',d.message+' Select Retry after checking Wi-Fi settings.','error');
      }catch(e){
        if(attempt===5)msg('verifyResult',e.message+'. Select Retry to search again.','error');
      }
      if(attempt<5)await new Promise(resolve=>setTimeout(resolve,4000));
    }
  }finally{discoveryActive=false;buttons()}
}
$('verifyLan').onclick=()=>{verified=false;discoveredIp=null;autoDiscoverLan()};
$('disconnectFallback').onclick=async()=>{if(!verified)return;if(!confirm('Disable the Yellow’s temporary wlan0 Wi-Fi connection?'))return;try{const d=await post('wifi-disconnect',{confirm:true});msg('cleanupResult',d.message,'success');await checkWifi();if(disabled)displayCompletion()}catch(e){msg('cleanupResult',e.message,'error')}};
document.addEventListener('visibilitychange',()=>{if(!document.hidden){checkEthernet();if(step===2||step===5)checkWifi();if(step===5&&!verified)autoDiscoverLan()}});
setInterval(()=>{if(!document.hidden)checkEthernet()},15000);
function displayCompletion(){
  if(!verified||!disabled)return;
  $('completed').hidden=false;
  $('summaryIp').textContent=discoveredIp||'Found on home LAN';
  $('summaryMac').textContent=expectedMac||'Not recorded';
}
$('startAgain').onclick=()=>{
  if(!disabled)return msg('cleanupResult','Disable temporary Wi-Fi before starting another setup.','error');
  identified=false;expectedMac=null;sent=false;verified=false;discoveredIp=null;wifi=false;
  $('completed').hidden=true;$('saveResult').textContent='';$('cleanupResult').textContent='';
  $('ssid').value='';$('psk').value='';$('deviceName').textContent='—';$('deviceMac').textContent='—';
  $('statusBadge').className='pill waiting';$('statusBadge').textContent='Not checked';
  page(0);
};
page(0);
