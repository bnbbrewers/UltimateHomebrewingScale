"""Small progressive enhancement for Wi-Fi and simulation settings."""
SCRIPT = r"""<script>
(()=>{
const el=id=>document.getElementById(id), field=n=>document.querySelector('[name="'+n+'"]');
const token=new URLSearchParams(location.search).get('k');
async function request(path,values){
  if(token)path+=(path.includes('?')?'&':'?')+'k='+encodeURIComponent(token);
  const options=values===undefined?{cache:'no-store'}:{method:'POST',body:new URLSearchParams(values),cache:'no-store'};
  const response=await fetch(path,options),data=await response.json();
  if(!response.ok)throw new Error(typeof data.error==='string'?data.error:JSON.stringify(data.error));
  return data;
}
const messages={connected:'Connected',wrong_password:'Incorrect Wi-Fi password',network_not_found:'Network not found',connection_failed:'Connection failed',timeout:'Connection timed out',connecting:'Connecting...',disconnected:'Disconnected',unavailable:'Wi-Fi unavailable'};
let busy=false;
async function refresh(){
 if(busy||document.hidden)return;busy=true;
 try{
  const w=await request('/wifi/status');
  const code=w.test&&w.test!=='idle'?w.test:w.code;
  el('wifi-status').textContent=(messages[code]||code)+(w.testSsid?' / '+w.testSsid:'')+(w.connected?' / IP '+w.ip:'')+(w.rssi!=null?' / '+w.rssi+' dBm':'');
  const s=await request('/simulation/status');
  el('sim-status').textContent=s.enabled?'SIMULATION: '+s.weightG.toFixed(1)+' g / target '+s.targetG+' g / '+(s.stable?'stable':'moving'):'Real scale active. Enable test mode and save to simulate.';
  ['sim-set','sim-target','sim-tare'].forEach(id=>el(id).disabled=!s.enabled);
 }catch(error){el('wifi-status').textContent='Portal unreachable. Reconnect to UHS-Setup or open the new IP.';}
 finally{busy=false;}
}
el('wifi-scan').onclick=async()=>{
 if(busy)return;busy=true;el('wifi-scan').disabled=true;
 try{
  el('wifi-status').textContent='Scanning...';
  const data=await request('/wifi/scan',{}),list=el('wifi-list');list.replaceChildren();
  data.networks.forEach(n=>{const option=document.createElement('option');option.value=n.ssid;option.label=n.rssi+' dBm / '+(n.secure?'secured':'open');list.append(option);});
  el('wifi-status').textContent=data.networks.length+' networks found. Select a suggestion in the SSID field.';
  field('WIFI_SSID').focus();
 }catch(error){el('wifi-status').textContent=error.message;}finally{busy=false;el('wifi-scan').disabled=false;}
};
el('wifi-test').onclick=async()=>{
 if(busy)return;busy=true;el('wifi-test').disabled=true;
 try{
  el('wifi-status').textContent='Testing... If disconnected, join UHS-Setup and open http://192.168.4.1:8080.';
  const result=await request('/wifi/test',{WIFI_SSID:field('WIFI_SSID').value,WIFI_PASSWORD:field('WIFI_PASSWORD').value});
  el('wifi-status').textContent=result.message;
 }catch(error){el('wifi-status').textContent=error.message+' / Reconnect to UHS-Setup if needed.';}
 finally{busy=false;el('wifi-test').disabled=false;}
};
async function sim(action){
 if(busy)return;busy=true;
 try{await request('/simulation/weight',{action,weight:el('sim-weight').value});}
 catch(error){el('sim-status').textContent=error.message;}finally{busy=false;}
}
el('sim-set').onclick=()=>sim('set');el('sim-target').onclick=()=>sim('target');el('sim-tare').onclick=()=>sim('tare');
if(token){const input=document.createElement('input');input.type='hidden';input.name='k';input.value=token;el('s').append(input);}
refresh();setInterval(refresh,2500);
})();
</script>"""
