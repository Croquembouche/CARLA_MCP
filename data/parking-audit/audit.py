import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import bootstrap,carla,json,math,xml.etree.ElementTree as ET,numpy as np
import parking
root=Path('data/parking-audit');xml=Path('data/map-cache.xodr').read_text();m=carla.Map('Town10HD_Opt',xml);quads=[]
for road in ET.fromstring(xml).findall('road'):
 sections=road.findall('./lanes/laneSection')
 for i,section in enumerate(sections):
  start=float(section.get('s'));end=float(sections[i+1].get('s')) if i+1<len(sections) else float(road.get('length'))
  for lane in section.findall('./*/lane'):
   if lane.get('type') not in ('shoulder','parking'):continue
   points=[]
   for s in np.linspace(start+.001,end-.001,max(2,math.ceil((end-start)/.25)+1)):
    w=m.get_waypoint_xodr(int(road.get('id')),int(lane.get('id')),float(s))
    if not w or w.lane_width<1.8 or w.is_junction:points.append(None);continue
    p=w.transform.location;a=math.radians(w.transform.rotation.yaw);n=np.array([-math.sin(a),math.cos(a)])*w.lane_width/2;c=np.array([p.x,p.y]);points.append((c-n,c+n))
   for a,b in zip(points,points[1:]):
    if a is not None and b is not None:quads.append([a[0].tolist(),a[1].tolist(),b[1].tolist(),b[0].tolist()])
Q=np.array(quads);LO=Q.min(axis=1);HI=Q.max(axis=1)
def inside(p):
 polys=Q[((LO-1e-4<=p)&(HI+1e-4>=p)).all(axis=1)];edge=np.roll(polys,-1,axis=1)-polys;rel=np.array(p)-polys;cross=edge[:,:,0]*rel[:,:,1]-edge[:,:,1]*rel[:,:,0];return bool(((cross>=-1e-4).all(axis=1)|(cross<=1e-4).all(axis=1)).any())
def validate(b):
 a=math.radians(b['yaw']);return [[b['x']+u*b['length']*math.cos(a)-v*b['width']*math.sin(a),b['y']+u*b['length']*math.sin(a)+v*b['width']*math.cos(a)] for u in np.linspace(-.495,.495,21) for v in np.linspace(-.495,.495,7)]
bays=parking.build_parking(m,xml,root/'before-annotations.json')['parking_spaces'];report=[]
for b in bays:
 pts=validate(b);bad=[p for p in pts if not inside(p)];report.append({'id':b['id'],'outside':len(bad),'samples':len(pts),'fraction':round(len(bad)/len(pts),3),'outside_points':bad})
(root/'road-strips.json').write_text(json.dumps(quads));(root/'before-bays.json').write_text(json.dumps(bays,indent=2));(root/'footprint-audit.json').write_text(json.dumps(report,indent=2));print([{k:v for k,v in r.items() if k!='outside_points'} for r in report if r['outside']])
