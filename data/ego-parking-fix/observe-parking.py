import httpx,time,json,math
from pathlib import Path
p=Path(__file__).resolve().parent;c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=60,headers={'X-Control-Client':'carla-control-center'});s=c.get('/api/status').json();ego=next(i for i,m in s['managed'].items() if m['role']=='ego');assert s['managed'][ego]['destination']['parking_space']=='P024';sensors=[x['id'] for x in s['sensors']];r=c.post('/api/command/run',json={});r.raise_for_status();samples=[];last=None;reverse=False
for _ in range(240):
 s=c.get('/api/status').json();m=s['managed'][ego];a=next(a for a in s['actors'] if str(a['id'])==ego);trip=m.get('parking_trip',{});stage=trip.get('stage');reverse|=a.get('control',{}).get('reverse',False)
 sample=dict(frame=s['frame'],stage=stage,motion=trip.get('motion'),blocked=trip.get('blocked'),pose=a['pose'],control=a.get('control'));samples.append(sample);(p/'parking-samples.json').write_text(json.dumps(samples,indent=2))
 if stage!=last:print(json.dumps(sample),flush=True);last=stage
 if stage=='parked':
  assert m['parked'] and m['parking_space']=='P024' and m['role']=='ego' and m['planner']=='tm';assert [x['id'] for x in s['sensors']]==sensors
  (p/'parking-completed.json').write_text(json.dumps(dict(ego=ego,bay='P024',reverse_observed=reverse,pose=a['pose'],sensor_ids_preserved=True,frame=s['frame'],running=s['running']),indent=2));break
 if stage=='blocked' or s.get('error'):raise RuntimeError(json.dumps(sample))
 time.sleep(2)
else:raise RuntimeError('Parking did not complete within 8 minutes')
(p/'parking-samples.json').write_text(json.dumps(samples,indent=2));print('EGO_PARKING_COMPLETED',flush=True)
