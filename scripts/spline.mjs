// Mirrors SplineMeshComponent.cpp CalcSliceTransformAtSplineOffset in UE 5.5.
import {Matrix4,Vector3,Quaternion,Matrix3} from 'three';
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],norm=a=>{const l=Math.hypot(...a)||1;return a.map(x=>x/l)},lerp=(a,b,t)=>a.map((x,i)=>x+(b[i]-x)*t);
export function bendGeometry(position,normal,s){
 const p=new Float32Array(position.length),n=new Float32Array(normal.length),axis=s.axis.includes('.Y')?1:s.axis.includes('.Z')?2:0;
 const min=s.boundary[0]!==s.boundary[1]?s.boundary[0]:s.bounds[0][axis],max=s.boundary[0]!==s.boundary[1]?s.boundary[1]:s.bounds[1][axis];
 const tr=s.transform,matrix=new Matrix4().compose(new Vector3().fromArray(tr),new Quaternion().fromArray(tr,3),new Vector3().fromArray(tr,7)),nm=new Matrix3().getNormalMatrix(matrix),v=new Vector3();
 for(let i=0;i<position.length;i+=3){
  const q=[position[i]*100,position[i+2]*100,position[i+1]*100],a=(q[axis]-min)/(max-min||1),a2=a*a,a3=a2*a,h=s.smooth?Math.max(0,Math.min(1,a))**2*(3-2*Math.max(0,Math.min(1,a))):a;
  let centre=[0,1,2].map(j=>(2*a3-3*a2+1)*s.start_position[j]+(a3-2*a2+a)*s.start_tangent[j]+(-2*a3+3*a2)*s.end_position[j]+(a3-a2)*s.end_tangent[j]);
  const dir=norm([0,1,2].map(j=>(6*a2-6*a)*s.start_position[j]+(3*a2-4*a+1)*s.start_tangent[j]+(-6*a2+6*a)*s.end_position[j]+(3*a2-2*a)*s.end_tangent[j]));
  const bx=norm(cross(s.up,dir)),by=norm(cross(dir,bx)),off=lerp(s.start_offset,s.end_offset,h),roll=s.start_roll+(s.end_roll-s.start_roll)*h,cs=Math.cos(roll),sn=Math.sin(roll),x=bx.map((v,j)=>cs*v-sn*by[j]),y=by.map((v,j)=>cs*v+sn*bx[j]),scale=lerp(s.start_scale,s.end_scale,h);
  centre=centre.map((v,j)=>v+off[0]*bx[j]+off[1]*by[j]);const frame=axis===0?[dir,x,y]:axis===1?[y,dir,x]:[x,y,dir],sc=axis===0?[1,...scale]:axis===1?[scale[1],1,scale[0]]:[...scale,1];q[axis]=0;
  const r=centre.map((v,j)=>v+q.reduce((sum,c,k)=>sum+c*sc[k]*frame[k][j],0));v.set(r[0]/100,r[2]/100,r[1]/100).applyMatrix4(matrix).toArray(p,i);
  const nn=[normal[i],normal[i+2],normal[i+1]],nr=[0,1,2].map(j=>nn.reduce((sum,c,k)=>sum+c/(sc[k]||1)*frame[k][j],0));v.set(nr[0],nr[2],nr[1]).applyMatrix3(nm).normalize().toArray(n,i);
 }
 return [p,n];
}
