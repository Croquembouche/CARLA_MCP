// Split large categories at mesh boundaries; keep each browser decode bounded.
import zlib from 'node:zlib';
import crypto from 'node:crypto';
export function packLayers(meta,binary,limit=96*1024*1024){
 const batches=[];let keys=[],size=0;
 for(const [key,mesh] of Object.entries(meta.meshes)){
  const groups=meta.groups.filter(g=>g.mesh===key);if(!groups.length)continue;
  const bytes=mesh.sections.reduce((n,s)=>n+['position','normal','uv','index'].reduce((n,k)=>n+s[k][1]*4,0),0)+groups.reduce((n,g)=>n+g.transforms[1]*4,0);
  if(bytes>limit)throw Error(`Mesh exceeds scene chunk budget: ${key}`);
  if(size+bytes>limit&&keys.length){batches.push(keys);keys=[];size=0}keys.push(key);size+=bytes;
 }
 if(keys.length)batches.push(keys);
 return batches.map((keys,i)=>{
  const selected=new Set(keys),parts=[],copy={category:meta.category,meshes:{},groups:[],materials:{}};let offset=0;
  const put=ref=>{const bytes=binary.subarray(ref[0],ref[0]+ref[1]*4),r=[offset,ref[1]];parts.push(bytes);offset+=bytes.length;return r};
  for(const key of keys)copy.meshes[key]={sections:meta.meshes[key].sections.map(s=>({...s,position:put(s.position),normal:put(s.normal),uv:put(s.uv),index:put(s.index)}))};
  let instances=0,triangles=0,uniqueTriangles=0;
  for(const mesh of Object.values(copy.meshes))uniqueTriangles+=mesh.sections.reduce((n,s)=>n+s.index[1]/3,0);
  for(const g of meta.groups.filter(g=>selected.has(g.mesh))){copy.groups.push({...g,transforms:put(g.transforms)});instances+=g.count;triangles+=g.count*copy.meshes[g.mesh].sections.reduce((n,s)=>n+s.index[1]/3,0);for(const m of g.materials)if(meta.materials[m])copy.materials[m]=meta.materials[m]}
  const header=Buffer.from(JSON.stringify(copy)),pad=Buffer.alloc((4-header.length%4)%4),prefix=Buffer.alloc(4);prefix.writeUInt32LE(header.length);
  const packed=zlib.gzipSync(Buffer.concat([prefix,header,pad,...parts]),{level:6});const hash=crypto.createHash('sha256').update(packed).digest('hex').slice(0,12);
  return {packed,layer:{category:meta.category,chunk:i,instances,triangles,uniqueTriangles,file:meta.category+'-'+hash+'.scene.gz',bytes:packed.length,decodedBytes:4+header.length+pad.length+offset}};
 });
}
