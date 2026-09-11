// Map symbols scale uniformly in world space; legend and overview use screen sizes.
export const actorKinds = {
 background: {label:'Background vehicle', color:'#4299f5', size:14, lengthMeters:4.5, widthMeters:1.9},
 ego: {label:'Ego vehicle', color:'#38cf78', size:14, lengthMeters:4.5, widthMeters:1.9},
 pedestrian: {label:'Pedestrian', color:'#b779f4', size:8, lengthMeters:.65, widthMeters:.65},
 bicycle: {label:'Bicyclist', color:'#f0d43a', size:11, lengthMeters:2, widthMeters:.65},
 emergency: {label:'Emergency vehicle', color:'#f05261', size:14, lengthMeters:4.5, widthMeters:1.9},
 motorcycle: {label:'Motorcyclist', color:'#f59b42', size:11, lengthMeters:2, widthMeters:.65},
};
export function actorKind(actor,managed){
 const type=actor.type||'',attrs=actor.attributes||{};
 if(!type.startsWith('vehicle.')&&!type.startsWith('walker.'))return null;
 // Ego is a role and stays green regardless of the chosen vehicle model.
 if(managed?.role==='ego')return 'ego';
 if(type.startsWith('walker.')||managed?.role==='pedestrian')return 'pedestrian';
 if(/emergency|police|ambulance|firetruck/i.test(attrs.special_type||'')||/ambulance|firetruck|fire_truck|dodgecop|chargercop|police/i.test(type))return 'emergency';
 if(attrs.base_type==='bicycle'||/vehicle\.(bh\.|diamondback\.|gazelle\.)/.test(type))return 'bicycle';
 if(attrs.base_type==='motorcycle'||/vehicle\.(harley\.|kawasaki\.|vespa\.|yamaha\.)/.test(type))return 'motorcycle';
 return 'background';
}
export function drawActorMarker(ctx,actor,managed,x,y,{light=false,selected=false,sizeScale=1,pixelsPerMeter=null}={}){
 const kind=actorKind(actor,managed);if(!kind)return;
 const {color,size,lengthMeters,widthMeters}=actorKinds[kind];
 const dimension=(value,fallback)=>Number.isFinite(Number(value))&&Number(value)>0?Number(value)*2:fallback;
 const worldLength=dimension(actor.extent?.x,lengthMeters),worldWidth=dimension(actor.extent?.y,widthMeters);
 const pedestrian=kind==='pedestrian';
 const length=pixelsPerMeter===null?size*sizeScale:(pedestrian?Math.max(worldLength,worldWidth):worldLength)*pixelsPerMeter;
 const width=pedestrian?length:pixelsPerMeter===null?length*worldWidth/worldLength:worldWidth*pixelsPerMeter;
 ctx.save();ctx.translate(x,y);ctx.rotate((actor.pose.yaw||0)*Math.PI/180);
 ctx.fillStyle=color;ctx.strokeStyle=light?'#203442':'#0c1720';ctx.lineWidth=Math.min(sizeScale,Math.min(length,width)*.12);
 ctx.beginPath();
 if(pedestrian)ctx.arc(0,0,length/2,0,Math.PI*2);
 else ctx.rect(-length/2,-width/2,length,width);
 ctx.fill();ctx.stroke();
 // A filled arrow stays inside the footprint and follows the actor's local +X heading.
 const tip=length*.32,tail=-length*.3,neck=length*.02,head=width*.28,shaft=width*.09;
 ctx.fillStyle='#102531';ctx.beginPath();ctx.moveTo(tip,0);ctx.lineTo(neck,-head);ctx.lineTo(neck,-shaft);ctx.lineTo(tail,-shaft);ctx.lineTo(tail,shaft);ctx.lineTo(neck,shaft);ctx.lineTo(neck,head);ctx.closePath();ctx.fill();
 if(selected){ctx.strokeStyle=light?'#173f35':'#e2fff3';ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(0,0,Math.hypot(length,width)/2+4,0,Math.PI*2);ctx.stroke()}
 ctx.restore();
}
export function renderActorLegend(element){
 element.replaceChildren(...Object.entries(actorKinds).map(([kind,{label}])=>{
  const row=document.createElement('span');row.className='actor-legend-row';row.dataset.kind=kind;
  const symbol=document.createElement('canvas');symbol.className='actor-legend-symbol';symbol.width=40;symbol.height=32;symbol.setAttribute('aria-hidden','true');
  const ctx=symbol.getContext('2d');ctx.scale(2,2);
  const types={background:'vehicle.car',ego:'vehicle.car',pedestrian:'walker.pedestrian',bicycle:'vehicle.bh.bicycle',emergency:'vehicle.ambulance',motorcycle:'vehicle.yamaha.motorcycle'};
  drawActorMarker(ctx,{type:types[kind],pose:{yaw:0}},{role:kind==='ego'?'ego':'background'},10,8);
  row.append(symbol,document.createTextNode(label));return row;
 }));
}
