import json,urllib.request
from pathlib import Path
base='http://127.0.0.1:8095';out=Path('data/offroad-cleanup-cabin')
def get(path):
 with urllib.request.urlopen(base+path,timeout=180) as r:return json.load(r)
def command(action,p={}):
 request=urllib.request.Request(base+'/api/command/'+action,data=json.dumps(p).encode(),headers={'Content-Type':'application/json','X-Control-Client':'carla-control-center'})
 with urllib.request.urlopen(request,timeout=600) as r:return json.load(r)
s=get('/api/status');cfg=get('/api/configuration');sensors=next(a for a in cfg['actors'] if a['id']==28)['sensors'];camera=next(c for c in sensors if c['name']=='cabin_overview');camera['attributes']['post_process_profile']='AmbulanceCabinObservation';camera['mount']={'x':1.6,'y':-.55,'z':1.65,'yaw':140,'pitch':-20}
try:
 if s['running']:command('pause')
 print(command('sensors',{'id':28,'sensors':sensors}),flush=True)
 for i in range(10):command('step')
 state=get('/api/status');sensor=next(a for a in state['sensors'] if a['name']=='cabin_overview' and a['parent']==28)
 with urllib.request.urlopen(base+'/api/preview/'+str(sensor['id'])+'?width=960',timeout=60) as r:(out/'cabin-adjusted.jpg').write_bytes(r.read())
 (out/'configuration.json').write_text(json.dumps(get('/api/configuration'),indent=2))
finally:
 if s['running']:command('run')
