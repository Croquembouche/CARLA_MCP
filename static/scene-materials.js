import * as THREE from 'three';
export function roadPaint(info){return /lanemarking/i.test(info?.name||'')}
export function sceneMaterial(info,category,texture,clippingPlanes=[]){
 const name=info?.name||'',paint=roadPaint(info),masked=info?.blend?.includes('MASKED'),glass=/glass/i.test(name)&&!paint,translucent=info?.blend?.includes('TRANSLUCENT');
 let color=new THREE.Color(0xa4b0b5);
 if(paint)color.set(/yellow/i.test(name)?0xe8bd43:0xeee9dc);
 else if(texture)color.set(0xffffff);
 else{
  const tint=Object.entries(info?.vectors||{}).find(([k,v])=>/^(base.?color|diffuse.?color|color|tint)$/i.test(k)&&v.slice(0,3).some(x=>x>0));
  if(tint)color.setRGB(...tint[1].slice(0,3));
  else color.set(glass?0x496a7b:/leaf|leaves|grass|foliage/i.test(name)?0x4e793c:/bark|wood|trunk/i.test(name)?0x7c6753:/asphalt|road/i.test(name)?0x5b6265:/brick/i.test(name)?0xa57f6b:({roads:0x777b7c,buildings:0xa8b3b7,vegetation:0x477d45,street:0x7e8990,props:0x9b8f7d,water:0x3b778d}[category]||0xa4b0b5));
 }
 const options={color,map:paint?null:texture,clippingPlanes,side:THREE.DoubleSide,depthTest:true,depthWrite:!translucent,transparent:!!translucent,opacity:translucent?(glass?.4:.75):1,alphaTest:texture&&(masked||info?.browser_alpha)?.4:0,polygonOffset:paint,polygonOffsetFactor:paint?-2:0,polygonOffsetUnits:paint?-2:0};
 return paint?new THREE.MeshBasicMaterial(options):new THREE.MeshLambertMaterial(options);
}
