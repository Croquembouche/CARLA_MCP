"""Propose additional individual curb spaces without changing existing placements. Run from the control-center directory; requires the saved mesh survey and Shapely."""
import json,sys,math
sys.path.insert(0,'.')
from shapely import from_wkb
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
from shapely.prepared import prep
from parking import corners
p=json.load(open('data/parking/Town10HD_Opt.json'));usable=from_wkb(open('data/parking-redraw/usable.wkb','rb').read()).buffer(.005)
usable=prep(usable)
existing=p['validated_spaces'];polys=[Polygon(b['polygon']).buffer(.15) for b in existing];strips=p['curb_strips'];samples=json.load(open('data/parking-redraw/samples.json'));new=[]
for strip in strips:
 shape=Polygon(strip['polygon']).buffer(.025);row=[s for s in samples if s['lane']==strip['lane'] and shape.covers(Point(s['x'],s['y']))]
 for length in [6.,5.5,5.]:
  for s in row:
   if s['width']<1.8:continue
   for inset in [0,.1,.2]:
    width=s['width']-inset
    if width<1.8:continue
    polygon=corners(s['x'],s['y'],length,width,s['yaw']);q=Polygon(polygon)
    if not shape.covers(q) or not usable.covers(q) or any(q.intersects(o) for o in polys):continue
    b={k:s[k] for k in ['x','y','z','yaw','lane']};b.update(id=f'R{121+len(new):03d}',length=length,width=width,polygon=polygon,curb_strip=strip['id'],source='surveyed_curb_position',estimated=True,boundary_note='Additional individual planning position, not a painted stall; full footprint fits surveyed pavement and curb area')
    new.append(b);polys.append(q.buffer(.15));break
print('new',len(new));print([(b['id'],b['curb_strip'],b['length']) for b in new]);open('data/parking-clarity/additional-positions.json','w').write(json.dumps(new,indent=2))
