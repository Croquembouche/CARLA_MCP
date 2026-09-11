import json,urllib.request
from pathlib import Path
base='http://127.0.0.1:8095';out=Path('data/offroad-cleanup-cabin')
def get(path):
 with urllib.request.urlopen(base+path,timeout=180) as r:return json.load(r)
def command(action,p={}):
 request=urllib.request.Request(base+'/api/command/'+action,data=json.dumps(p).encode(),headers={'Content-Type':'application/json','X-Control-Client':'carla-control-center'})
 with urllib.request.urlopen(request,timeout=600) as r:return json.load(r)
s=get('/api/status');config=get('/api/configuration');(out/'before-configuration.json').write_text(json.dumps(config,indent=2));expected={a['id']:a['source'] for a in json.loads((out/'audit.json').read_text())}
assert s['mode']=='live' and not s.get('recording')
for aid,source in expected.items():assert s['managed'][str(aid)]['scene_source']==source
assert s['managed']['28']['role']=='ego'
try:
 if s['running']:print('PAUSE',command('pause'),flush=True)
 for aid in sorted(expected):print('DELETE',aid,command('delete',{'id':aid}),flush=True)
 cfg=get('/api/configuration');(out/'after-removal-configuration.json').write_text(json.dumps(cfg,indent=2))
 sensors=next(a for a in cfg['actors'] if a['id']==28)['sensors'];camera=json.loads(Path('examples/lincoln-cabin-sensors.json').read_text())[0]
 assert not any(a['name']=='cabin_overview' for a in sensors)
 print('ATTACHING_CABIN_CAMERA',flush=True);print(command('sensors',{'id':28,'sensors':sensors+[camera]}),flush=True)
 final=get('/api/status');(out/'after-status.json').write_text(json.dumps(final,indent=2));(out/'configuration.json').write_text(json.dumps(get('/api/configuration'),indent=2))
 assert len(final['managed'])==len(s['managed'])-3;assert len(final['sensors'])==len(s['sensors'])+1
 sensor=next(a for a in final['sensors'] if a['name']=='cabin_overview' and a['parent']==28)
 with urllib.request.urlopen(base+'/api/preview/'+str(sensor['id'])+'?width=960',timeout=60) as r:(out/'cabin-preview.jpg').write_bytes(r.read())
 print('CAMERA',sensor['id'],flush=True)
finally:
 if s['running']:print('RUN',command('run'),flush=True)
