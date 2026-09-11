import sys,time,json,httpx
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root));import bootstrap,carla
out=root/'data/lag-light-fix';c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=10)
for _ in range(600):
 try:
  s=c.get('/api/status').json()
  if s.get('phase')=='error':raise RuntimeError(s.get('error'))
  if s.get('recovery_operation',{}).get('stage')=='ready':break
 except httpx.TransportError:pass
 time.sleep(1)
else:raise RuntimeError('restore timeout')
def cmd(n,p={}):
 r=c.post('/api/command/'+n,json=p,headers={'X-Control-Client':'carla-control-center'},timeout=120);r.raise_for_status();return r.json()
start=s['frame'];records=[];started=time.monotonic();last_frame=start;last_advance=started;max_gap=0
cmd('run')
try:
 while True:
  t=time.monotonic();s=c.get('/api/status').json();http_ms=(time.monotonic()-t)*1000
  if s.get('error'):raise RuntimeError(s['error'])
  now=time.monotonic();f=s.get('last_complete_frame',s['frame'])
  if f!=last_frame:max_gap=max(max_gap,now-last_advance);last_advance=now;last_frame=f
  rss={str(w['adapter']):int(next(x for x in Path(f"/proc/{w['pid']}/status").read_text().splitlines() if x.startswith('VmRSS:')).split()[1])/1048576 for w in s['gpu_workers']}
  row={'wall':time.time(),'seconds':round(now-started,2),'frame':f,'http_ms':round(http_ms,2),'rss_gib':rss,'gap_seconds':round(now-last_advance,2),'timings':s.get('performance',{}).get('last_frame_ms'),'health':s.get('stream_health'),'native_profiles':s.get('native_profiles')};records.append(row)
  if len(records)%15==1:print(json.dumps({k:v for k,v in row.items() if k not in ('timings','native_profiles')}),flush=True)
  for cam in s.get('sensors',[]):
   if cam['type']=='sensor.camera.rgb':
    r=c.get(f"/api/preview/{cam['id']}?width=640");r.raise_for_status()
  if max(rss.values())>24:raise RuntimeError('Camera worker exceeded 24 GiB during acceptance')
  if f>=start+1000:break
  if now-started>650:raise RuntimeError('soak time limit')
  time.sleep(.8)
finally:
 cmd('pause');(out/'soak-final.json').write_text(json.dumps({'start_frame':start,'last_frame':last_frame,'max_observed_gap_seconds':max_gap,'samples':records},indent=2))
print('SOAK COMPLETE',last_frame-start,'frames',max_gap,'max gap',flush=True)
