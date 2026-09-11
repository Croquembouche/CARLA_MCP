export function parkingAt(map,x,y){return (map.parking_spaces||[]).find(p=>{const a=p.yaw*Math.PI/180,dx=x-p.x,dy=y-p.y;return Math.abs(dx*Math.cos(a)+dy*Math.sin(a))<=p.length/2&&Math.abs(-dx*Math.sin(a)+dy*Math.cos(a))<=p.width/2})}
export function drawParking(ctx,map,occupied={},selected=null,scale=1,light=false){
 for(const strip of map.parking_curb_strips||[]){ctx.beginPath();strip.polygon.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.strokeStyle=light?'#577f87':'#6d929c';ctx.lineWidth=.8/scale;ctx.setLineDash([4/scale,4/scale]);ctx.stroke();ctx.setLineDash([])}
 for(const area of map.parking_areas||[]){ctx.beginPath();area.polygon.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.fillStyle=light?'#7955b015':'#b99aff10';ctx.fill();ctx.strokeStyle=light?'#725692':'#8d78a6';ctx.lineWidth=.8/scale;ctx.setLineDash([3/scale,3/scale]);ctx.stroke();ctx.setLineDash([])}
 for(const p of map.parking_spaces||[]){const active=p.id===selected,used=!!occupied[p.id];ctx.beginPath();p.polygon.forEach((v,i)=>i?ctx.lineTo(...v):ctx.moveTo(...v));ctx.closePath();ctx.fillStyle=used?'#7b899455':light?'#7751c522':'#b79bff22';ctx.fill();ctx.strokeStyle=active?(light?'#5d279e':'#e2c4ff'):used?(light?'#606b75':'#7f909b'):(light?'#7850b1':'#b79bff');ctx.lineWidth=(active?2.5:1)/scale;ctx.stroke();if(scale>=3||active){ctx.font=`${(active?11:9)/scale}px sans-serif`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=light?'#442568':'#e3d3ff';ctx.fillText(active?p.id:'P',p.x,p.y)}}
}
export class ParkingPanel{
 constructor(root,command,notice,onChange,onActor){this.root=root;this.command=command;this.notice=notice;this.onChange=onChange;this.onActor=onActor;this.selected=null;
  this.bays=root.querySelector('#parking-bay');this.models=root.querySelector('#parking-model');this.button=root.querySelector('#parking-spawn');
  this.bays.onchange=()=>this.select(this.bays.value);
  this.button.onclick=async()=>{try{const r=await command('spawn',{role:'background',model:this.models.value,parking_space:this.selected});onActor(r.id);notice(`Vehicle ${r.id} parked in ${r.parking_space}. Handbrake applied; autopilot is off.`,true)}catch(e){notice(e.message)}};
 }
 select(id){this.selected=id||null;this.bays.value=this.selected||'';this.renderDetail();this.onChange()}
 render(state,map,catalog){this.state=state;this.map=map;const surveyLink=this.root.querySelector('#parking-survey-link');if(surveyLink)surveyLink.hidden=map.name?.split('/').pop()!=='Town10HD_Opt';const spaces=map.parking_spaces||[],occupied=state.parking?.occupied||{};
  this.root.querySelector('#parking-count').textContent=`${spaces.length} selectable parking positions · ${spaces.filter(p=>occupied[p.id]).length} occupied`;
  const review=this.root.querySelector('#parking-restrictions');if(review){
   const excluded=map.parking_excluded||[],key=JSON.stringify([map.parking_rules,excluded.map(p=>[p.id,p.restriction_reasons,state.parking?.excluded_occupied?.[p.id]])]);
   if(key!==this.reviewKey){this.reviewKey=key;review.replaceChildren();const summary=document.createElement('summary');summary.textContent=`Excluded parking · ${excluded.length} spaces`;review.append(summary);
    const info=document.createElement('p');info.className='hint';info.textContent=`${map.parking_rules?.profile||'No traffic-rule audit available'}. Excluded spaces cannot be spawned into or selected as parking destinations.`;review.append(info);
    for(const p of excluded){const item=document.createElement('p');item.className='hint';item.textContent=`${p.id}${state.parking?.excluded_occupied?.[p.id]?.id?' · existing vehicle '+state.parking.excluded_occupied[p.id].id:''} — ${p.restriction_reasons.map(r=>r.reason).join('; ')}`;review.append(item)}
   }
  }
  const keys=JSON.stringify(spaces.map(p=>p.id));if(keys!==this.keys){this.keys=keys;this.bays.replaceChildren(new Option('Select a bay on the map or here',''),...spaces.map(p=>new Option(p.id,p.id)));if(!spaces.some(p=>p.id===this.selected))this.selected=null;this.bays.value=this.selected||''}
  for(const option of this.bays.options)if(option.value)option.textContent=`${option.value} · ${occupied[option.value]?'Occupied':state.parking?.reserved?.[option.value]?'Reserved':'Free'}`;
  const vehicles=(catalog.vehicles||[]).filter(v=>v.id.startsWith('vehicle.'));const modelKey=vehicles.map(v=>v.id).join(',');if(this.modelKey!==modelKey){this.modelKey=modelKey;const old=this.models.value;this.models.replaceChildren(...vehicles.map(v=>new Option(v.label,v.id)));this.models.value=vehicles.some(v=>v.id===old)?old:vehicles.find(v=>v.id==='vehicle.mini.cooper')?.id||vehicles.find(v=>v.id==='vehicle.tesla.model3')?.id||vehicles[0]?.id||''}
  this.renderDetail();
 }
 renderDetail(){const p=this.map?.parking_spaces?.find(p=>p.id===this.selected),used=this.state?.parking?.occupied?.[this.selected];this.root.querySelector('#parking-detail').textContent=p?`${p.id} · ${p.length.toFixed(1)} × ${p.width.toFixed(1)} m · ${used?(used.kind==='actor'?`occupied by vehicle ${used.id}`:'occupied by a scenery vehicle'):'free'} · ${p.boundary_note||'estimated bay boundary'}`:'Purple: selectable parking positions. Grey: occupied. Dashed blue-grey: surveyed curb strips, including restricted portions. Continuous strips have no painted divisions between cars; individual boxes are planning positions.';this.setDisabled(this.disabled)}
 setDisabled(disabled){this.disabled=disabled;this.button.disabled=!!disabled||!this.selected||!!this.state?.parking?.occupied?.[this.selected]||!!this.state?.parking?.reserved?.[this.selected];this.root.querySelector('#parking-help').textContent=this.state?.running?'Pause to place or remove parked vehicles. Parking bays remain selectable during a run.':'Place a background vehicle in a free bay, then select it and choose a road destination or another parking bay. It drives parking maneuvers at low speed and uses Traffic Manager on the road.'}
}
