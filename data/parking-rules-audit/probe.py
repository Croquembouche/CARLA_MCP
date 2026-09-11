import json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from parking import overlaps,corners
s=json.load(open('data/scene-source/scene.json'));m=json.load(open('data/map-cache.json'));bays=json.load(open('data/parking/Town10HD_Opt.json'))['validated_spaces']
def pointseg(p,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy or 1)))
 return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
def dist(p,poly):return min(pointseg(p,a,b) for a,b in zip(poly,poly[1:]+poly[:1]))
def pdist(a,b):
 if overlaps(a,b):return 0
 return min(min(dist(p,b) for p in a),min(dist(p,a) for p in b))
for bay in bays:
 reasons=[]
 for i,c in enumerate(m['crosswalks']):
  d=pdist(bay['polygon'],[p[:2] for p in c['points']])
  if d<6.096:reasons.append(f'crosswalk {i}: {d:.2f}m')
 for g in s['groups'].values():
  if 'FireHdrant' not in g['mesh'] and 'SM_BusStop' not in g['mesh']:continue
  for t in g['transforms']:
   d=dist([t[0],t[2]],bay['polygon'])
   limit=4.572 if 'Hdrant' in g['mesh'] else 6
   if d<limit:reasons.append(f"{g['mesh'].split('/')[-1].split('.')[0]} {t[0]:.1f},{t[2]:.1f}: {d:.2f}m")
 if reasons:print(bay['id'], '; '.join(sorted(set(reasons))))
