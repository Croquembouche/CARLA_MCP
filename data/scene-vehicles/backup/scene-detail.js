import * as THREE from 'three';
import {sceneMaterial} from './scene-materials.js';
import {roadArea,overlapsArea} from './scene-area.js';
export function release(group){const geometries=new Set(),materials=new Set(),textures=new Set();group.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of o.material?(Array.isArray(o.material)?o.material:[o.material]):[])materials.add(m)});for(const m of materials){for(const t of Object.values(m))if(t?.isTexture)textures.add(t);m.dispose()}for(const g of geometries)g.dispose();for(const t of textures){t.dispose();t.image?.close?.()}group.clear()}
export function areaPlanes(area){return area?[new THREE.Plane(new THREE.Vector3(1,0,0),-area[0]),new THREE.Plane(new THREE.Vector3(-1,0,0),area[2]),new THREE.Plane(new THREE.Vector3(0,0,1),-area[1]),new THREE.Plane(new THREE.Vector3(0,0,-1),area[3])]:[];}
export async function fetchLayer(url,signal,onProgress,textureCache=new Map(),area=null){
 const response=await fetch(url,{signal});if(!response.ok)throw Error('Scene layer download failed ('+response.status+')');
 const bytes=await response.arrayBuffer();if(bytes.byteLength>96*1024*1024)throw Error('Scene layer exceeds transfer budget');
 const decoded=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
 if(decoded.byteLength>256*1024*1024)throw Error('Scene layer exceeds memory budget');
 const length=new DataView(decoded).getUint32(0,true),meta=JSON.parse(new TextDecoder().decode(new Uint8Array(decoded,4,length))),base=4+length+(4-length%4)%4;
 const attribute=(r,type=Float32Array)=>new type(decoded,base+r[0],r[1]);
 const group=new THREE.Group(),geometries=new Map(),materials=new Map(),clippingPlanes=areaPlanes(area);group.name=meta.category;
 try{
 const usedMeshes=new Set(meta.groups.map(g=>g.mesh));for(const [key,m] of Object.entries(meta.meshes).filter(([key])=>usedMeshes.has(key)))geometries.set(key,m.sections.map(s=>{const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(attribute(s.position),3));g.setAttribute('normal',new THREE.BufferAttribute(attribute(s.normal),3));g.setAttribute('uv',new THREE.BufferAttribute(attribute(s.uv),2));g.setIndex(new THREE.BufferAttribute(attribute(s.index,Uint32Array),1));g.computeBoundingSphere();return {geometry:g,slot:s.slot}}));
 let count=0,instances=0,triangles=0;const usedGeometries=new Set(),matrix=new THREE.Matrix4(),object=new THREE.Object3D(),worldBounds=new THREE.Box3();
 for(const batch of meta.groups){
  if(signal.aborted)throw new DOMException('Aborted','AbortError');
  const transforms=attribute(batch.transforms),tiles=new Map();
  const sections=geometries.get(batch.mesh),localBounds=new THREE.Box3();
  for(const {geometry} of sections){if(!geometry.boundingBox)geometry.computeBoundingBox();localBounds.union(geometry.boundingBox)}
  for(let i=0;i<batch.count;i++){
   const t=transforms.subarray(i*10,i*10+10);
   // Test transformed mesh bounds, not its pivot: baked splines and offset meshes
   // can have their origin hundreds of metres away from their visible geometry.
   if(area&&meta.category!=='roads'){
    object.position.fromArray(t);object.quaternion.fromArray(t,3);object.scale.fromArray(t,7);object.updateMatrix();matrix.copy(object.matrix);
    worldBounds.copy(localBounds).applyMatrix4(matrix);
    if(!overlapsArea(area,worldBounds.min.x,worldBounds.min.z,worldBounds.max.x,worldBounds.max.z))continue;
   }
   const key=Math.floor(t[0]/100)+','+Math.floor(t[2]/100);if(!tiles.has(key))tiles.set(key,[]);tiles.get(key).push(t);instances++;
  }
  if(!tiles.size)continue;
  for(const {geometry,slot} of geometries.get(batch.mesh)){
   usedGeometries.add(geometry);
   const materialKey=batch.materials[slot]||meta.category;
   if(!materials.has(materialKey)){
    const info=meta.materials[materialKey];let texture=null;
    if(info?.web_texture&&!/lanemarking/i.test(info.name)){const path=new URL('textures/'+info.web_texture,new URL(url,location.href)).href;
     if(!textureCache.has(path)){const response=await fetch(path,{signal});if(!response.ok)throw Error('Scene texture missing');const bitmap=await createImageBitmap(await response.blob());const t=new THREE.Texture(bitmap);t.colorSpace=THREE.SRGBColorSpace;t.wrapS=t.wrapT=THREE.RepeatWrapping;t.flipY=false;t.anisotropy=4;t.needsUpdate=true;textureCache.set(path,t);}
     texture=textureCache.get(path);
    }
    materials.set(materialKey,sceneMaterial(info,meta.category,texture,clippingPlanes));
   }
   for(const tile of tiles.values()){
    triangles+=geometry.index.count/3*tile.length;
    const inst=new THREE.InstancedMesh(geometry,materials.get(materialKey),tile.length),o=new THREE.Object3D();
    tile.forEach((t,i)=>{o.position.fromArray(t);o.quaternion.fromArray(t,3);o.scale.fromArray(t,7);o.updateMatrix();inst.setMatrixAt(i,o.matrix)});inst.computeBoundingSphere();inst.userData.sceneLayer=meta.category;if(/lanemarking/i.test(meta.materials[materialKey]?.name||''))inst.renderOrder=2;group.add(inst);
   }
  }
  if(++count%30===0){onProgress?.();await new Promise(r=>setTimeout(r,0));}
 }
 for(const sections of geometries.values())for(const {geometry} of sections)if(!usedGeometries.has(geometry))geometry.dispose();
 group.userData={instances,triangles,category:meta.category};return group;
 }catch(e){release(group);for(const sections of geometries.values())for(const s of sections)s.geometry.dispose();for(const m of materials.values())m.dispose();throw e}
}
export class SceneDetail{
 constructor(view,status){this.view=view;this.status=status;this.group=new THREE.Group();view.scene.add(this.group);this.layers=new Map();this.enabled=true;this.hidden=new Set();this.serial=0;this.scope='road';}
 async load(map,force=false){
  const mapName=map.name.split('/').pop();this.map=map;
  if(!force&&this.mapName===mapName&&(this.loading||this.layers.size)){this.view.fallback.visible=!this.enabled||!this.layers.has('roads');return}
  this.mapName=mapName;if(!this.enabled){this.status('Lightweight map · select Detailed geometry to load scene objects');return}this.loading=true;this.view.node.dataset.sceneLoading='true';
  const serial=++this.serial;const textureCache=new Map();this.abort?.abort();this.abort=new AbortController();const signal=this.abort.signal,area=this.scope==='road'?roadArea(map):null;release(this.group);this.layers.clear();this.view.fallback.visible=true;this.group.visible=this.enabled;this.status('Loading actual scene geometry…');
  const name=map.name.split('/').pop(),base='/scenes/'+encodeURIComponent(name)+'/';
  try{
   const response=await fetch(base+'manifest.json',{signal,cache:'no-cache'});if(serial!==this.serial)return;if(response.status===404){this.loading=false;this.view.node.dataset.sceneLoading='false';this.status('Lightweight map · detailed geometry is not exported for this map yet');return}if(!response.ok)throw Error('Scene manifest unavailable');
   const manifest=await response.json();if(serial!==this.serial)return;if(manifest.map.split('/').pop()!==name)throw Error('Scene geometry belongs to another map');
   this.manifest=manifest;this.view.node.dataset.sceneLoading='true';let completed=0;
   for(const layer of manifest.layers){
    if(serial!==this.serial)return;
    this.status(`Loading ${layer.category} · ${completed}/${manifest.layers.length} layers`);
    const group=await fetchLayer(base+layer.file,signal,undefined,textureCache,area);
    if(serial!==this.serial){release(group);return}
    group.visible=!this.hidden.has(layer.category);this.layers.set(layer.category,group);this.group.add(group);completed++;
    if(layer.category==='roads')this.view.fallback.visible=!this.enabled;
    this.view.render();
   }
   const totals=[...this.layers.values()].reduce((n,g)=>({instances:n.instances+g.userData.instances,triangles:n.triangles+g.userData.triangles}),{instances:0,triangles:0});
   this.loading=false;this.view.node.dataset.sceneLoading='false';this.view.node.dataset.sceneScope=this.scope;this.view.node.dataset.sceneInstances=String(totals.instances);this.view.node.dataset.sceneTriangles=String(totals.triangles);
   this.status(`${this.scope==='road'?'Road network area':'Full environment'} · ${totals.instances.toLocaleString()} mesh instances · ${(totals.triangles/1e6).toFixed(1)}M triangles`);this.view.render();
  }catch(e){if(serial===this.serial)this.loading=false;if(e.name!=='AbortError'&&serial===this.serial){this.view.node.dataset.sceneLoading='false';release(this.group);this.layers.clear();this.view.fallback.visible=true;for(const t of textureCache.values()){t.dispose();t.image?.close?.()}this.status('Lightweight fallback · scene detail could not load: '+e.message);this.view.render()}}
 }
 setScope(scope){const next=scope==='full'?'full':'road';if(next===this.scope)return;this.scope=next;this.view.node.dataset.sceneScope=next;if(this.map)this.load(this.map,true)}
 setEnabled(enabled){this.enabled=enabled;this.group.visible=enabled;
  if(!enabled){++this.serial;this.abort?.abort();this.loading=false;release(this.group);this.layers.clear();this.view.node.dataset.sceneLoading='false';delete this.view.node.dataset.sceneInstances;delete this.view.node.dataset.sceneTriangles;this.status('Lightweight map · detailed geometry unloaded');this.view.fallback.visible=true;}
  else if(this.map)this.load(this.map);
  this.view.render()
 }
 setLayer(name,visible){if(visible)this.hidden.delete(name);else this.hidden.add(name);if(this.layers.has(name))this.layers.get(name).visible=visible;this.view.render()}
}
