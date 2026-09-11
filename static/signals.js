export const signalColors={Red:'#e75359',Yellow:'#f1bd3d',Green:'#27c787',Off:'#7d8d97',Unknown:'#8794b8'};
export const isSignal=a=>a.type.startsWith('traffic.traffic_light');
export const signalPoint=a=>a.heads?.[0]||a.pose;
export const signalPoints=a=>a.heads?.length?a.heads:[a.pose];
const center=points=>({x:points.reduce((s,p)=>s+p.x,0)/points.length,y:points.reduce((s,p)=>s+p.y,0)/points.length,z:points.reduce((s,p)=>s+(p.z||0),0)/points.length});
export function signalGroups(actors){const groups=new Map();for(const a of actors.filter(isSignal)){const id=a.group_id??a.id;if(!groups.has(id))groups.set(id,[]);groups.get(id).push(a)}return [...groups].map(([id,members])=>({id,members:members.sort((a,b)=>a.id-b.id),pose:center(members.flatMap(signalPoints))}))}
// Shared screen-space layout keeps both maps consistent, with one overview badge
// per native group. Physical heads are only useful once they are separable.
export function signalMarkers(actors,selected,project){const markers=[];for(const group of signalGroups(actors)){
 const c=project(group.pose);if(!c)continue;
 const approaches=group.members.map(a=>({a,anchor:project(center(signalPoints(a)))})).filter(v=>v.anchor);
 const span=Math.max(0,...approaches.map(v=>Math.hypot(v.anchor[0]-c[0],v.anchor[1]-c[1])))*2;
 if(!group.members.some(a=>a.id===selected)&&span<180){markers.push({kind:'group',a:group.members[0],group,x:c[0],y:c[1],width:36,height:24,label:`G${group.id}`});continue}
 const detailed=span>=180,placed=[];
 for(const [i,{a,anchor}] of approaches.entries()){
  let dx=anchor[0]-c[0],dy=anchor[1]-c[1],length=Math.hypot(dx,dy);if(length<1){dx=Math.cos(i*2*Math.PI/approaches.length);dy=Math.sin(i*2*Math.PI/approaches.length);length=1}
  const radius=Math.max(length,detailed?45:32);let x=c[0]+dx/length*radius,y=c[1]+dy/length*radius;
  // Nearby approaches can share a pole. Offset labels without losing the anchor.
  for(let n=0;n<12&&placed.some(p=>Math.abs(p.x-x)<(detailed?66:42)&&Math.abs(p.y-y)<(detailed?48:29));n++)y+=n%2?-(n+1)*16:(n+1)*16;
  const m={kind:'approach',a,group,anchor,x,y,width:detailed&&a.movements?60:36,height:detailed&&a.movements?42:24,label:`A${a.id}`,selected:a.id===selected,detailed};placed.push(m);
  if(detailed)for(const h of signalPoints(a)){const p=project(h);if(p)markers.push({kind:'head',a,group,x:p[0],y:p[1],width:6,height:6})}
  markers.push(m);
 }
 }
 const placed=[];for(const m of markers.filter(m=>m.kind!=='head').sort((a,b)=>(a.kind==='group'?0:a.selected?1:2)-(b.kind==='group'?0:b.selected?1:2))){
  const [x,y]=[m.x,m.y],overlaps=(px,py)=>placed.some(p=>Math.abs(p.x-px)<(p.width+m.width)/2+6&&Math.abs(p.y-py)<(p.height+m.height)/2+6);
  search:for(let radius=8;overlaps(m.x,m.y)&&radius<=384;radius+=8)for(let i=0;i<24;i++){const px=x+Math.cos(i*Math.PI/12)*radius,py=y+Math.sin(i*Math.PI/12)*radius;if(!overlaps(px,py)){m.anchor??=[x,y];m.x=px;m.y=py;break search}}
  placed.push(m);
 }return markers}
export function markerAt(markers,x,y){return [...markers].reverse().find(m=>m.kind!=='head'&&Math.abs(m.x-x)<=m.width/2+4&&Math.abs(m.y-y)<=m.height/2+4)}
const movementColor=(a,m)=>({Stop:signalColors.Red,Caution:signalColors.Yellow,Protected:signalColors.Green,Permissive:signalColors.Yellow,Off:signalColors.Off}[a.movements?.[m]]||signalColors.Off);
export function drawTurn(g,direction,x,y,size=12){g.save();g.translate(x,y);g.scale(size/24,size/24);g.lineWidth=3;g.lineCap='round';g.lineJoin='round';g.beginPath();if(direction==='straight'){g.moveTo(12,21);g.lineTo(12,3);g.moveTo(6,9);g.lineTo(12,3);g.lineTo(18,9)}else{const left=direction==='left';if(!left){g.translate(24,0);g.scale(-1,1)}g.moveTo(17,21);g.lineTo(17,11);g.quadraticCurveTo(17,7,13,7);g.lineTo(3,7);g.moveTo(8,2);g.lineTo(3,7);g.lineTo(8,12)}g.stroke();g.restore()}
export function drawSignalMarker(g,m,light=false){g.save();const ink=light?'#28434e':'#dcebf1',bg=light?'#ffffff':'#132733';if(m.kind==='head'){g.fillStyle=ink;g.globalAlpha=.65;g.beginPath();g.arc(m.x,m.y,2,0,7);g.fill();g.restore();return}
 if(m.anchor&&Math.hypot(m.x-m.anchor[0],m.y-m.anchor[1])>8){g.strokeStyle=light?'#617d8b':'#9eb7c5';g.globalAlpha=.6;g.lineWidth=1;g.beginPath();g.moveTo(...m.anchor);g.lineTo(m.x,m.y);g.stroke();g.globalAlpha=1}
 g.translate(m.x,m.y);g.fillStyle=bg;g.strokeStyle=m.selected?(light?'#087b62':'#83efd0'):(light?'#79919c':'#7d97a6');g.lineWidth=m.selected?2:1;g.beginPath();g.roundRect(-m.width/2,-m.height/2,m.width,m.height,6);g.fill();g.stroke();g.fillStyle=ink;g.font='600 11px system-ui';g.textAlign='center';g.textBaseline='middle';g.fillText(m.label,0,m.height>24?-10:0);
 if(m.height>24){['left','straight','right'].forEach((d,i)=>{g.strokeStyle=movementColor(m.a,d);g.globalAlpha=m.a.movements[d]==='Permissive'&&!(m.a.movement_word&0x4000)?.35:1;drawTurn(g,d,-25+i*18,1,14)})}g.restore()}
export const turnIcon=direction=>`<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path ${direction==='right'?'transform="translate(24 0) scale(-1 1)"':''} d="${direction==='straight'?'M12 21V3M6 9l6-6 6 6':'M17 21V11Q17 7 13 7H3M8 2L3 7l5 5'}"/></svg>`;
