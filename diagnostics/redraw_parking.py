"""Reproducible Town10 curb survey from exported road, paint and curb geometry.

Writes a proposal and evidence into data/parking-redraw; does not deploy it.
Requires the control-center Python environment plus shapely 2.1.2.
"""
import sys,json,math,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,Point,LineString,mapping
from shapely.ops import unary_union
from shapely.prepared import prep
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bootstrap,carla
from parking import corners
from parking_rules import screen_spaces
out=ROOT/'data/parking-redraw';source=ROOT/'data/scene-source/scene.json';scene=json.loads(source.read_text());blob=(source.parent/'geometry.bin').read_bytes()
data=json.loads((out/'before-annotations.json').read_text());xodr=(ROOT/'data/map-cache.xodr').read_text();wmap=carla.Map('Town10HD_Opt',xodr)
# Projection of real triangles, preserving authored transforms and material slots.
def rotation(q):
 x,y,z,w=q;return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
parts={k:[] for k in ['asphalt','paint','sidewalk']}
for g in scene['groups'].values():
 if g['category']!='roads':continue
 for section in scene['meshes'][g['mesh']]['sections']:
  material=g['materials'][section['slot']].lower()
  kind='paint' if 'lanemarking' in material else 'asphalt' if 'mi_road_asphalt_b.' in material or 'mi_gutterdirty.' in material else 'sidewalk' if any(k in material for k in ['sidewalk/mi_','curb/mi_','mi_accessramp.']) else None
  if kind is None:continue
  v=np.frombuffer(blob,dtype='<f4',count=section['position'][1],offset=section['position'][0]).reshape(-1,3)
  index=np.frombuffer(blob,dtype='<u4',count=section['index'][1],offset=section['index'][0]).reshape(-1,3)
  for t in g['transforms']:
   verts=(v*np.array(t[7:]))@rotation(t[3:7]).T+np.array(t[:3]);tri=verts[index]
   tri=tri[(tri[:,:,1].max(1)<1.2)&(tri[:,:,1].min(1)>-1)]
   for p in tri[:,:,[0,2]]:
    poly=Polygon(p)
    if poly.area>1e-7:parts[kind].append(poly)
print({k:len(v) for k,v in parts.items()},flush=True)
geom={k:unary_union(v) for k,v in parts.items()};paved=geom['asphalt'].buffer(.06).buffer(-.06).difference(geom['sidewalk']);usable=paved.difference(geom['paint'].buffer(.04));usable_test=prep(usable.buffer(.005))
(out/'usable.wkb').write_bytes(usable.wkb)
# Survey-only asphalt/curb constraints do not establish parking permission.
# Only non-junction outer shoulders visible as a curb strip in the overhead
# survey are accepted; medians and shoulders that lack edge paint are rejected.
strips=[];samples=[]
for road in ET.fromstring(xodr).findall('road'):
 if road.get('junction')!='-1':continue
 sections=road.findall('./lanes/laneSection')
 for i,section in enumerate(sections):
  start=float(section.get('s'));end=float(sections[i+1].get('s')) if i+1<len(sections) else float(road.get('length'))
  for lane in section.findall('./*/lane'):
   if lane.get('type') not in ['shoulder','parking']:continue
   rid,lid=int(road.get('id')),int(lane.get('id'));row=[]
   for s in np.arange(start+.05,end-.05,.25):
    w=wmap.get_waypoint_xodr(rid,lid,float(s))
    if not w or w.is_junction or w.lane_width<1.8:continue
    p=w.transform.location;a=math.radians(w.transform.rotation.yaw);n=np.array([-math.sin(a),math.cos(a)]);center=np.array([p.x,p.y]);cross=LineString([center-n*(w.lane_width/2+.8),center+n*(w.lane_width/2+.8)])
    cut=usable.intersection(cross);segments=[cut] if cut.geom_type=='LineString' else list(cut.geoms) if cut.geom_type=='MultiLineString' else []
    candidates=[seg for seg in segments if seg.length>=1.8 and seg.distance(Point(center))<.3]
    if not candidates:continue
    seg=min(candidates,key=lambda seg:seg.distance(Point(center)));ends=np.array(seg.coords);c=ends.mean(0)
    # One edge must meet the road edge paint, and the other the actual curb.
    if geom['paint'].distance(Point(ends[0]))>.22 and geom['paint'].distance(Point(ends[-1]))>.22:continue
    if geom['sidewalk'].distance(Point(ends[0]))>.25 and geom['sidewalk'].distance(Point(ends[-1]))>.25:continue
    width=min(seg.length-.2,3.0)
    row.append(dict(x=float(c[0]),y=float(c[1]),z=p.z,yaw=w.transform.rotation.yaw,width=width,s=float(s),lane=[rid,w.section_id,lid]))
   if row:
    # Split at real gaps, access ramps, junctions and missing painted edges.
    runs=[]
    for p in row:
     if not runs or p['s']-runs[-1][-1]['s']>.4:runs.append([])
     runs[-1].append(p)
    for run in runs:
     if len(run)<8:continue
     left=[];right=[]
     for p in run:
      a=math.radians(p['yaw']);dx=-math.sin(a)*p['width']/2;dy=math.cos(a)*p['width']/2
      left.append([p['x']+dx,p['y']+dy]);right.append([p['x']-dx,p['y']-dy])
     poly=Polygon(left+right[::-1]).buffer(0).simplify(.02, preserve_topology=True)
     strips.append({'id':f'C{len(strips)+1:03d}','lane':run[0]['lane'],'polygon':list(max([poly] if poly.geom_type=='Polygon' else poly.geoms,key=lambda q:q.area).exterior.coords)[:-1],'source':'surveyed_curb_strip','samples':run})
     samples.extend(run)
