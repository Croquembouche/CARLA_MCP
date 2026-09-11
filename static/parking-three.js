import * as THREE from 'three';
import {parkingPositions,parkingStyle} from './parking-display.js?v=open-parking-1';
// Batch vector ground markings by color: no per-space textures or draw calls.
export function buildParkingOverlay(map,occupied={},selected=null){
 const group=new THREE.Group(),fills=new Map(),lines=new Map();
 const bucket=(collection,color)=>{if(!collection.has(color))collection.set(color,[]);return collection.get(color)};
 const outline=(p,color,height)=>{const vertices=bucket(lines,color);for(let i=0;i<p.polygon.length;i++){const a=p.polygon[i],b=p.polygon[(i+1)%p.polygon.length];vertices.push(a[0],height,a[1],b[0],height,b[1])}};
 for(const bay of parkingPositions(map)){
  const style=parkingStyle(bay,!!occupied[bay.id]),height=(bay.z||0)+.7;
  const vertices=bucket(fills,style.color),points=bay.polygon.map(v=>new THREE.Vector2(...v));for(const face of THREE.ShapeUtils.triangulateShape(points,[]))for(const i of face)vertices.push(points[i].x,height,points[i].y);
  outline(bay,style.color,height+.04);
  const pts=[[-.42,.8],[-.42,-.8],[.3,-.8],[.5,-.6],[.5,-.1],[.3,.1],[-.42,.1]],glyph=bucket(lines,'#ffffff');
  for(let i=1;i<pts.length;i++)for(const p of [pts[i-1],pts[i]])glyph.push(bay.x+p[0],height+.1,bay.y+p[1]);
  if(bay.id===selected)outline(bay,'#ffffff',height+.15);
 }
 for(const [color,vertices] of fills){const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({color,transparent:true,opacity:.68,depthTest:false,depthWrite:false,side:THREE.DoubleSide}));mesh.renderOrder=70;group.add(mesh)}
 for(const [color,vertices] of lines){const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));const line=new THREE.LineSegments(geometry,new THREE.LineBasicMaterial({color,depthTest:false,depthWrite:false}));line.renderOrder=80;group.add(line)}
 group.userData={bands:0,positions:parkingPositions(map).length};return group;
}
