// Match authored spline components once without repeatedly scanning the world.
export function removeSplineInstances(groups,splines){
 const batches=new Map(),exact=new Map(),removed=new Map();
 const batchKey=(mesh,materials)=>mesh+'|'+JSON.stringify(materials);
 for(const g of Object.values(groups)){
  const key=batchKey(g.mesh,g.materials);if(!batches.has(key))batches.set(key,[]);batches.get(key).push(g);
  g.transforms.forEach((t,i)=>{const k=key+'|'+JSON.stringify(t);if(!exact.has(k))exact.set(k,[]);exact.get(k).push({g,i})});
 }
 for(const s of splines){
  const key=batchKey(s.mesh,s.materials),queue=exact.get(key+'|'+JSON.stringify(s.transform));let found;
  while(queue?.length&&!found){const x=queue.pop();if(!removed.get(x.g)?.has(x.i))found=x}
  if(!found)for(const g of batches.get(key)||[]){const i=g.transforms.findIndex((t,i)=>!removed.get(g)?.has(i)&&t.every((v,j)=>Math.abs(v-s.transform[j])<1e-5));if(i>=0){found={g,i};break}}
  if(!found)throw Error('Spline instance missing: '+s.mesh);
  if(!removed.has(found.g))removed.set(found.g,new Set());removed.get(found.g).add(found.i);
 }
 for(const [g,indices] of removed)g.transforms=g.transforms.filter((_,i)=>!indices.has(i));
}
