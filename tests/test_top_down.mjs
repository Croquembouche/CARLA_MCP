import assert from 'node:assert/strict';
import * as THREE from 'three';
import {SceneView} from '../static/scene3d.js';
const view=Object.create(SceneView.prototype);
view.map={bounds:[-180,-90,120,210]};view.node={dataset:{}};
view.camera=new THREE.PerspectiveCamera(50,1.6,.1,20000);
view.camera.position.set(40,220,280);
view.controls={target:new THREE.Vector3(-30,0,60),mouseButtons:{LEFT:THREE.MOUSE.ROTATE},touches:{ONE:THREE.TOUCH.ROTATE},update(){view.camera.lookAt(this.target);view.camera.updateMatrixWorld()}};
view.render=()=>{};
const original=view.camera.position.clone(),target=view.controls.target.clone();
for(const aspect of [1.6,.55]){
 view.camera.aspect=aspect;view.camera.updateProjectionMatrix();view.setTopDown(true);
 assert(view.topDown&&!view.controls.enableRotate);
 assert.equal(view.controls.mouseButtons.LEFT,THREE.MOUSE.PAN);
 const direction=view.camera.getWorldDirection(new THREE.Vector3());assert(direction.y<-.999999);
 for(const x of [-180,120])for(const z of [-90,210]){const projected=new THREE.Vector3(x,0,z).project(view.camera);assert(Math.abs(projected.x)<.9&&Math.abs(projected.y)<.9,'entire map fits with margin in wide and narrow viewports')}
 view.camera.position.multiplyScalar(1.2);view.fit();assert.equal(view.node.dataset.cameraMode,'top-down');
 view.setTopDown(false);assert(view.camera.position.distanceTo(original)<1e-8);assert(view.controls.target.distanceTo(target)<1e-8);assert(view.controls.enableRotate);
}
console.log('PASS: overhead orientation, map fit at wide/narrow aspects, pan mode, fit-mode preservation, original orbit pose restoration');
