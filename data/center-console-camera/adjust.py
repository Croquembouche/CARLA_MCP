import json,urllib.request
from pathlib import Path
base='http://127.0.0.1:8095';out=Path('data/center-console-camera')
def get(ep):
 with urllib.request.urlopen(base+'/api/'+ep,timeout=180) as r:return json.load(r)
def cmd(action,p={}):
 req=urllib.request.Request(base+'/api/command/'+action,data=json.dumps(p).encode(),headers={'Content-Type':'application/json','X-Control-Client':'carla-control-center'})
 with urllib.request.urlopen(req,timeout=600) as r:return json.load(r)
s=get('status');config=get('configuration');ego=next(a for a in config['actors'] if a['role']=='ego');assert ego['id']==60 and ego['model']=='vehicle.lincoln.mkz_interior';assert not s.get('recording') and s['mode']=='live'
camera=next(c for c in ego['sensors'] if c['name']=='cabin_overview');camera['mount']={'x':.55,'y':0,'z':1.2,'yaw':180,'pitch':-8,'roll':0}
try:
 if s['running']:cmd('pause')
 print(cmd('sensors',{'id':60,'sensors':ego['sensors']}),flush=True)
 for _ in range(15):cmd('step')
 final=get('status');sid=next(c['id'] for c in final['sensors'] if c['parent']==60 and c['name']=='cabin_overview')
 with urllib.request.urlopen(base+'/api/preview/'+str(sid)+'?width=960',timeout=60) as r:(out/'preview.jpg').write_bytes(r.read())
 (out/'configuration.json').write_text(json.dumps(get('configuration'),indent=2));print('SENSOR',sid,flush=True)
finally:
 if s['running']:cmd('run')
