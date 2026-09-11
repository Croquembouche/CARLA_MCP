import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

// Sensor-local forward (+X) becomes -Z below. Look forward from behind the
// vehicle (+Z), elevated above it, so the default view follows its heading.
const DEFAULT_VIEW_POSITION=[0,90,100];

// One bounded scan, rendered only on a new sample, resize or interaction.
export class LidarView {
 constructor(host,saved){
  this.host=host;this.scene=new THREE.Scene();this.scene.background=new THREE.Color('#0a131b');
  this.camera=new THREE.PerspectiveCamera(50,1,.1,6000);
  this.renderer=new THREE.WebGLRenderer({antialias:false,powerPreference:'low-power'});
  this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
  const canvas=this.renderer.domElement;canvas.tabIndex=0;canvas.setAttribute('aria-label','LiDAR point cloud. Drag to rotate, scroll or use plus and minus to zoom. Panning disabled.');host.appendChild(canvas);
  this.controls=new OrbitControls(this.camera,canvas);this.controls.enablePan=false;this.controls.enableDamping=false;this.controls.minDistance=2;this.controls.maxDistance=2000;this.controls.zoomSpeed=.8;
  this.controls.mouseButtons.RIGHT=null;this.controls.touches.TWO=THREE.TOUCH.DOLLY_ROTATE;
  this.grid=new THREE.GridHelper(160,8,0x476479,0x233746);this.scene.add(this.grid);
  this.axes=new THREE.AxesHelper(5);this.scene.add(this.axes);
  this.geometry=new THREE.BufferGeometry();this.material=new THREE.PointsMaterial({size:2,sizeAttenuation:false,vertexColors:true});this.points=new THREE.Points(this.geometry,this.material);this.points.frustumCulled=false;this.scene.add(this.points);
  this.change=()=>this.render();this.controls.addEventListener('change',this.change);
  canvas.addEventListener('contextmenu',e=>e.preventDefault());
  canvas.addEventListener('keydown',e=>{if(['+','=','-','_','Home'].includes(e.key)){e.preventDefault();e.key==='Home'?this.reset():this.zoom(['+','='].includes(e.key)?.8:1.25)}});
  this.resize=new ResizeObserver(()=>this.render());this.resize.observe(host);
  this.camera.position.fromArray(saved?.position||DEFAULT_VIEW_POSITION);this.camera.lookAt(0,0,0);this.controls.update();
 }
 setData(buffer,scale){
  if(buffer.byteLength%9||!Number.isFinite(scale)||scale<=0)throw Error('Invalid LiDAR point preview');
  const n=buffer.byteLength/9,view=new DataView(buffer),positions=new Float32Array(n*3),colours=new Float32Array(n*3);
  for(let i=0;i<n;i++){const p=i*9,j=i*3;positions[j]=view.getInt16(p+2,true)*scale;positions[j+1]=view.getInt16(p+4,true)*scale;positions[j+2]=-view.getInt16(p,true)*scale;for(let c=0;c<3;c++)colours[j+c]=view.getUint8(p+6+c)/255}
  this.geometry.dispose();this.geometry=new THREE.BufferGeometry();this.geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));this.geometry.setAttribute('color',new THREE.BufferAttribute(colours,3));this.points.geometry=this.geometry;this.render();
 }
 render(){const w=this.host.clientWidth,h=this.host.clientHeight;if(!w||!h)return;this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.renderer.render(this.scene,this.camera);this.host.dataset.orbit=this.camera.position.toArray().map(n=>n.toFixed(3)).join(',');this.host.dataset.target=this.controls.target.toArray().join(',')}
 zoom(factor){this.camera.position.setLength(THREE.MathUtils.clamp(this.camera.position.length()*factor,2,2000));this.controls.update();this.render()}
 reset(){this.camera.position.fromArray(DEFAULT_VIEW_POSITION);this.controls.target.set(0,0,0);this.controls.update();this.render()}
 snapshot(){return {position:this.camera.position.toArray()}}
 dispose(){this.resize.disconnect();this.controls.removeEventListener('change',this.change);this.controls.dispose();this.geometry.dispose();this.material.dispose();this.grid.geometry.dispose();for(const m of [this.grid.material,this.axes.material].flat())m.dispose();this.axes.geometry.dispose();this.renderer.dispose();this.renderer.forceContextLoss();this.renderer.domElement.remove()}
}
