"""Rebuild Town10 restriction evidence from the exported scene and OpenDRIVE.

Run with control-center .venv Python from the project root. This only changes
parking annotations/audit artifacts, never the Unreal map or lane geometry.
"""
import hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bootstrap,carla
from parking import corners
from parking_rules import screen_spaces
root=ROOT/'data/parking-rules-audit';root.mkdir(exist_ok=True)
source=ROOT/'data/parking/Town10HD_Opt.json';data=json.loads(source.read_text())
if data.get('curb_strips'):
 raise SystemExit('This legacy audit would discard the curb survey review regions. Use diagnostics/redraw_parking.py and review its proposal instead.')
backup=root/'before-annotations.json'
if not backup.exists():backup.write_text(source.read_text())
scene_path=ROOT/'data/scene-source/scene.json';scene=json.loads(scene_path.read_text())
xodr=(ROOT/'data/map-cache.xodr').read_text();wmap=carla.Map('Town10HD_Opt',xodr)
source_url='https://delcode.delaware.gov/title21/c041/sc10/index.html'
rules={'profile':'Delaware baseline + authored scene restrictions (provisional)',
 'jurisdiction_confirmed':False,'review_date':'2026-09-09',
 'source_url':source_url,'opendrive_sha256':hashlib.sha256(xodr.encode()).hexdigest(),
 'scene_sha256':hashlib.sha256(scene_path.read_bytes()).hexdigest(),
 'scope':'Screened for exported hydrants, crosswalks, access ramps, bus stops, nearby approach controls and reviewed parking signs. Remaining bay bounds are estimates; unrepresented restrictions are not certified.',
 'policy':'Withhold permit-only and time-dependent parking until eligibility and a civil clock/duration policy are implemented. Bus-stop clearance is a conservative scenario reserve, not a statutory distance. Mixed-sign rows remain withheld where exact changeover boundaries are not authored.',
 'zones':[]}
zones=rules['zones'];features=[]
for g in scene['groups'].values():
 name=g['mesh'].split('/')[-1].split('.')[0]
 if not any(k in name for k in ['FireHdrant','BusStop','accessRamp','SM_Parking0','SM_NoStopping','SM_Tow01']):continue
 for index,t in enumerate(g['transforms']):
  p=[t[0],t[2]];feature={'id':f'{name}-{index}','mesh':g['mesh'],'point':p};features.append(feature)
  if 'FireHdrant' in name:
   zones.append(dict(id=feature['id'],kind='hydrant',point=p,clearance_m=4.572,reason='Within 15 ft (4.572 m) of a fire hydrant',evidence=feature['id']+'; Delaware 21 §4179(e)(4)'))
  elif 'BusStop' in name and 'Glasses' not in name:
   zones.append(dict(id=feature['id'],kind='bus_stop',point=p,clearance_m=6.,reason='Bus-stop boarding/stopping area reserved from general parking',evidence=feature['id']+'; conservative 6 m scenario reserve around authored stop; exact curb extent is not authored'))
  elif 'accessRamp' in name:
   # Ramp access footprints must remain open. Fixed 4 m reserve exceeds the
   # exported small ramp half-width and reaches the neighboring curb strip.
   zones.append(dict(id=feature['id'],kind='access',point=p,clearance_m=4.,reason='Driveway/access-ramp frontage must remain clear',evidence=feature['id']+'; conservative scenario frontage reserve'))
# Native crosswalk loop boundaries are closed by a repeated first location.
loops=[];loop=[]
for p in wmap.get_crosswalks():
 q=[p.x,p.y]
 if loop and math.dist(q,loop[0])<.01:
  if len(loop)>=3:loops.append(loop)
  loop=[]
 else:loop.append(q)
for index,poly in enumerate(loops):
 zones.append(dict(id=f'crosswalk-{index}',kind='crosswalk',polygon=poly,clearance_m=6.096,reason='Within 20 ft (6.096 m) of a crosswalk',evidence=f'CARLA/OpenDRIVE crosswalk {index}; Delaware 21 §4179(e)(6)'))
# Signs are interpreted from their exported mesh UVs in T_TrafficSignAtlas04_d:
# Parking02 = no parking 08:30-17:30; Parking04 = accessible permit reserved;
# Parking03 = 30 minute parking 08:30-17:30; Parking01 = no parking any time.
# No curb interval delimiters are authored. Do not invent a midpoint boundary.
for ids,kind,reason,evidence in [
 (range(1,8),'posted_conditional','Accessible-reserved / timed no-parking row; exact sign extents and eligibility are unresolved','SM_Parking04 at (-16.97,7.74),(3.03,7.74); SM_Parking02 at (22.01,7.74); inspected sign atlas and mesh UVs'),
 (range(27,34),'posted_mixed','30-minute / no-parking-any-time row; exact transition and duration enforcement are unresolved','SM_Parking03 at (-23.92,125.07),(-1.14,125.23); SM_Parking01 at (28.86,125.81); inspected sign atlas and mesh UVs')]:
 zones.append(dict(id=kind,kind=kind,bay_ids=[f'P{i:03}' for i in ids],reason=reason,evidence=evidence))
# A roadside control only restricts its approach, not a bay beyond the control
# or on another curb. Project onto each candidate's traffic heading.
landmarks={lm.id:lm for lm in wmap.get_all_landmarks() if lm.type in ('206','1000001')}
for bay in data['validated_spaces']:
 a=math.radians(bay['yaw']);c,s=math.cos(a),math.sin(a)
 for ident,lm in landmarks.items():
  p=lm.transform.location;dx,dy=p.x-bay['x'],p.y-bay['y'];along=dx*c+dy*s;lateral=abs(-dx*s+dy*c)
  nearest=along-bay['length']/2
  if along>=0 and nearest<=9.144 and lateral<=bay['width']/2+2.5:
   zones.append(dict(id=f'control-{ident}-{bay["id"]}',kind='control_approach',bay_ids=[bay['id']],reason='Within 30 ft (9.144 m) on approach to a roadside stop sign or signal',evidence=f'OpenDRIVE landmark {ident}; approach clearance {max(0,nearest):.3f} m; Delaware 21 §4179(e)(7)'))
allowed,excluded=screen_spaces(data['validated_spaces'],rules)
data['traffic_rules']=rules
source.write_text(json.dumps(data,indent=2)+'\n')
report={'profile':rules['profile'],'allowed_ids':[b['id'] for b in allowed],'excluded':excluded,'features':features,'rules':rules}
(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'allowed':report['allowed_ids'],'excluded':{b['id']:[r['kind'] for r in b['restriction_reasons']] for b in excluded}},indent=2))
