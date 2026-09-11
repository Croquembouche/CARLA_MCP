import json,math,bisect
from pathlib import Path
import numpy as np
root=Path('data/parking-audit');bays=json.loads((root/'before-bays.json').read_text());Q=np.array(json.loads((root/'road-strips.json').read_text()));LO=Q.min(axis=1);HI=Q.max(axis=1)
def fits(b):
 a=math.radians(b['yaw']);u,v=np.meshgrid(np.linspace(-.5,.5,51),np.linspace(-.5,.5,11));u=u.ravel()*b['length'];v=v.ravel()*b['width'];P=np.array([b['x']+u*math.cos(a)-v*math.sin(a),b['y']+u*math.sin(a)+v*math.cos(a)]).T
 polygons=Q[((HI>=P.min(0)-1e-4)&(LO<=P.max(0)+1e-4)).all(1)];edge=np.roll(polygons,-1,axis=1)-polygons;rel=P[:,None,None,:]-polygons;cross=edge[None,:,:,0]*rel[:,:,:,1]-edge[None,:,:,1]*rel[:,:,:,0];return bool(((cross>=-1e-4).all(2)|(cross<=1e-4).all(2)).any(1).all())
def polygon(b):
 a=math.radians(b['yaw']);return [[b['x']+u*math.cos(a)-v*math.sin(a),b['y']+u*math.sin(a)+v*math.cos(a)] for u,v in [(-b['length']/2,-b['width']/2),(b['length']/2,-b['width']/2),(b['length']/2,b['width']/2),(-b['length']/2,b['width']/2)]]
rows=[]
for b in sorted(bays,key=lambda b:b['y']):
 row=next((r for r in rows if abs(r[0]['y']-b['y'])<2),None)
 if row is None:rows.append([b])
 else:row.append(b)
chosen=[];dropped=[]
for row in rows:
 states=[(-1e9,0,[])];row.sort(key=lambda b:b['x'])
 for original in row:
  candidates=[]
  for length in sorted(set([original['length'],5.]+[float(v) for v in np.arange(5.5,original['length'],.5)]),reverse=True):
   for width in [original['width'],original['width']-.1,original['width']-.2]:
    for offset in np.arange(-4,4.01,.25):
     b=dict(original,length=length,width=width,x=original['x']+float(offset),y=original['y']+float(offset)*math.tan(math.radians(original['yaw'])));b['polygon']=polygon(b)
     if not fits(b):continue
     cost=float(offset)**2+2*(original['length']-length)**2+20*(original['width']-width)**2
     candidates.append((min(p[0] for p in b['polygon']),max(p[0] for p in b['polygon']),cost,b))
  new=[(right,cost+100,path+[None]) for right,cost,path in states];rights=[r for r,_,_ in states]
  for left,right,cost,b in candidates:
   index=bisect.bisect_right(rights,left-.15)-1
   if index>=0:
    previous=states[index];new.append((right,previous[1]+cost,previous[2]+[b]))
  states=[];best=1e99
  for state in sorted(new,key=lambda state:(state[0],state[1])):
   if state[1]<best:states.append(state);best=state[1]
  print(original['id'],len(candidates),'candidates',flush=True)
 selected=min(states,key=lambda state:state[1])[2]
 for original,b in zip(row,selected):
  if b is None:dropped.append(original);continue
  chosen.append(b)
chosen.sort(key=lambda b:b['id']);changes=[]
for b in chosen:
 old=next(a for a in bays if a['id']==b['id']);delta={k:[old[k],b[k]] for k in ['x','y','length','width'] if abs(old[k]-b[k])>1e-7}
 if delta:changes.append({'id':b['id'],'changes':delta})
assert all(fits(b) for b in chosen)
(root/'corrected-bays.json').write_text(json.dumps(chosen,indent=2));(root/'corrections.json').write_text(json.dumps({'changes':changes,'excluded':[b['id'] for b in dropped],'count':len(chosen)},indent=2));print(json.dumps({'changes':changes,'excluded':[b['id'] for b in dropped],'count':len(chosen)}))