print('strips',len(strips),'samples',len(samples),flush=True)
(out/'samples.json').write_text(json.dumps(samples))
# Preserve old IDs where a footprint can be fitted to measured paint/curb edges.
def fits(b):return usable_test.covers(Polygon(b['polygon']))
old=[];removed=[]
for b in data['validated_spaces']:
 nearby=sorted([s for s in samples if math.hypot(s['x']-b['x'],s['y']-b['y'])<4],key=lambda s:math.hypot(s['x']-b['x'],s['y']-b['y']))
 found=None
 for p in nearby:
  for length in [min(b['length'],7.5),6.,5.5,5.]:
   if length>b['length']+.01:continue
   for inset in [0,.1,.2,.3]:
    width=p['width']-inset
    if width<1.8:continue
    q={**b,**{k:p[k] for k in ['x','y','z','yaw','lane']},'length':length,'width':width,'source':'surveyed_curb_position','estimated':True,'boundary_note':'Paint and curb edges measured from scene mesh; along-curb divisions are planning positions, not painted stalls'}
    q['polygon']=corners(q['x'],q['y'],length,width,q['yaw'])
    if fits(q) and not any(Polygon(q['polygon']).intersects(Polygon(o['polygon']).buffer(.15)) for o in old):found=q;break
   if found:break
  if found:break
 if found:old.append(found)
 else:removed.append(b['id'])
# Add positions along the surveyed strips missed by the old meter-only inventory.
new=[]
for strip in strips:
 for p in strip['samples'][::2]:
  if p['width']<1.8:continue
  q={k:p[k] for k in ['x','y','z','yaw','width','lane']};q.update(length=6.,estimated=True,source='surveyed_curb_position',curb_strip=strip['id'],boundary_note='Paint and curb edges measured from scene mesh; 6 m planning position, not a painted individual stall')
  q['polygon']=corners(q['x'],q['y'],q['length'],q['width'],q['yaw'])
  if not fits(q):continue
  # Keep bays inside one continuous surveyed run, away from its endpoints.
  if math.hypot(p['x']-strip['samples'][0]['x'],p['y']-strip['samples'][0]['y'])<3.2 or math.hypot(p['x']-strip['samples'][-1]['x'],p['y']-strip['samples'][-1]['y'])<3.2:continue
  if any(Polygon(q['polygon']).intersects(Polygon(o['polygon']).buffer(.6)) for o in old+new):continue
  q['id']=f'R{len(new)+1:03d}';new.append(q)
