// Unreal and browser face conventions differ. Match triangle winding to the
// exported vertex normals so double-sided lighting does not shade roofs inside-out.
export function orientTriangles(position,normal,index){
 let reversed=0;
 for(let i=0;i<index.length;i+=3){
  const a=index[i]*3,b=index[i+1]*3,c=index[i+2]*3;
  const ux=position[b]-position[a],uy=position[b+1]-position[a+1],uz=position[b+2]-position[a+2];
  const vx=position[c]-position[a],vy=position[c+1]-position[a+1],vz=position[c+2]-position[a+2];
  const nx=normal[a]+normal[b]+normal[c],ny=normal[a+1]+normal[b+1]+normal[c+1],nz=normal[a+2]+normal[b+2]+normal[c+2];
  if((uy*vz-uz*vy)*nx+(uz*vx-ux*vz)*ny+(ux*vy-uy*vx)*nz<0){const t=index[i+1];index[i+1]=index[i+2];index[i+2]=t;reversed++}
 }
 return reversed;
}
