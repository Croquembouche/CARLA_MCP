// Glyph coordinates: x forward, y right in CARLA's left-handed road plane.
export function glyph(m){
 const segments=[];
 const arrow=points=>{segments.push(points);const a=points.at(-2),b=points.at(-1),angle=Math.atan2(b[1]-a[1],b[0]-a[0]);for(const side of [-1,1])segments.push([b,[b[0]-.55*Math.cos(angle)+side*.4*Math.sin(angle),b[1]-.55*Math.sin(angle)-side*.4*Math.cos(angle)]])};
 if(m.kind==='direction')arrow([[-1.5,0],[1.5,0]]);
 else for(const turn of m.turns){if(turn==='straight')arrow([[-1.7,0],[1.7,0]]);else if(turn==='uturn')arrow([[-1.7,0],[.8,0],[.8,-1],[-.4,-1]]);else arrow([[-1.7,0],[.5,0],[.5,turn==='left'?-1.2:1.2]])}
 return segments;
}
export function markingLines(map){const out=[];for(const m of map.markings||[]){const a=m.yaw*Math.PI/180,c=Math.cos(a),s=Math.sin(a);for(const line of glyph(m))for(let i=1;i<line.length;i++){for(const p of [line[i-1],line[i]])out.push(m.x+p[0]*c-p[1]*s,m.z+.16,m.y+p[0]*s+p[1]*c)}}return out}
export function laneAt(map,x,y){let best=null,d=Infinity;for(const l of map.lanes||[])for(const p of l.points){const n=Math.hypot(p[0]-x,p[1]-y);if(n<d){d=n;best=l}}return d<5?best:null}
export function laneDescription(l){return l?`Lane ${l.id} · ${l.junction?'Junction connector':l.maneuvers?.length?l.maneuvers.map(t=>t==='uturn'?'U-turn':t[0].toUpperCase()+t.slice(1)).join(' / '):'Follow lane'} · arrows show travel direction`:''}
