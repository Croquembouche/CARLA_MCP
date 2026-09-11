import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const {signalGroups,signalMarkers,markerAt}=await import('data:text/javascript;base64,'+Buffer.from(await readFile(new URL('../static/signals.js',import.meta.url))).toString('base64'));
const signal=(id,group_id,x,y)=>({id,group_id,type:'traffic.traffic_light',pose:{x,y,z:0},heads:[0,1,2].map(i=>({x:x+i,y,z:0})),movements:{left:'Stop',straight:'Protected',right:'Permissive'}});
const actors=[signal(8,8,0,0),signal(9,8,10,0),signal(16,8,0,10),signal(15,15,35,0),signal(17,15,45,0)];
const project=p=>[p.x,p.y];
const badges=ms=>ms.filter(m=>m.kind!=='head');
const overview=signalMarkers(actors,null,project);
assert.equal(overview.length,2);assert.ok(overview.every(m=>m.kind==='group'));
assert.equal(signalGroups(actors)[0].members.length,3);
const selected=signalMarkers(actors,8,project);
assert.equal(badges(selected).length,4);assert.equal(selected.filter(m=>m.kind==='approach').length,3);
const close=signalMarkers(actors,null,p=>[p.x*30,p.y*30]);
assert.equal(close.filter(m=>m.kind==='head').length,15);assert.ok(close.some(m=>m.detailed));
for(const ms of [overview,selected,close,signalMarkers(actors,8,()=>[100,100])]){
 const bs=badges(ms);for(let i=0;i<bs.length;i++){assert.equal(markerAt(ms,bs[i].x,bs[i].y),bs[i]);for(let j=0;j<i;j++)assert.ok(Math.abs(bs[i].x-bs[j].x)>=(bs[i].width+bs[j].width)/2||Math.abs(bs[i].y-bs[j].y)>=(bs[i].height+bs[j].height)/2,'badges must not overlap')}
}
assert.equal(markerAt(overview,-1000,-1000),undefined);
assert.deepEqual(signalMarkers(actors,null,()=>null),[]);
console.log('Signal layout passed: overview grouping, selected approaches, zoom detail, overlap avoidance, visible-marker picking.');
