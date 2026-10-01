// Reduce a read-only Unreal export into independently loadable browser layers.
import fs from 'node:fs';
import {repairUV} from '../static/scene-attributes.js';
import {orientTriangles} from '../static/scene-winding.js';
import {bendGeometry} from './spline.mjs';
import {removeSplineInstances} from './scene-splines.mjs';
import {packLayers} from './scene-pack.mjs';
import {MeshoptSimplifier as S} from 'meshoptimizer';
await S.ready;
const root=new URL('../',import.meta.url).pathname,source=process.env.CARLA_SCENE_SOURCE||root+'data/scene-source',src=JSON.parse(fs.readFileSync(source+'/scene.json')),raw=fs.readFileSync(source+'/geometry.bin');
const worldLoadFile=source+'/world-load.json';if(fs.existsSync(worldLoadFile)){const world=JSON.parse(fs.readFileSync(worldLoadFile));if(world.expected_tiles&&world.tiles.length!==world.expected_tiles)throw Error('Incomplete streamed-town export');}
if(src.errors?.length)throw Error('Source export has errors; refusing to publish');
const mapName=src.map.split('/').pop(),out=root+'static/scenes/'+mapName+'/';fs.mkdirSync(out,{recursive:true});
for(const [path,m] of Object.entries(src.meshes)){if(m.category==='vegetation'&&!/vegetation|\/trees?\/|\/grass\/|\/bush/i.test(path))m.category='street';}
for(const g of Object.values(src.groups))g.category=src.meshes[g.mesh].category;
const counts={};for(const g of Object.values(src.groups))counts[g.mesh]=(counts[g.mesh]||0)+g.transforms.length;
const splineFile=source+'/splines.json',splineData=fs.existsSync(splineFile)?JSON.parse(fs.readFileSync(splineFile)):{splines:[]};if(splineData.errors?.length)throw Error('Spline export has errors');const splines=splineData.splines;
// Replace every undeformed spline instance with its baked geometry, exactly once.
removeSplineInstances(src.groups,splines);
const splineCounts={};for(const s of splines)splineCounts[s.mesh]=(splineCounts[s.mesh]||0)+1;
const layers={},report={repairedUVComponents:0,map:src.map,sourceInstances:0,instances:0,sourceTriangles:0,triangles:0,uniqueTriangles:0,bytes:0,layers:[],errors:src.errors,skipped:{...src.skipped},bakedSplines:splines.length};delete report.skipped.spline_deformation_not_baked;
function get(ref,type=Float32Array){return new type(raw.buffer,raw.byteOffset+ref[0],ref[1]).slice()}
for(const cat of ['roads','buildings','vegetation','street','props','water']){
 const entries=Object.entries(src.meshes).filter(([k,m])=>m.category===cat&&counts[k]);if(!entries.length)continue;
 const parts=[],meta={meshes:{},groups:[],materials:src.materials,category:cat},stats={category:cat,instances:0,triangles:0,uniqueTriangles:0,sourceTriangles:0};let offset=0;const reducedMeshes=new Map();
 const put=a=>{const b=Buffer.from(a.buffer,a.byteOffset,a.byteLength),r=[offset,a.length];parts.push(b);offset+=b.length;return r};
 for(const [key,m] of entries){
  const total=m.sections.reduce((n,s)=>n+s.index[1]/3,0),inst=counts[key];
  const roadSpline=cat==='roads'&&/curb|gutter/i.test(key)&&splineCounts[key]===inst;
  const budget=roadSpline?128:cat==='roads'?total:cat==='vegetation'?Math.max(64,Math.min(8000,200000/inst)):Math.max(100,Math.min(5000,40000/inst));
  const result=[],reduced=[];
  for(const section of m.sections){
   const p=get(section.position),n=get(section.normal),uv=get(section.uv);report.repairedUVComponents+=repairUV(p,uv);let ix=get(section.index,Uint32Array);orientTriangles(p,n,ix);stats.sourceTriangles+=ix.length/3*inst;
   const target=Math.min(ix.length,Math.max(36,Math.floor(budget*(ix.length/3)/Math.max(1,total))*3));
   if(ix.length>target&&(cat!=='roads'||roadSpline)){
    const [reduced]=S.simplify(ix,p,3,target,roadSpline?.003:.015,['Prune']);ix=reduced;
    // Dense Nanite fallback meshes often consist of disconnected triangles.
    // Cluster these only when topology preservation cannot reach the budget.
    if(ix.length>target*1.5&&!roadSpline){const [clustered]=S.simplifySloppy(ix,p,3,null,target,.025);if(clustered.length>=12)ix=clustered;}
   }
   if(!ix.length)continue;
   const [remap,count]=S.compactMesh(ix),pp=new Float32Array(count*3),nn=new Float32Array(count*3),tt=new Float32Array(count*2);
   for(let i=0;i<remap.length;i++)if(remap[i]!==0xffffffff){const j=remap[i];pp.set(p.subarray(i*3,i*3+3),j*3);nn.set(n.subarray(i*3,i*3+3),j*3);tt.set(uv.subarray(i*2,i*2+2),j*2);}
   reduced.push({position:pp,normal:nn,uv:tt,index:ix,slot:section.slot});result.push({position:put(pp),normal:put(nn),uv:put(tt),index:put(ix),slot:section.slot});stats.triangles+=ix.length/3*inst;stats.uniqueTriangles+=ix.length/3;
  }
  meta.meshes[key]={sections:result};reducedMeshes.set(key,reduced);
 }
 for(const g of Object.values(src.groups).filter(g=>meta.meshes[g.mesh]&&g.transforms.length)){meta.groups.push({...g,transforms:put(Float32Array.from(g.transforms.flat())),count:g.transforms.length});stats.instances+=g.transforms.length;}
 // Merge bent components by material and spatial tile to avoid one draw per fence piece.
 const baked=new Map();
 for(const spline of splines.filter(s=>reducedMeshes.has(s.mesh))){
  stats.instances++;
  for(const section of reducedMeshes.get(spline.mesh)){
   const [p,n]=bendGeometry(section.position,section.normal,spline),mat=spline.materials[section.slot],tile=Math.floor(p[0]/100)+','+Math.floor(p[2]/100),baseKey=tile+'|'+mat;let part=0,key=baseKey;
   while(baked.has(key)&&baked.get(key).vertices+p.length/3>750000)key=baseKey+'|part'+(++part);
   if(!baked.has(key))baked.set(key,{positions:[],normals:[],uvs:[],indices:[],vertices:0,mat});const b=baked.get(key);b.positions.push(p);b.normals.push(n);b.uvs.push(section.uv);b.indices.push(Uint32Array.from(section.index,x=>x+b.vertices));b.vertices+=p.length/3;
  }
 }
 const concat=(parts,Type)=>{const a=new Type(parts.reduce((n,p)=>n+p.length,0));let offset=0;for(const p of parts){a.set(p,offset);offset+=p.length}return a};
 for(const [key,b] of baked){const name='spline:'+key,ix=concat(b.indices,Uint32Array);meta.meshes[name]={sections:[{position:put(concat(b.positions,Float32Array)),normal:put(concat(b.normals,Float32Array)),uv:put(concat(b.uvs,Float32Array)),index:put(ix),slot:0}]};meta.groups.push({mesh:name,category:cat,materials:[b.mat],transforms:put(new Float32Array([0,0,0,0,0,0,1,1,1,1])),count:1});stats.uniqueTriangles+=ix.length/3;}
 for(const {packed,layer} of packLayers(meta,Buffer.concat(parts))){
  fs.writeFileSync(out+layer.file,packed);report.layers.push(layer);report.instances+=layer.instances;report.triangles+=layer.triangles;report.uniqueTriangles+=layer.uniqueTriangles;report.bytes+=packed.length;console.log(layer);
 }
 report.sourceTriangles+=stats.sourceTriangles;
}
report.sourceInstances=Object.values(src.groups).reduce((n,g)=>n+g.transforms.length,0)+splines.length;
const textureReportPath=source+'/texture-report.json';if(fs.existsSync(textureReportPath)){const textures=JSON.parse(fs.readFileSync(textureReportPath));report.geometryBytes=report.bytes;report.textureBytes=textures.bytes;report.texturePixels=textures.pixels;report.textures=textures.textures;report.bytes+=textures.bytes;}
const manifest={version:1,map:src.map,coordinates:'x,z,y metres',generated:new Date().toISOString(),layers:report.layers,summary:report,limitations:['Static material approximation; Unreal lighting, animated effects and projected decals are not reproduced.','Animated skeletal meshes and particle systems use live map symbols or are omitted.']};
fs.writeFileSync(out+'manifest.json.tmp',JSON.stringify(manifest));fs.renameSync(out+'manifest.json.tmp',out+'manifest.json');fs.writeFileSync(source+'/build-report.json',JSON.stringify(report,null,2));
