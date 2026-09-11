import json,math,collections,httpx
from pathlib import Path
root=Path(__file__).resolve().parent;c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=20)
s=c.get('/api/status').json();cfg=c.get('/api/configuration').json();m=c.get('/api/map').json();before=json.loads((root/'configuration.json').read_text());original=json.loads((root/'before-configuration.json').read_text())
targets={'BP_Carlacola_Parked_C_7','BP_Carlacola_Parked_C_9','BP_EuropeanHGV_Parked_C_8'}
assert s['phase']=='connected' and not s['running'] and not s['error'];assert s['recovery_operation']['stage']=='ready'
assert len(cfg['actors'])==28 and len(s['sensors'])==6
assert targets <= {r['key'] for r in s['scene_vehicles']['removed']};assert len(s['scene_vehicles']['removed'])==13;assert s['scene_vehicles']['total']==35
assert not any(a.get('scene_source') in targets for a in cfg['actors'])
assert cfg['weather']==before['weather']==original['weather']
assert collections.Counter((a['model'],a['role'],a.get('scene_source')) for a in cfg['actors'])==collections.Counter((a['model'],a['role'],a.get('scene_source')) for a in before['actors'])
ego=next(a for a in cfg['actors'] if a['role']=='ego');old_ego=next(a for a in before['actors'] if a['role']=='ego');assert ego['sensors']==old_ego['sensors']
def identity(a):return (a.get('scene_source'),a['role'],a['model'])
prior={identity(a):a for a in before['actors']}
for a in cfg['actors']:
 old=prior[identity(a)];assert bool(a.get('destination'))==bool(old.get('destination'))
 if old.get('destination'):
  for k in ['x','y','z']:
   if k in old['destination']:assert abs(a['destination'][k]-old['destination'][k])<.01
points=[p for l in m['lanes'] for p in l['points']];distances=[(a['id'],min(math.hypot(a['pose']['x']-p[0],a['pose']['y']-p[1]) for p in points)) for a in s['actors'] if a['type'].startswith('vehicle.')];assert all(d<10 for _,d in distances)
assert len(m['parking_spaces'])==53 and len(m['parking_excluded'])==127
report=dict(verified=True,actors=28,scenery_vehicles=35,deleted_sources=13,offroad_sources_absent=sorted(targets),ego_sensors=6,weather_preserved=True,destinations_preserved_within_1cm=True,ego_sensor_configuration_preserved=True,retained_actor_models_roles_sources_preserved=True,maximum_vehicle_road_distance_m=max(d for _,d in distances),gpu_workers=s['worker_count'],paused=True,parking_positions=180,frame=s['frame'])
(root/'live-verification.json').write_text(json.dumps(report,indent=2));(root/'final-status.json').write_text(json.dumps(s,indent=2));(root/'final-configuration.json').write_text(json.dumps(cfg,indent=2));print(json.dumps(report,indent=2))
