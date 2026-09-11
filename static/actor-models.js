import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {clone} from 'three/addons/utils/SkeletonUtils.js';
export const isMobileActor=a=>a.type?.startsWith('vehicle.')||a.type?.startsWith('walker.pedestrian.');
export function applyActorPose(object,pose){
 object.position.set(pose.x,pose.z,pose.y);
 const radians=Math.PI/180;object.rotation.set(-(pose.roll||0)*radians,-(pose.yaw||0)*radians,(pose.pitch||0)*radians,'YZX');
}
export function focusPose(actor,camera,target){
 const center=new THREE.Vector3(actor.pose.x,actor.pose.z+(actor.type.startsWith('vehicle.')?(actor.extent?.z||.8):0),actor.pose.y);
 const direction=camera.clone().sub(target).normalize();if(direction.lengthSq()<.1)direction.set(1,1,1).normalize();
 const distance=Math.max(8,(actor.extent?.x||.4)*7,(actor.extent?.z||.8)*7);
 return {target:center,position:center.clone().addScaledVector(direction,distance)};
}
export class ActorModels{
 constructor(view){this.view=view;this.entries=new Map();this.cache=new Map();this.meshCache=new Map();this.loader=new GLTFLoader();this.group=new THREE.Group();view.scene.add(this.group);
  this.pin=new THREE.Mesh(new THREE.ConeGeometry(.5,1.5,12),new THREE.MeshBasicMaterial({color:0x9ff4d2,depthTest:false}));this.pin.rotation.z=Math.PI;this.pin.renderOrder=8;this.pin.visible=false;view.scene.add(this.pin);
 }
 async template(type){
  if(!this.manifest)this.manifest=fetch('/actors/manifest.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('Actor catalog unavailable');return r.json()});
  if(!this.cache.has(type))this.cache.set(type,(async()=>{
   const info=(await this.manifest).models[type];if(!info?.parts?.length)throw Error('Model not exported: '+type);
   const root=new THREE.Group();
   for(const part of info.parts){
    if(!this.meshCache.has(part.file))this.meshCache.set(part.file,this.loader.loadAsync('/actors/'+encodeURIComponent(part.file)+'?v=3').then(g=>g.scene));
    const mesh=clone(await this.meshCache.get(part.file)),pivot=new THREE.Group();pivot.position.fromArray(part.position);pivot.quaternion.fromArray(part.quaternion);pivot.scale.fromArray(part.scale);pivot.add(mesh);root.add(pivot);
   }
   root.updateMatrixWorld(true);if(!root.getObjectByProperty('isMesh',true))throw Error('Export contains no mesh: '+type);return root;
  })());
  return this.cache.get(type);
 }

 update(actors,selected){
  const current=new Map(actors.filter(isMobileActor).map(a=>[a.id,a]));this.selected=selected;
  for(const [id,entry] of this.entries)if(!current.has(id)||current.get(id).type!==entry.actor.type){entry.root.traverse(o=>{if(o.isSkinnedMesh)o.skeleton.dispose()});this.group.remove(entry.root);this.entries.delete(id)}
  for(const [id,actor] of current){
   let entry=this.entries.get(id);
   if(!entry){
    const root=new THREE.Group();root.userData.actorId=id;entry={root,actor,loaded:false};this.entries.set(id,entry);this.group.add(root);
    this.template(actor.type).then(template=>{
     if(this.entries.get(id)!==entry)return;
     const model=clone(template);model.updateMatrixWorld(true);model.traverse(o=>{if(o.isSkinnedMesh)o.skeleton.update()});entry.bounds=new THREE.Box3().setFromObject(model);entry.height=entry.bounds.max.y;model.traverse(o=>{o.userData.actorId=id});root.add(model);entry.loaded=true;
     this.updatePin();this.report();this.view.render();
    }).catch(error=>{if(this.entries.get(id)!==entry)return;entry.error=error.message;this.report()});
   }
   entry.actor=actor;applyActorPose(entry.root,actor.pose);
  }
  this.updatePin();this.report();
 }
 updatePin(){
  const entry=this.entries.get(Number(this.selected));this.pin.visible=!!entry;
  if(entry){const a=entry.actor,top=a.pose.z+Math.max(entry.height||0,(a.extent?.z||1)*(a.type.startsWith('walker.')?1:2));const distance=this.view.camera.position.distanceTo(new THREE.Vector3(a.pose.x,top,a.pose.y));const scale=Math.max(.08,20*2*distance*Math.tan(this.view.camera.fov*Math.PI/360)/(this.view.node.clientHeight||500)/1.5);this.pin.scale.setScalar(scale);this.pin.position.set(a.pose.x,top+.25+.75*scale,a.pose.y)}
  this.view.node.dataset.actorCones=entry?'1':'0';this.view.node.dataset.selectedActor=entry?String(entry.actor.id):'';
 }
 report(){
  const entries=[...this.entries.values()];this.view.node.dataset.actorModels=String(entries.filter(e=>e.loaded).length);this.view.node.dataset.actorModelErrors=String(entries.filter(e=>e.error).length);
  const status=document.getElementById('actor-model-status');if(status)status.textContent=entries.some(e=>e.error)?'Actor model unavailable · '+entries.filter(e=>e.error).map(e=>e.actor.type).join(', '):entries.some(e=>!e.loaded)?'Loading actor models…':`${entries.length} actor models loaded`;
 }
 pick(event){
  const rect=this.view.renderer.domElement.getBoundingClientRect(),ray=new THREE.Raycaster();
  ray.setFromCamera(new THREE.Vector2((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1),this.view.camera);
  this.group.updateMatrixWorld(true);
  let closest=null,best=Infinity;
  // Intersect each actor's oriented model bounds rather than thousands of skin triangles.
  for(const entry of this.entries.values()){
   if(!entry.bounds)continue;
   const localRay=ray.ray.clone().applyMatrix4(entry.root.matrixWorld.clone().invert()),point=new THREE.Vector3();
   if(localRay.intersectBox(entry.bounds,point)){
    point.applyMatrix4(entry.root.matrixWorld);const distance=point.distanceTo(ray.ray.origin);
    if(distance<best){best=distance;closest=entry.actor}
   }
  }
  if(closest)return closest;
  // Small actors remain clickable from the map overview, within a 12px radius.
  let nearest=null,distance=12;
  for(const entry of this.entries.values()){
   const p=new THREE.Vector3(entry.actor.pose.x,entry.actor.pose.z+(entry.height||1)/2,entry.actor.pose.y).project(this.view.camera);
   if(p.z<-1||p.z>1)continue;
   const d=Math.hypot((p.x+1)*rect.width/2-(event.clientX-rect.left),(1-p.y)*rect.height/2-(event.clientY-rect.top));
   if(d<distance){distance=d;nearest=entry.actor}
  }
  return nearest;
 }
 focus(id){
  const entry=this.entries.get(Number(id));if(!entry)return;
  const pose=focusPose(entry.actor,this.view.camera.position,this.view.controls.target);
  this.view.controls.target.copy(pose.target);this.view.camera.position.copy(pose.position);this.view.controls.update();this.view.node.dataset.focusedActor=String(id);this.view.render();
 }
}
