// Sidewalk geometry is distinct from the simulator's pedestrian navigation mesh.
export function pedestrianRole(kind,selected,managed,creationRole){return (kind==='goal'&&managed?.[selected]?managed[selected].role:creationRole)==='pedestrian'}
export function snapPedestrian(map,p){
 let best=null,distance=Infinity;
 for(const lane of map.pedestrian_lanes||[])for(let i=1;i<lane.points.length;i++){
  const a=lane.points[i-1],b=lane.points[i],dx=b[0]-a[0],dy=b[1]-a[1],length=dx*dx+dy*dy,t=length?Math.max(0,Math.min(1,((p.x-a[0])*dx+(p.y-a[1])*dy)/length)):0;
  const q={x:a[0]+t*dx,y:a[1]+t*dy,z:a[2]+t*(b[2]-a[2])},d=Math.hypot(q.x-p.x,q.y-p.y);
  if(d<distance&&d<=Math.max(5,(a[3]+t*(b[3]-a[3]))/2+2)){best={...q,lane:lane.id};distance=d}
 }
 for(const q of map.pedestrian_points||[]){const d=Math.hypot(q.x-p.x,q.y-p.y);if(d<=2&&d<distance){best={x:q.x,y:q.y,z:q.z};distance=d}}
 return best;
}
export function drawPedestrianMap(ctx,map,scale,light){
 ctx.save();ctx.lineCap='butt';
 for(const l of map.pedestrian_lanes||[]){
  ctx.beginPath();l.points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));
  ctx.strokeStyle=light?'#b5dcef':'#294e68';ctx.lineWidth=l.points[0][3];ctx.stroke();
  ctx.strokeStyle=light?'#26729c':'#78b8e2';ctx.lineWidth=Math.max(.18,.65/scale);ctx.setLineDash([1.5,2]);ctx.stroke();ctx.setLineDash([]);
 }
 for(const c of map.crosswalks||[]){ctx.beginPath();c.points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fillStyle=light?'#4299bb44':'#92caed44';ctx.fill();ctx.strokeStyle=light?'#32799a':'#8abfdd';ctx.lineWidth=.6/scale;ctx.setLineDash([1,1]);ctx.stroke();ctx.setLineDash([])}
 ctx.restore();
}
