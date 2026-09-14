import {streamHealth} from './stream-health.js?v=lag-lights-1';
import {LidarView} from './lidar-view.js?v=vehicle-forward-1';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const cabinPresets={
 overview:{name:'cabin_overview',type:'sensor.camera.rgb',mount:{x:.55,y:0,z:1.2,yaw:180,pitch:-8,roll:0},attributes:{image_size_x:'960',image_size_y:'600',fov:'120',post_process_profile:'CabinObservation',lens_k:'0',use_ray_tracing:'false'}},
 dashboard:{name:'cabin_dashboard',type:'sensor.camera.rgb',mount:{x:-.20,y:0,z:1.25,yaw:0,pitch:-16},attributes:{image_size_x:'960',image_size_y:'600',fov:'100',post_process_profile:'CabinObservation',lens_k:'0',use_ray_tracing:'false'}},
 rear:{name:'cabin_rear_seats',type:'sensor.camera.rgb',mount:{x:-.43,y:.05,z:1.22,yaw:180,pitch:-15},attributes:{image_size_x:'960',image_size_y:'600',fov:'100',post_process_profile:'CabinObservation',lens_k:'0',use_ray_tracing:'false'}}
};
export function cabinOverviewFor(model){
 const camera=structuredClone(cabinPresets.overview);
 if(model==='vehicle.ambulance.ford'){
  camera.mount={x:1.6,y:-.55,z:1.65,yaw:140,pitch:-20};
  camera.attributes.post_process_profile='AmbulanceCabinObservation';
 }
 return camera;
}
export function shouldFetch({active,visible,pageVisible,busy,now,nextAt,running,frame,lastFrame}){return active&&visible&&pageVisible&&!busy&&now>=nextAt&&(running||frame!==lastFrame)}
export class SensorView{
 constructor(root,controls){
  this.root=root;this.controls=controls;this.active=false;this.cards=new Map();this.selected=new Set();this.mode='all';this.fps=5;this.inFlight=0;this.transfers=[];this.state={};this.orbits=new Map();this.lidarColor="height";
  root.innerHTML=`<div class="sensor-view-heading"><div><div class="eyebrow">LIVE OBSERVATION</div><h2>Sensor views</h2></div><div id="sensor-transfer" role="status">No preview transfer</div></div><div class="sensor-view-toolbar"><label>Ego vehicle<select id="view-ego" aria-label="View ego vehicle"></select></label><div class="segmented"><button id="view-all" class="active">All sensors</button><button id="view-single">Single sensor</button></div><label id="view-focus-label" hidden>Sensor<select id="view-focus"></select></label><label>Preview rate<select id="view-rate"><option value="2">2 fps · low bandwidth</option><option value="5" selected>5 fps · balanced</option><option value="10">10 fps · smoother</option></select></label><label>LiDAR color<select id="view-lidar-color"><option value="height">Height</option><option value="intensity">Intensity · 0–1</option></select></label><button id="view-freeze">Freeze previews</button></div><p id="sensor-view-status" class="hint" role="status"></p><p id="sensor-scene-weather" class="hint" role="status"></p><div id="sensor-grid"></div>`;
  controls.innerHTML=`<div class="eyebrow">DISPLAY SELECTION</div><h2>Visible sensors</h2><p class="hint">Choose which feeds appear in the grid. Focus a tile to view just that sensor.</p><div id="view-sensor-list"></div><button id="view-edit-loadout" class="wide">Configure this ego’s sensors</button><p class="hint">Only on-screen tiles download previews. Switching tabs, hiding this browser tab or freezing previews stops requests. LiDAR: drag to rotate, scroll or use + / − to zoom; panning is disabled. Previews are bounded; raw recording and ROS capture keep full fidelity.</p><p class="hint">New ego vehicles include front RGB, LiDAR, IMU, GNSS, radar and cabin_overview. Uncheck a sensor above to stop its preview downloads; capture and recording continue. Remove the camera in Sensors to stop capture. Choose Lincoln / MKZ Interior for the finished cabin; other models may need a mount adjustment.</p>`;
  this.el=id=>document.getElementById(id);
  this.el('view-edit-loadout').onclick=()=>this.onConfigure?.(this.ego);
  this.el('view-ego').onchange=()=>{this.ego=this.el('view-ego').value;this.signature='';this.update(this.state)};
  this.el('view-all').onclick=()=>{this.mode='all';this.selected=new Set(this.sensors.map(s=>s.id));this.rebuild()};
  this.el('view-single').onclick=()=>{this.mode='single';this.focus=Number(this.el('view-focus').value)||this.sensors[0]?.id;this.rebuild()};
  this.el('view-focus').onchange=()=>{this.focus=Number(this.el('view-focus').value);this.rebuild()};
  this.el('view-lidar-color').onchange=()=>{this.lidarColor=this.el('view-lidar-color').value;for(const c of this.cards.values())if(c.sensor.type==='sensor.lidar.ray_cast'){c.abort?.abort();c.lastFrame=-1;c.nextAt=0}};
  this.el('view-rate').onchange=()=>{this.fps=Number(this.el('view-rate').value)};
  this.el('view-freeze').onclick=()=>{this.frozen=!this.frozen;this.el('view-freeze').textContent=this.frozen?'Resume previews':'Freeze previews';if(this.frozen)this.cancel();this.status()};
  this.observer=new IntersectionObserver(entries=>{for(const e of entries){const card=this.cards.get(Number(e.target.dataset.sensorId));if(card&&card.node===e.target){card.visible=e.isIntersecting&&e.intersectionRatio>=.05;if(!card.visible)card.abort?.abort()}}},{root:this.el('sensor-grid'),threshold:.05});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)this.cancel();this.status()});
  window.addEventListener('pagehide',()=>this.cancel());
  this.resize=new ResizeObserver(()=>this.layout());this.resize.observe(this.el('sensor-grid'));
  this.timer=setInterval(()=>this.pump(),80);
 }
 setActive(value){this.active=value;this.root.hidden=!value;if(!value)this.cancel();this.status()}
 cancel(){for(const c of this.cards.values())c.abort?.abort();this.transfers=[]}
 update(state){
  if(this.previousFrame>(state.last_complete_frame??state.frame??0)){this.signature='';this.cancel()}
  this.previousFrame=state.last_complete_frame??state.frame??0;this.state=state;
  const egos=Object.entries(state.managed||{}).filter(([,m])=>m.role==='ego');if(!egos.some(([id])=>id===this.ego))this.ego=egos[0]?.[0]||'';
  const opts=egos.map(([id])=>`<option value="${id}">Ego / ${id}</option>`).join('');if(this.el('view-ego').innerHTML!==opts)this.el('view-ego').innerHTML=opts;this.el('view-ego').value=this.ego;
  const sensors=(state.sensors||[]).filter(s=>String(s.parent)===this.ego),signature=JSON.stringify(sensors);
  if(signature!==this.signature){this.signature=signature;this.sensors=sensors;this.selected=new Set(sensors.map(s=>s.id));if(!sensors.some(s=>s.id===this.focus))this.focus=sensors[0]?.id;this.rebuild()}
  this.status();
 }
 rebuild(){
  this.cancel();for(const c of this.cards.values()){this.observer.unobserve(c.node);if(c.lidar){this.orbits.set(c.sensor.id,c.lidar.snapshot());c.lidar.dispose()}if(c.url)URL.revokeObjectURL(c.url)}this.cards.clear();
  this.el('view-focus-label').hidden=this.mode!=='single';this.el('view-all').classList.toggle('active',this.mode==='all');this.el('view-single').classList.toggle('active',this.mode==='single');
  this.el('view-focus').innerHTML=(this.sensors||[]).map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');this.el('view-focus').value=this.focus??'';
  this.el('view-sensor-list').innerHTML=(this.sensors||[]).map(s=>`<label class="view-sensor-option"><input type="checkbox" data-sensor="${s.id}" ${this.selected.has(s.id)?'checked':''}><span><b>${esc(s.name)}</b><small>${esc(s.type.replace('sensor.',''))}</small></span></label>`).join('')||'<p class="hint">No sensors configured on this ego vehicle.</p>';
  this.controls.querySelectorAll('[data-sensor]').forEach(el=>el.onchange=()=>{if(el.checked)this.selected.add(Number(el.dataset.sensor));else this.selected.delete(Number(el.dataset.sensor));this.mode='all';this.rebuild()});
  const shown=(this.sensors||[]).filter(s=>this.mode==='single'?s.id===this.focus:this.selected.has(s.id));this.el('sensor-grid').classList.toggle('single',this.mode==='single');
  this.el('sensor-grid').innerHTML=shown.map(s=>`<article class="sensor-tile" data-sensor-id="${s.id}"><div class="sensor-tile-heading"><div><h3>${esc(s.name)}</h3><small>${esc(s.type.replace('sensor.',''))}</small></div><button data-focus="${s.id}" aria-label="Focus ${esc(s.name)}">Focus</button></div><div class="sensor-image-wrap">${s.type.startsWith('sensor.lidar.')?`<div class="lidar-canvas" aria-label="${esc(s.name)} 3D point cloud"></div><div class="lidar-tools"><button data-zoom="in" aria-label="Zoom in ${esc(s.name)}">+</button><button data-zoom="out" aria-label="Zoom out ${esc(s.name)}">−</button><button data-reset aria-label="Reset view ${esc(s.name)}">Reset</button></div>`:''}<img alt="${esc(s.name)} live sensor preview" hidden><dl hidden></dl><span class="sensor-placeholder">Waiting for a completed frame</span></div><div class="sensor-tile-footer"><span class="sensor-frame">No frame received</span><span class="sensor-quality">${s.type.includes('lidar')?'Drag to rotate · scroll to zoom':s.type.endsWith('radar')?'Top view · 80 m radius':s.type.endsWith('depth')?'Log depth · 0–1,000 m':s.type.includes('camera')?'Compressed preview':'Live measurements'}</span></div></article>`).join('');
  for(const s of shown){const node=this.el('sensor-grid').querySelector(`[data-sensor-id="${s.id}"]`);const c={node,sensor:s,lastFrame:-1,nextAt:0,visible:false};this.cards.set(s.id,c);node.querySelectorAll('[data-zoom]').forEach(b=>b.onclick=()=>c.lidar?.zoom(b.dataset.zoom==='in'?.8:1.25));const reset=node.querySelector('[data-reset]');if(reset)reset.onclick=()=>c.lidar?.reset();this.observer.observe(node);node.querySelector('[data-focus]').onclick=()=>{this.focus=s.id;this.mode='single';this.rebuild()}}
  this.layout();this.status();
 }
 layout(){const grid=this.el('sensor-grid'),n=this.cards.size,w=grid.clientWidth;const columns=this.mode==='single'?1:Math.max(1,Math.min(n,n>4?3:2,Math.floor(w/230)));grid.style.gridTemplateColumns=`repeat(${columns},minmax(0,1fr))`;grid.style.gridTemplateRows=`repeat(${Math.max(1,Math.ceil(n/columns))},minmax(190px,1fr))`}
 status(){
  if(!this.el('sensor-view-status'))return;
  const w=this.state.weather;this.el('sensor-scene-weather').textContent=w?`Shared scene weather · Cloud ${Math.round(w.cloudiness)}% · Rain ${Math.round(w.precipitation)}% · Sun ${Math.round(w.sun_altitude_angle)}°. Frame numbers below identify each displayed sample.`:'';
  this.el('sensor-view-status').textContent=['loading','warming','verifying','releasing'].includes(this.state.gpu_operation?.stage)?this.state.gpu_operation.detail+' · previews resume when capture is ready.':this.state.phase!=='connected'?'Waiting for a connected simulator.':this.state.mode==='native-replay'?'Live sensor previews are unavailable during native actor replay.':!this.ego?'Spawn an ego vehicle, then configure its sensors in Sensors.':!this.sensors?.length?'This ego has no sensors. Add a loadout in Sensors.':this.frozen?'Previews frozen. Sensor capture and recording continue.':this.state.running?(streamHealth(this.state).status==='waiting'?streamHealth(this.state).text+' · last completed samples remain visible.':'Live previews · each tile shows its frame and simulation time.'):`Simulator paused · showing the last completed samples. Step or Run to refresh.`;
 }
 pump(){
  const now=performance.now();this.transfers=this.transfers.filter(t=>t.at>now-2000);const bytes=this.transfers.reduce((n,t)=>n+t.bytes,0);
  const active=this.active&&!this.frozen&&this.state.phase==='connected'&&!['loading','warming','verifying','releasing'].includes(this.state.gpu_operation?.stage)&&this.state.mode!=='native-replay'&&!['restoring','restarting'].includes(this.state.recovery_operation?.stage);
  this.el('sensor-transfer').textContent=!active||document.hidden?'No preview transfer':`${[...this.cards.values()].filter(c=>c.visible).length} visible · ${(bytes/2000).toFixed(1)} kB/s`;
  for(const c of [...this.cards.values()].sort((a,b)=>a.nextAt-b.nextAt)){
   if(this.inFlight>=3)break;
   if(shouldFetch({active,visible:c.visible,pageVisible:!document.hidden,busy:c.abort,now,nextAt:c.nextAt,running:this.state.running,frame:this.state.last_complete_frame??this.state.frame,lastFrame:c.lastFrame}))this.fetchCard(c);
  }
 }
 async fetchCard(c){
  const abort=new AbortController();c.abort=abort;this.inFlight++;const deadline=setTimeout(()=>abort.abort(),5000);
  const width=this.mode==='single'?960:Math.min(640,Math.max(320,Math.round(c.node.clientWidth/80)*80));
  try{
   const r=await fetch(`/api/preview/${c.sensor.id}?width=${width}&after=${c.lastFrame}${c.sensor.type.startsWith('sensor.lidar.')?'&format=points&color='+this.lidarColor+'&point_limit='+(this.mode==='single'?12000:4000):''}`,{signal:abort.signal,cache:'no-store'});
   if(!r.ok)throw Error(r.status===404?'Waiting for a completed sensor sample':`Preview unavailable (${r.status})`);
   if(r.status===204)return;
   const body=await r.blob();if(abort.signal.aborted||this.cards.get(c.sensor.id)!==c)return;
   this.transfers.push({at:performance.now(),bytes:body.size});c.lastFrame=Number(r.headers.get('X-CARLA-Frame'));c.node.querySelector('.sensor-placeholder').hidden=true;
   if(body.type==='application/vnd.carla.pointcloud'){const buffer=await body.arrayBuffer();if(abort.signal.aborted||this.cards.get(c.sensor.id)!==c)return;if(!c.lidar)c.lidar=new LidarView(c.node.querySelector('.lidar-canvas'),this.orbits.get(c.sensor.id));c.lidar.setData(buffer,Number(r.headers.get('X-Point-Scale')))}
   else if(body.type.startsWith('image/')){const img=c.node.querySelector('img'),old=c.url;c.url=URL.createObjectURL(body);img.src=c.url;img.hidden=false;if(old)URL.revokeObjectURL(old)}
   else{const data=JSON.parse(await body.text()),dl=c.node.querySelector('dl');dl.hidden=false;dl.innerHTML=Object.entries(data.values).map(([name,value])=>`<dt>${esc(name)} <small>${esc(data.units[name])}</small></dt><dd>${typeof value==='object'?Object.entries(value).map(([axis,n])=>`${axis} ${Number(n).toFixed(3)}`).join(' · '):Number(value).toFixed(name==='latitude'||name==='longitude'?7:3)}</dd>`).join('')}
   c.node.querySelector('.sensor-frame').textContent=`Frame ${c.lastFrame} · ${Number(r.headers.get('X-CARLA-Timestamp')).toFixed(2)} s`;
   if(r.headers.has('X-Preview-Points'))c.node.querySelector('.sensor-quality').textContent=`${Number(r.headers.get('X-Preview-Points')).toLocaleString()} / ${Number(r.headers.get('X-Preview-Source-Points')).toLocaleString()} points · ${c.sensor.type.startsWith('sensor.lidar.')?`${r.headers.get('X-Preview-Color')==='intensity'?'Intensity 0–1 · ':''}drag to rotate · scroll to zoom`:'top view'}`;
  }catch(e){if(e.name!=='AbortError'){c.node.querySelector('.sensor-placeholder').hidden=false;c.node.querySelector('.sensor-placeholder').textContent=e.message}}
  finally{clearTimeout(deadline);if(c.abort===abort)c.abort=null;this.inFlight--;c.nextAt=performance.now()+1000/this.fps}
 }
}
