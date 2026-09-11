import json,time,math
from pathlib import Path
import httpx
root=Path('data/parking-open-fix');c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
for attempt in range(600):
 try:
  ready=c.get('/api/status',timeout=3).json()
  if ready.get('phase')=='error':raise RuntimeError(ready.get('error'))
  if ready.get('recovery_operation',{}).get('stage')=='ready':break
 except httpx.TransportError:pass
 time.sleep(1)
else:raise RuntimeError('Restore did not complete')
time.sleep(2)
s=c.get('/api/status').json();aid=next(int(k) for k,m in s['managed'].items() if m['role']=='ego');bay=next(b for b in c.get('/api/map').json()['parking_spaces'] if b['id']=='R136');goal={k:bay[k] for k in ('x','y','z')};goal['parking_space']=bay['id'];r=c.post('/api/command/destination',json={'id':aid,'point':goal});print('RESPONSE',r.status_code,r.text[:250],flush=True);r.raise_for_status();print('ASSIGNED',r.json()['parking_trip'],flush=True);c.post('/api/command/run',json={}).raise_for_status();rows=[];last=None;started=time.monotonic()
while time.monotonic()-started<500:
 s=c.get('/api/status').json();m=s['managed'][str(aid)];a=next(a for a in s['actors'] if a['id']==aid);trip=m.get('parking_trip',{});row={'frame':s['frame'],'stage':trip.get('stage'),'blocked':trip.get('blocked'),'motion':trip.get('motion'),'pose':a['pose'],'control':a['control']};rows.append(row)
 key=(row['stage'],row['blocked'],row['motion'])
 if key!=last:print(json.dumps(row),flush=True);last=key
 if m.get('parked') or row['stage']=='blocked' or s.get('phase')=='error':
  c.post('/api/command/pause',json={}).raise_for_status();root.joinpath('r136-result.json').write_text(json.dumps({'actor':a,'managed':m,'sensors':s['sensors']},indent=2));print('RESULT',trip,flush=True);break
 time.sleep(.6)
root.joinpath('r136-samples.json').write_text(json.dumps(rows,indent=2))
