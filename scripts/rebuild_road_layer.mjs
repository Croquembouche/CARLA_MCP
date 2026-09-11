// Preserve source road boundaries and paint instead of Unreal's coarse Nanite fallback.
import * as THREE from 'three';import fs from 'node:fs';import zlib from 'node:zlib';import crypto from 'node:crypto';import {MeshoptSimplifier as S} from 'meshoptimizer';await S.ready;
const root='static/scenes/Town10HD_Opt/',manifest=JSON.parse(fs.readFileSync(root+'manifest.json'));
if(!fs.existsSync('data/road-render-backup/manifest.json'))fs.writeFileSync('data/road-render-backup/manifest.json',JSON.stringify(manifest));
const original=JSON.parse(fs.readFileSync('data/road-render-backup/manifest.json')),layer=original.layers.find(l=>l.category==='roads'),bytes=zlib.gunzipSync(fs.readFileSync(root+layer.file)),n=bytes.readUInt32LE(),meta=JSON.parse(bytes.subarray(4,4+n)),base=(4+n+3)&~3;
const old=(r,T=Float32Array)=>new T(bytes.buffer,bytes.byteOffset+base+r[0],r[1]);
const currentBytes=zlib.gunzipSync(fs.readFileSync(root+manifest.layers.find(l=>l.category==='roads').file)),currentLength=currentBytes.readUInt32LE();meta.materials=JSON.parse(currentBytes.subarray(4,4+currentLength)).materials;
const parts=[];let offset=0;const put=a=>{const b=Buffer.from(a.buffer,a.byteOffset,a.byteLength),r=[offset,a.length];parts.push(b);offset+=b.length;return r};const report=[];
for(const [key,mesh] of Object.entries(meta.meshes)){
 const file='data/road-source/'+key.split('/').at(-1).split('.')[0]+'.glb';let sections;
 if(key.includes('SM_Town10HD_')){
  const raw=fs.readFileSync(file),length=raw.readUInt32LE(12),g=JSON.parse(raw.subarray(20,20+length)),bin=raw.subarray(28+length);
  if(!g.meshes?.length)throw Error('Source export is empty: '+file);
  const array=id=>{const a=g.accessors[id],v=g.bufferViews[a.bufferView],T={5123:Uint16Array,5125:Uint32Array,5126:Float32Array}[a.componentType],size={SCALAR:1,VEC2:2,VEC3:3,VEC4:4}[a.type];if(v.byteStride)throw Error('Unexpected interleaved source');return new T(bin.buffer,bin.byteOffset+(v.byteOffset||0)+(a.byteOffset||0),a.count*size)};
  let before=0,after=0;sections=[];
  for(const p of g.meshes.flatMap(m=>m.primitives)){
   let positions=array(p.attributes.POSITION),uv=array(p.attributes.TEXCOORD_0);let indices=Uint32Array.from(array(p.indices)),normals;if(p.attributes.NORMAL!=null)normals=array(p.attributes.NORMAL);else{const geom=new THREE.BufferGeometry();geom.setAttribute('position',new THREE.BufferAttribute(positions,3));geom.setIndex(new THREE.BufferAttribute(indices,1));geom.computeVertexNormals();normals=geom.getAttribute('normal').array;}before+=indices.length/3;
   // The source exporter expands vertices per triangle. Rejoin identical surface
   // positions/UVs so interior edges are not mistaken for protected boundaries.
   const welded=new Map(),wp=[],wu=[],wn=[],wi=new Uint32Array(indices.length);
   for(let i=0;i<indices.length;i++){
    const id=indices[i],key=[Math.round(positions[id*3]*1e5),Math.round(positions[id*3+1]*1e5),Math.round(positions[id*3+2]*1e5),Math.round(uv[id*2]*1e5),Math.round(uv[id*2+1]*1e5)].join(',');
    let index=welded.get(key);if(index===undefined){index=wp.length/3;welded.set(key,index);wp.push(...positions.subarray(id*3,id*3+3));wu.push(...uv.subarray(id*2,id*2+2));wn.push(0,0,0)}
    wi[i]=index;for(let k=0;k<3;k++)wn[index*3+k]+=normals[id*3+k];
   }
   for(let i=0;i<wn.length;i+=3){const length=Math.hypot(wn[i],wn[i+1],wn[i+2])||1;for(let k=0;k<3;k++)wn[i+k]/=length}
   positions=Float32Array.from(wp);uv=Float32Array.from(wu);normals=Float32Array.from(wn);indices=wi;
   const target=Math.max(6000,Math.floor(indices.length*.15/3)*3);
   if(indices.length>target)[indices]=S.simplify(indices,positions,3,target,.00001,['LockBorder']);
   const [remap,count]=S.compactMesh(indices),pp=new Float32Array(count*3),nn=new Float32Array(count*3),tt=new Float32Array(count*2);
   for(let i=0;i<remap.length;i++)if(remap[i]!==0xffffffff){const j=remap[i];pp.set(positions.subarray(i*3,i*3+3),j*3);nn.set(normals.subarray(i*3,i*3+3),j*3);tt.set(uv.subarray(i*2,i*2+2),j*2)}
   after+=indices.length/3;sections.push({position:pp,normal:nn,uv:tt,index:indices,slot:p.material||0});
  }
  report.push({mesh:key,before,after});
 }else sections=mesh.sections.map(s=>({position:old(s.position),normal:old(s.normal),uv:old(s.uv),index:old(s.index,Uint32Array),slot:s.slot}));
 mesh.sections=sections.map(s=>({position:put(s.position),normal:put(s.normal),uv:put(s.uv),index:put(s.index),slot:s.slot}));
}
for(const batch of meta.groups)batch.transforms=put(old(batch.transforms));
const triangles=meta.groups.reduce((n,g)=>n+meta.meshes[g.mesh].sections.reduce((n,s)=>n+s.index[1]/3,0)*g.count,0),uniqueTriangles=Object.values(meta.meshes).reduce((n,m)=>n+m.sections.reduce((n,s)=>n+s.index[1]/3,0),0);
const header=Buffer.from(JSON.stringify(meta)),size=Buffer.alloc(4);size.writeUInt32LE(header.length);const packed=zlib.gzipSync(Buffer.concat([size,header,Buffer.alloc((4-header.length%4)%4),...parts]),{level:9});
const file='roads-'+crypto.createHash('sha256').update(packed).digest('hex').slice(0,12)+'.scene.gz';fs.writeFileSync(root+file,packed);
const previous=manifest.layers.find(l=>l.category==='roads'),updated={...previous,file,bytes:packed.length,decodedBytes:4+header.length+(4-header.length%4)%4+offset,triangles,uniqueTriangles};
manifest.layers=manifest.layers.map(l=>l.category==='roads'?updated:l);manifest.summary.layers=manifest.layers;for(const [k,delta] of Object.entries({triangles:triangles-previous.triangles,uniqueTriangles:uniqueTriangles-previous.uniqueTriangles,bytes:packed.length-previous.bytes,geometryBytes:packed.length-previous.bytes}))manifest.summary[k]+=delta;manifest.sourceRoadMeshes=true;
fs.writeFileSync(root+'manifest.json.tmp',JSON.stringify(manifest));fs.renameSync(root+'manifest.json.tmp',root+'manifest.json');fs.writeFileSync('data/road-source-upgrade.json',JSON.stringify({report,layer:updated},null,2));console.log({meshes:report.length,triangles,bytes:packed.length});
