// CARLA ground coordinates are x/y; Three.js ground coordinates are x/z.
// Keep whole central blocks, with 25 metres of context outside the outer lanes.
export function roadArea(map, margin=25){
 const bounds=[Infinity,Infinity,-Infinity,-Infinity];
 for(const lane of map?.lanes||[])for(const p of lane.points||[]){
  if(!Number.isFinite(p[0])||!Number.isFinite(p[1]))continue;
  const half=Number.isFinite(p[3])?Math.max(0,p[3])/2:0;
  bounds[0]=Math.min(bounds[0],p[0]-half);bounds[1]=Math.min(bounds[1],p[1]-half);
  bounds[2]=Math.max(bounds[2],p[0]+half);bounds[3]=Math.max(bounds[3],p[1]+half);
 }
 if(!bounds.every(Number.isFinite))return null;
 return [bounds[0]-margin,bounds[1]-margin,bounds[2]+margin,bounds[3]+margin];
}
export function overlapsArea(area,minX,minY,maxX,maxY){
 return !area||maxX>=area[0]&&maxY>=area[1]&&minX<=area[2]&&minY<=area[3];
}
export function buildingInArea(building,area){
 const angle=(building.yaw||0)*Math.PI/180,c=Math.abs(Math.cos(angle)),s=Math.abs(Math.sin(angle));
 const ex=c*building.extent.x+s*building.extent.y,ey=s*building.extent.x+c*building.extent.y;
 return overlapsArea(area,building.x-ex,building.y-ey,building.x+ex,building.y+ey);
}