allbays=old+new
# Preserve existing restriction evidence and extend posted coverage to new rows.
rules=data['traffic_rules'];rules['review_date']='2026-09-10';rules['scope']='Footprints follow surveyed curb and paint edges. Existing clearance policy retained; new roadside positions screened against authored signs, crossings, hydrants, stops and access points. Sign changeover limits remain conservative review regions.'
# Explicit spatial row reviews based on the sign inventory and overhead panels.
review_rows=[('north_outer',[-90,-78,80,-66],'posted_mixed','Northern outer curb has no-parking, permit-only and timed signs; exact changeovers unresolved'),('north_inner',[-40,-58,65,-50],'posted_conditional','Northern inner curb has timed no-parking signs; civil-time enforcement unavailable'),('middle_north',[-35,6,92,13],'posted_conditional','Central north curb has permit-only and timed no-parking signs'),('west_upper',[-122,-45,-112,8],'posted_conditional','Western outer curb has accessible-reserved signs; exact coverage unresolved'),('west_lower',[-125,45,-75,148],'no_stopping','Western/southwest curb corridor has no-stopping signs and inner tow-away frontage; exact coverage unresolved'),('east_lower',[82,73,118,146],'posted_conditional','Eastern outer curve has accessible-reserved and timed no-parking signs'),('south_inner',[-35,122,66,131],'posted_mixed','Southern inner curb has timed and no-parking signs; changeover unresolved')]
for ident,rect,kind,reason in review_rows:
 x0,y0,x1,y1=rect
 ids=[b['id'] for b in allbays if b['id'].startswith('R') and x0<=b['x']<=x1 and y0<=b['y']<=y1 and (ident!='east_lower' or b['lane'][2]<0)]
 if ids:rules['zones'].append(dict(id='survey-'+ident,kind=kind,bay_ids=ids,reason=reason,evidence='Scene sign mesh inventory and unobstructed overhead survey 2026-09-10: '+ident))
# Do not allow the observed tow-away frontage on the narrow southern cross street.
ids=[b['id'] for b in allbays if b['id'].startswith('R') and 69<b['y']<77 and -35<b['x']<92]
if ids:rules['zones'].append(dict(id='survey-tow-frontage',kind='posted_unresolved',bay_ids=ids,reason='Tow-away frontage; accompanying permission and access coverage unresolved',evidence='SM_Tow01 at (-13.52,75.27), (37.50,75.28) and overhead survey'))
# Approach control test for all new geometry; old control exclusions also retained.
for b in allbays:
 a=math.radians(b['yaw']);c,s=math.cos(a),math.sin(a)
 for lm in {lm.id:lm for lm in wmap.get_all_landmarks() if lm.type in ('206','1000001')}.values():
  dx,dy=lm.transform.location.x-b['x'],lm.transform.location.y-b['y'];along=dx*c+dy*s;lateral=abs(-dx*s+dy*c)
  if along>=0 and along-b['length']/2<=9.144 and lateral<=b['width']/2+2.5:
   rules['zones'].append(dict(id=f'survey-control-{lm.id}-{b["id"]}',kind='control_approach',bay_ids=[b['id']],reason='Scenario approach-control clearance',evidence=f'OpenDRIVE landmark {lm.id}; retained baseline 9.144 m'))
allowed,excluded=screen_spaces(allbays,rules)
for strip in strips:strip.pop('samples')
data.update(validated_spaces=allbays,curb_strips=strips)
data['validation']['mesh_seam_closing_radius_m']=.06
data['validation'].update(method='Orthographic scene survey; projected native road/paint/curb triangles constrain full footprints; OpenDRIVE supplies lane heading; no overlap',boundaries='Surveyed continuous curb strips; individual along-curb divisions remain planning estimates',geometry_sha256=hashlib.sha256(blob).hexdigest(),scene_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),survey_date='2026-09-10',removed_bays=removed)
report=dict(old_count=len(old),new_count=len(new),allowed=[b['id'] for b in allowed],excluded={b['id']:[r['kind'] for r in b['restriction_reasons']] for b in excluded},removed=removed,strips=len(strips),mesh_area_m2={k:round(v.area,2) for k,v in geom.items()},notes='Buildings and vegetation omitted from survey renderer; roads/paint/curbs retained. Projected decals are not rendered; source decal inventory reviewed separately.')
(out/'proposal.json').write_text(json.dumps(data,indent=2)+'\n');(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');(out/'survey-spaces.json').write_text(json.dumps(allbays));print(json.dumps(report),flush=True)
