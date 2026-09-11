import assert from 'node:assert/strict';
import fs from 'node:fs';
import zlib from 'node:zlib';
import * as THREE from 'three';
import {roadArea,overlapsArea,buildingInArea} from '../static/scene-area.js';
const square={lanes:[{points:[[0,0,100,4],[100,100,100,4]]}]};
assert.deepEqual(roadArea(square),[-27,-27,127,127]);
assert.equal(roadArea({lanes:[]}),null);
assert(overlapsArea(null,1000,1000,1010,1010));
assert(overlapsArea(roadArea(square),40,40,60,60),'keep central blocks even away from a lane');
assert(!overlapsArea(roadArea(square),200,40,250,60));
assert(buildingInArea({x:135,y:50,yaw:90,extent:{x:2,y:10}},roadArea(square)),'rotated edge building intersects');
assert(!buildingInArea({x:135,y:50,yaw:0,extent:{x:2,y:10}},roadArea(square)));
const map=JSON.parse(fs.readFileSync('data/map-cache.json')),area=roadArea(map);
const root='static/scenes/Town10HD_Opt/',manifest=JSON.parse(fs.readFileSync(root+'manifest.json'));
const report={area,layers:[],fallback:{full:map.buildings.length,road:map.buildings.filter(b=>buildingInArea(b,area)).length}};
for(const layer of manifest.layers){
 const bytes=zlib.gunzipSync(fs.readFileSync(root+layer.file)),length=bytes.readUInt32LE(),meta=JSON.parse(bytes.subarray(4,4+length)),base=(4+length+3)&~3;
 const array=(r,Type=Float32Array)=>new Type(bytes.buffer,bytes.byteOffset+base+r[0],r[1]);
 const bounds=new Map();
 for(const [key,m] of Object.entries(meta.meshes)){
  const box=new THREE.Box3();for(const section of m.sections){const p=array(section.position);for(let i=0;i<p.length;i+=3)box.expandByPoint(new THREE.Vector3(p[i],p[i+1],p[i+2]))}bounds.set(key,box);
 }
 const result={category:layer.category,full:0,road:0,fullTriangles:0,roadTriangles:0};
 for(const g of meta.groups){
  const transforms=array(g.transforms),triangles=meta.meshes[g.mesh].sections.reduce((n,s)=>n+s.index[1]/3,0);
  for(let i=0;i<g.count;i++){
   const t=transforms.subarray(i*10,i*10+10),object=new THREE.Object3D();object.position.fromArray(t);object.quaternion.fromArray(t,3);object.scale.fromArray(t,7);object.updateMatrix();
   const b=bounds.get(g.mesh).clone().applyMatrix4(object.matrix);
   result.full++;result.fullTriangles+=triangles;
   if(layer.category==='roads'||overlapsArea(area,b.min.x,b.min.z,b.max.x,b.max.z)){result.road++;result.roadTriangles+=triangles}
  }
 }
 assert.equal(result.fullTriangles,layer.triangles);
 report.layers.push(result);
}
const roads=report.layers.find(l=>l.category==='roads'),buildings=report.layers.find(l=>l.category==='buildings');
assert.equal(roads.road,roads.full,'all original road meshes retained');
assert(buildings.road>500,'near-road detail retained');assert(buildings.road<buildings.full*.5,'peripheral buildings substantially reduced');
assert(report.fallback.road>0&&report.fallback.road<report.fallback.full);
fs.writeFileSync('data/scene-area-verification.json',JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
console.log('PASS: road envelope, central blocks, rotated buildings, empty map fallback, complete roads, real scene counts.');
const {areaPlanes}=await import('../static/scene-detail.js');
const planes=areaPlanes(area);
for(const p of planes)assert(p.distanceToPoint(new THREE.Vector3((area[0]+area[2])/2,100,(area[1]+area[3])/2))>0);
assert(planes.some(p=>p.distanceToPoint(new THREE.Vector3(area[0]-1,0,0))<0));
assert.deepEqual(areaPlanes(null),[]);
console.log('PASS: scene boundary planes retain the road area and full mode removes clipping.');
