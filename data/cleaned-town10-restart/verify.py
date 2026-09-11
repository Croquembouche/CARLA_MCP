import json,collections,httpx,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent;c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=30)
s=c.get('/api/status').json();assert s.get('recovery_operation',{}).get('stage')=='ready',s.get('recovery_operation');assert s['phase']=='connected' and not s.get('error') and not s['running']
cfg=c.get('/api/configuration').json();m=c.get('/api/map').json();before=json.loads((root/'configuration.json').read_text())
assert cfg['map'].split('/')[-1]=='Town10HD_Opt';assert len(cfg['actors'])==len(before['actors'])==28
identity=lambda a:(a.get('scene_source'),a['role'],a['model'])
assert collections.Counter(map(identity,cfg['actors']))==collections.Counter(map(identity,before['actors']))
prior={identity(a):a for a in before['actors']}
for a in cfg['actors']:
 b=prior[identity(a)];assert a.get('sensors',[])==b.get('sensors',[])
 assert bool(a.get('destination'))==bool(b.get('destination'))
 if b.get('destination'):
  for key in ('x','y','z'):
   if key in b['destination']:assert abs(a['destination'][key]-b['destination'][key])<.01
assert cfg['weather']==before['weather'];assert len(s['sensors'])==6
removed={v['key'] for v in s['scene_vehicles']['removed']};targets={'BP_Carlacola_Parked_C_7','BP_Carlacola_Parked_C_9','BP_EuropeanHGV_Parked_C_8'};assert targets<=removed;assert len(removed)==13;assert not any(a.get('scene_source') in targets for a in cfg['actors'])
assert len(m['parking_spaces'])+len(m['parking_excluded'])==180
r={'ready':True,'map':cfg['map'],'actors':len(cfg['actors']),'sensors':len(s['sensors']),'workers':s['worker_count'],'frame':s['frame'],'paused':not s['running'],'permanently_removed_sources':len(removed),'remote_trucks_absent':True,'weather_sensors_and_destinations_preserved':True,'parking_positions':180}
(root/'verification.json').write_text(json.dumps(r,indent=2));(root/'after-status.json').write_text(json.dumps(s,indent=2));(root/'after-configuration.json').write_text(json.dumps(cfg,indent=2));print(json.dumps(r,indent=2))
