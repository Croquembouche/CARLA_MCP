import time,json,math
from pathlib import Path
import httpx
root=Path('data/parking-open-fix');c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
for _ in range(600):
 try:
  s=c.get('/api/status',timeout=3).json()
  if s.get('phase')=='error':raise RuntimeError(s.get('error'))
  if s.get('recovery_operation',{}).get('stage')=='ready':break
 except httpx.TransportError:pass
 time.sleep(1)
else:raise RuntimeError('Not ready')
aid=next(int(k) for k,m in s['managed'].items() if m['role']=='ego');print('READY',aid,s['managed'][str(aid)].get('parking_trip'),flush=True)
time.sleep(2);c.post('/api/command/run',json={}).raise_for_status();rows=[];last=None;start=time.monotonic();sensors=sorted(v['id'] for v in s['sensors'])
while time.monotonic()-start<500:
 s=c.get('/api/status').json();m=s['managed'][str(aid)];a=next(a for a in s['actors'] if a['id']==aid);trip=m.get('parking_trip',{});row={'frame':s['frame'],'time':s['time'],'stage':trip.get('stage'),'blocked':trip.get('blocked'),'motion':trip.get('motion'),'pose':a['pose'],'speed':math.sqrt(sum(x*x for x in a['velocity'].values())),'control':a['control']};rows.append(row)
 key=(row['stage'],row['blocked'],row['motion'])
 if key!=last:print(json.dumps(row),flush=True);last=key
 if m.get('parked'):
  c.post('/api/command/pause',json={}).raise_for_status();root.joinpath('r136-completed.json').write_text(json.dumps({'actor':a,'managed':m,'sensor_ids':sensors,'after_sensor_ids':sorted(v['id'] for v in s['sensors'])},indent=2));print('PARKED',flush=True);break
 if row['stage']=='blocked' or s.get('phase')=='error':print('FAILED',flush=True);break
 time.sleep(.6)
else:print('TIMEOUT',json.dumps(rows[-1]),flush=True)
root.joinpath('r136-samples.json').write_text(json.dumps(rows,indent=2))
