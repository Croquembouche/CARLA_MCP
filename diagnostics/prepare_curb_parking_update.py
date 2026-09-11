import json,sys,math,copy
from pathlib import Path
sys.path.insert(0,'.')
from parking_rules import screen_spaces
from shapely.geometry import Polygon
from shapely import from_wkb
from shapely.prepared import prep
import bootstrap,carla
root=Path('data/parking-clarity');p=json.load(open('data/parking/Town10HD_Opt.json'));old=copy.deepcopy(p);new=json.load(open(root/'additional-positions.json'));prior_good,prior_bad=screen_spaces(p['validated_spaces'],p['traffic_rules']);reasons={b['id']:b['restriction_reasons'] for b in prior_bad}
wmap=carla.Map('Town10HD_Opt',Path('data/map-cache.xodr').read_text());landmarks={lm.id:lm for lm in wmap.get_all_landmarks() if lm.type in ('206','1000001')}.values()
for b in new:
 nearby=sorted([o for o in p['validated_spaces'] if o['lane']==b['lane']],key=lambda o:math.hypot(o['x']-b['x'],o['y']-b['y']))[:2]
 inherited={r['id']:r for o in nearby if math.hypot(o['x']-b['x'],o['y']-b['y'])<=25 for r in reasons.get(o['id'],[]) if r['kind'].startswith('posted') or r['kind']=='no_stopping'}
 for r in inherited.values():p['traffic_rules']['zones'].append(dict(id=f'curb-fill-{b["id"]}-{r["id"]}',kind=r['kind'],bay_ids=[b['id']],reason=r['reason'],evidence=r.get('evidence','')+'; conservative coverage inherited from adjacent surveyed positions on the same lane'))
 a=math.radians(b['yaw']);c,s=math.cos(a),math.sin(a)
 for lm in landmarks:
  dx,dy=lm.transform.location.x-b['x'],lm.transform.location.y-b['y'];along=dx*c+dy*s;lateral=abs(-dx*s+dy*c)
  if along>=0 and along-b['length']/2<=9.144 and lateral<=b['width']/2+2.5:p['traffic_rules']['zones'].append(dict(id=f'curb-fill-control-{lm.id}-{b["id"]}',kind='control_approach',bay_ids=[b['id']],reason='Scenario approach-control clearance',evidence=f'OpenDRIVE landmark {lm.id}; retained baseline 9.144 m'))
p['validated_spaces']+=new;p['validation']['additional_curb_positions']=dict(count=len(new),minimum_length_m=5,minimum_width_m=1.8,minimum_existing_gap_m=.15,date='2026-09-10')
good,bad=screen_spaces(p['validated_spaces'],p['traffic_rules']);usable=prep(from_wkb(Path('data/parking-redraw/usable.wkb').read_bytes()).buffer(.005));polys=[Polygon(b['polygon']) for b in p['validated_spaces']]
assert all(usable.covers(poly) for poly in polys)
assert not any(a.intersection(b).area>1e-6 for i,a in enumerate(polys) for b in polys[i+1:])
assert p['validated_spaces'][:len(old['validated_spaces'])]==old['validated_spaces']
assert [b for b in good if b['id'] not in {n['id'] for n in new}]==prior_good
assert [b for b in bad if b['id'] not in {n['id'] for n in new}]==prior_bad
report=dict(total=len(good)+len(bad),selectable=len(good),excluded=len(bad),new=[dict(id=b['id'],length=b['length']) for b in new],new_selectable=[b['id'] for b in good if b['id'] in {n['id'] for n in new}],all_on_pavement=True,no_overlaps=True,prior_positions_and_eligibility_unchanged=True)
(root/'expanded-proposal.json').write_text(json.dumps(p,indent=2)+'\n');(root/'expansion-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
