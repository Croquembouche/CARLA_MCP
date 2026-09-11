import * as THREE from 'three';
const palette={roads:0x777b7c,buildings:0xa8b3b7,vegetation:0x477d45,street:0x7e8990,props:0x9b8f7d,water:0x3b778d};
export function release(group){const geometries=new Set(),materials=new Set(),textures=new Set();group.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of o.material?(Array.isArray(o.material)?o.material:[o.material]):[])materials.add(m)});for(const m of materials){for(const t of Object.values(m))if(t?.isTexture)textures.add(t);m.dispose()}for(const g of geometries)g.dispose();for(const t of textures){t.dispose();t.image?.close?.()}group.clear()}
function colour(info,category){const name=(info?.name||'').toLowerCase();const tint=Object.entries(info?.vectors||{}).find(([k,v])=>/^(base.?color|diffuse.?color|color|tint)$/i.test(k)&&v.slice(0,3).some(x=>x>0));if(tint)return new THREE.Color(...tint[1].slice(0,3));if(/glass|window/.test(name))return new THREE.Color(0x496a7b);if(/leaf|leaves|grass|foliage/.test(name))return new THREE.Color(0x4e793c);if(/bark|wood|trunk/.test(name))return new THREE.Color(0x7c6753);if(/line|marking/.test(name))return new THREE.Color(0xe3ded0);if(/asphalt|road/.test(name))return new THREE.Color(0x5b6265);if(/brick/.test(name))return new THREE.Color(0xa57f6b);return new THREE.Color(palette[category]||0xa4b0b5)}
export async function fetchLayer(url,signal,onProgress,textureCache=new Map()){
 const response=await fetch(url,{signal});if(!response.ok)throw Error('Scene layer download failed ('+response.status+')');
 const bytes=await response.arrayBuffer();if(bytes.byteLength>96*1024*1024)throw Error('Scene layer exceeds transfer budget');
 const decoded=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
 if(decoded.byteLength>256*1024*1024)throw Error('Scene layer exceeds memory budget');
 const length=new DataView(decoded).getUint32(0,true),meta=JSON.parse(new TextDecoder().decode(new Uint8Array(decoded,4,length))),base=4+length+(4-length%4)%4;
 const attribute=(r,type=Float32Array)=>new type(decoded,base+r[0],r[1]);
 const group=new THREE.Group(),geometries=new Map(),materials=new Map();group.name=meta.category;
 try{
 const usedMeshes=new Set(meta.groups.map(g=>g.mesh));for(const [key,m] of Object.entries(meta.meshes).filter(([key])=>usedMeshes.has(key)))geometries.set(key,m.sections.map(s=>{const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(attribute(s.position),3));g.setAttribute('normal',new THREE.BufferAttribute(attribute(s.normal),3));g.setAttribute('uv',new THREE.BufferAttribute(attribute(s.uv),2));g.setIndex(new THREE.BufferAttribute(attribute(s.index,Uint32Array),1));g.computeBoundingSphere();return {geometry:g,slot:s.slot}}));
 let count=0;
 for(const batch of meta.groups){
  if(signal.aborted)throw new DOMException('Aborted','AbortError');
  const transforms=attribute(batch.transforms),tiles=new Map();
  for(let i=0;i<batch.count;i++){const t=transforms.subarray(i*10,i*10+10),key=Math.floor(t[0]/100)+','+Math.floor(t[2]/100);if(!tiles.has(key))tiles.set(key,[]);tiles.get(key).push(t);}
  for(const {geometry,slot} of geometries.get(batch.mesh)){
   const materialKey=batch.materials[slot]||meta.category;
   if(!materials.has(materialKey)){
    const info=meta.materials[materialKey];let texture=null;
    if(info?.web_texture&&!/lanemarking/i.test(info.name)){const path=new URL('textures/'+info.web_texture,new URL(url,location.href)).href;
     if(!textureCache.has(path)){const response=await fetch(path,{signal});if(!response.ok)throw Error('Scene texture missing');const bitmap=await createImageBitmap(await response.blob());const t=new THREE.Texture(bitmap);t.colorSpace=THREE.SRGBColorSpace;t.wrapS=t.wrapT=THREE.RepeatWrapping;t.flipY=false;t.needsUpdate=true;textureCache.set(path,t);}
     texture=textureCache.get(path);
    }
    const laneColor=info?.vectors?.LaneColor;const color=texture?new THREE.Color(0xffffff):/lanemarking/i.test(info?.name||'')&&laneColor?new THREE.Color(...laneColor.slice(0,3)):colour(info,meta.category);
    const material=new THREE.MeshLambertMaterial({color,map:texture,alphaTest:texture&&(info?.browser_alpha||(meta.category==='vegetation'&&info?.blend?.includes('MASKED')))?.4:0,side:THREE.DoubleSide});materials.set(materialKey,material);
   }
   for(const tile of tiles.values()){
    const inst=new THREE.InstancedMesh(geometry,materials.get(materialKey),tile.length),o=new THREE.Object3D();
    tile.forEach((t,i)=>{o.position.fromArray(t);o.quaternion.fromArray(t,3);o.scale.fromArray(t,7);o.updateMatrix();inst.setMatrixAt(i,o.matrix)});inst.computeBoundingSphere();inst.userData.sceneLayer=meta.category;group.add(inst);
   }
  }
  if(++count%30===0){onProgress?.();await new Promise(r=>setTimeout(r,0));}
 }
 group.userData={instances:meta.groups.reduce((n,g)=>n+g.count,0),category:meta.category};return group;
 }catch(e){release(group);for(const sections of geometries.values())for(const s of sections)s.geometry.dispose();for(const m of materials.values())m.dispose();throw e}
}
export class SceneDetail{
 constructor(view,status){this.view=view;this.status=status;this.group=new THREE.Group();view.scene.add(this.group);this.layers=new Map();this.enabled=true;this.hidden=new Set();this.serial=0;}
 async load(map){
  const mapName=map.name.split('/').pop();this.map=map;
  if(this.mapName===mapName&&(this.loading||this.layers.size)){this.view.fallback.visible=!this.enabled||!this.layers.has('roads');return}
  this.mapName=mapName;if(!this.enabled){this.status('Lightweight map · select Detailed geometry to load scene objects');return}this.loading=true;
  const serial=++this.serial;const textureCache=new Map();this.abort?.abort();this.abort=new AbortController();release(this.group);this.layers.clear();this.view.fallback.visible=true;this.group.visible=this.enabled;this.status('Loading actual scene geometry…');
  const name=map.name.split('/').pop(),base='/scenes/'+encodeURIComponent(name)+'/';
  try{
   const response=await fetch(base+'manifest.json',{signal:this.abort.signal,cache:'no-cache'});if(response.status===404){this.loading=false;this.status('Lightweight map · detailed geometry is not exported for this map yet');return}if(!response.ok)throw Error('Scene manifest unavailable');
   const manifest=await response.json();if(manifest.map.split('/').pop()!==name)throw Error('Scene geometry belongs to another map');
   this.manifest=manifest;this.view.node.dataset.sceneLoading='true';let completed=0;
   for(const layer of manifest.layers){
    if(serial!==this.serial)return;
    this.status(`Loading ${layer.category} · ${completed}/${manifest.layers.length} layers`);
    const group=await fetchLayer(base+layer.file,this.abort.signal,undefined,textureCache);
    if(serial!==this.serial){release(group);return}
    group.visible=!this.hidden.has(layer.category);this.layers.set(layer.category,group);this.group.add(group);completed++;
    if(layer.category==='roads')this.view.fallback.visible=!this.enabled;
    this.view.render();
   }
   this.loading=false;this.view.node.dataset.sceneLoading='false';this.view.node.dataset.sceneInstances=String(manifest.summary.instances);this.view.node.dataset.sceneTriangles=String(manifest.summary.triangles);
   this.status(`${manifest.summary.instances.toLocaleString()} objects · ${(manifest.summary.triangles/1e6).toFixed(1)}M triangles · ${(manifest.summary.bytes/1048576).toFixed(1)} MiB`);this.view.render();
  }catch(e){if(serial===this.serial)this.loading=false;if(e.name!=='AbortError'&&serial===this.serial){this.view.node.dataset.sceneLoading='false';release(this.group);this.layers.clear();this.view.fallback.visible=true;for(const t of textureCache.values()){t.dispose();t.image?.close?.()}this.status('Lightweight fallback · scene detail could not load: '+e.message);this.view.render()}}
 }
 setEnabled(enabled){this.enabled=enabled;this.group.visible=enabled;
  if(!enabled){++this.serial;this.abort?.abort();this.loading=false;release(this.group);this.layers.clear();this.view.node.dataset.sceneLoading='false';this.status('Lightweight map · detailed geometry unloaded');this.view.fallback.visible=true;}
  else if(this.map)this.load(this.map);
  this.view.render()
 }
 setLayer(name,visible){if(visible)this.hidden.delete(name);else this.hidden.add(name);if(this.layers.has(name))this.layers.get(name).visible=visible;this.view.render()}
}
