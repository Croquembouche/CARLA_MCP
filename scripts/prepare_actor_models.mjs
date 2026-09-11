import fs from 'node:fs';
import {MeshoptSimplifier as S} from 'meshoptimizer';
await S.ready;
const root='static/actors/',manifest=JSON.parse(fs.readFileSync(root+'manifest.json')),files=new Set(Object.entries(manifest.models).filter(([id])=>!process.env.ACTOR_MODEL_IDS||JSON.parse(process.env.ACTOR_MODEL_IDS).includes(id)).map(([,m])=>m).flatMap(m=>m.parts.map(p=>p.file)));
fs.mkdirSync('data/actor-model-source',{recursive:true});const report=[];
const sizes={5120:1,5121:1,5122:2,5123:2,5125:4,5126:4},counts={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16};
const types={5120:Int8Array,5121:Uint8Array,5122:Int16Array,5123:Uint16Array,5125:Uint32Array,5126:Float32Array};
for(const file of files){
 const backup='data/actor-model-source/'+file;if(!fs.existsSync(backup))fs.copyFileSync(root+file,backup);
 const raw=fs.readFileSync(backup),length=raw.readUInt32LE(12),j=JSON.parse(raw.subarray(20,20+length)),bin=raw.subarray(28+length),newViews=new Map();
 function array(id){const a=j.accessors[id],v=j.bufferViews[a.bufferView],n=counts[a.type],size=sizes[a.componentType],T=types[a.componentType],out=new T(a.count*n),source=newViews.get(a.bufferView)||bin.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength);for(let i=0;i<a.count;i++){const start=(a.byteOffset||0)+i*(v.byteStride||n*size);new Uint8Array(out.buffer,i*n*size,n*size).set(source.subarray(start,start+n*size))}return out}
 function accessor(values,old,kind){const data=Buffer.from(values.buffer,values.byteOffset,values.byteLength),vi=j.bufferViews.length;j.bufferViews.push({buffer:0,byteLength:data.length});newViews.set(vi,data);const a={...old,bufferView:vi,byteOffset:0,count:values.length/counts[old.type]};delete a.min;delete a.max;if(kind==='POSITION'){a.min=[Infinity,Infinity,Infinity];a.max=[-Infinity,-Infinity,-Infinity];for(let i=0;i<values.length;i++){a.min[i%3]=Math.min(a.min[i%3],values[i]);a.max[i%3]=Math.max(a.max[i%3],values[i])}}return j.accessors.push(a)-1}
 let before=0,after=0;
 for(const mesh of j.meshes||[]){const total=mesh.primitives.reduce((n,p)=>n+(p.indices!=null?j.accessors[p.indices].count/3:0),0);for(const p of mesh.primitives){
  if(p.indices==null||p.mode!=null&&p.mode!==4)continue;
  let ix=Uint32Array.from(array(p.indices));before+=ix.length/3;const pos=array(p.attributes.POSITION),target=Math.max(36,Math.floor(20000/Math.max(total,1)*ix.length/3)*3);
  if(ix.length>target){const [reduced]=S.simplify(ix,pos,3,target,.008,['Prune']);ix=reduced;
   const [remap,count]=S.compactMesh(ix);
   for(const [kind,id] of Object.entries(p.attributes)){const a=j.accessors[id],source=array(id),stride=counts[a.type],values=new types[a.componentType](count*stride);for(let i=0;i<remap.length;i++)if(remap[i]!==0xffffffff)values.set(source.subarray(i*stride,(i+1)*stride),remap[i]*stride);p.attributes[kind]=accessor(values,a,kind)}
   p.indices=accessor(ix,{componentType:5125,type:'SCALAR'},'indices');
  }
  after+=ix.length/3;
 }}
 const ids=new Set();for(const m of j.meshes||[])for(const p of m.primitives){Object.values(p.attributes).forEach(i=>ids.add(i));if(p.indices!=null)ids.add(p.indices);for(const t of p.targets||[])Object.values(t).forEach(i=>ids.add(i))}for(const s of j.skins||[])if(s.inverseBindMatrices!=null)ids.add(s.inverseBindMatrices);for(const a of j.animations||[])for(const s of a.samplers){ids.add(s.input);ids.add(s.output)}
 const map=new Map([...ids].map((id,i)=>[id,i]));for(const m of j.meshes||[])for(const p of m.primitives){for(const k in p.attributes)p.attributes[k]=map.get(p.attributes[k]);if(p.indices!=null)p.indices=map.get(p.indices);for(const t of p.targets||[])for(const k in t)t[k]=map.get(t[k])}for(const s of j.skins||[])if(s.inverseBindMatrices!=null)s.inverseBindMatrices=map.get(s.inverseBindMatrices);for(const a of j.animations||[])for(const s of a.samplers){s.input=map.get(s.input);s.output=map.get(s.output)}j.accessors=[...ids].map(i=>j.accessors[i]);
 const views=new Set(j.accessors.map(a=>a.bufferView));for(const image of j.images||[])if(image.bufferView!=null)views.add(image.bufferView);
 const vm=new Map([...views].map((id,i)=>[id,i])),parts=[];let offset=0;const newBV=[];
 for(const id of views){const v=j.bufferViews[id],data=newViews.get(id)||bin.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength);newBV.push({...v,byteOffset:offset});parts.push(data);offset+=data.length;const pad=(4-offset%4)%4;parts.push(Buffer.alloc(pad));offset+=pad}
 for(const a of j.accessors)a.bufferView=vm.get(a.bufferView);for(const i of j.images||[])if(i.bufferView!=null)i.bufferView=vm.get(i.bufferView);j.bufferViews=newBV;j.buffers=[{byteLength:offset}];
 const json=Buffer.from(JSON.stringify(j)),jp=Buffer.alloc((4-json.length%4)%4,32),header=Buffer.alloc(20),bh=Buffer.alloc(8);header.write('glTF');header.writeUInt32LE(2,4);header.writeUInt32LE(28+json.length+jp.length+offset,8);header.writeUInt32LE(json.length+jp.length,12);header.write('JSON',16);bh.writeUInt32LE(offset);bh.write('BIN\0',4);const result=Buffer.concat([header,json,jp,bh,...parts]);fs.writeFileSync(root+file,result);report.push({file,before,after,sourceBytes:raw.length,bytes:result.length});
}
fs.writeFileSync('data/actor-model-optimization.json',JSON.stringify(report,null,2));console.log({files:report.length,triangles:report.reduce((n,x)=>n+x.after,0),sourceTriangles:report.reduce((n,x)=>n+x.before,0),bytes:report.reduce((n,x)=>n+x.bytes,0),sourceBytes:report.reduce((n,x)=>n+x.sourceBytes,0)});
