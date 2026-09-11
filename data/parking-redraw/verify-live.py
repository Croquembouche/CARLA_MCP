import json,httpx,collections
from pathlib import Path
root=Path('data/parking-redraw');c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def get(p):r=c.get('/api/'+p);r.raise_for_status();return r.json()
def cmd(a,p={}):r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
s=get('status');cfg=get('configuration');old=json.loads((root/'before-configuration.json').read_text());m=get('map')
assert s['recovery_operation']['stage']=='ready' and not s['running'] and not s.get('error')
assert len(cfg['actors'])==len(old['actors'])==31
assert collections.Counter((a['model'],a['role']) for a in cfg['actors'])==collections.Counter((a['model'],a['role']) for a in old['actors'])
e=next(a for a in cfg['actors'] if a['role']=='ego');oe=next(a for a in old['actors'] if a['role']=='ego');assert e['sensors']==oe['sensors'] and all(abs(e['destination'][k]-oe['destination'][k])<.001 for k in ['x','y','z']);assert cfg['weather']==old['weather']
assert len(m['parking_spaces'])==46 and len(m['parking_excluded'])==115 and len(m['parking_curb_strips'])==72
assert m['parking_spaces']==json.loads(Path('static/parking-survey/annotations.json').read_text())['parking_spaces']
report={'restored_actors':31,'restored_sensors':6,'ego_sensor_config_preserved':True,'weather_preserved':True,'ego_goal_preserved':True,'selectable':46,'restricted':115,'curb_strips':72}
aid=None
try:
 b=next(b for b in m['parking_spaces'] if b['id']=='R112');assert not s['parking']['occupied'].get(b['id'])
 result=cmd('spawn',{'role':'background','model':'vehicle.mini.cooper','parking_space':b['id']});aid=result['id'];report['test_spawn']={'id':aid,'bay':b['id'],'result':result};assert get('status')['managed'][str(aid)]['parking_space']==b['id']
 denied=c.post('/api/command/spawn',json={'role':'background','model':'vehicle.mini.cooper','parking_space':'P008'});assert denied.status_code==400 and 'parking bay' in denied.text
 denied=c.post('/api/command/destination',json={'id':aid,'point':{'parking_space':'P008'}});assert denied.status_code==400 and 'parking bay' in denied.text
 report['restricted_spawn_and_destination_rejected']=True
 # Exercise selection of another surveyed roadside bay. The full maneuver is
 # outside this annotation test; remove the temporary vehicle before running.
 result=cmd('destination',{'id':aid,'point':{'parking_space':'R113'}});report['new_parking_destination']=result
 assert result['destination']['parking_space']=='R113'
finally:
 if aid is not None:cmd('delete',{'id':aid})
 if json.loads((root/'before-status.json').read_text()).get('running'):cmd('run')
 s=get('status');(root/'final-status.json').write_text(json.dumps(s,indent=2));(root/'final-configuration.json').write_text(json.dumps(get('configuration'),indent=2))
 report['final_actors']=len(s.get('managed',{}));report['running']=s['running'];report['error']=s.get('error');(root/'live-verification.json').write_text(json.dumps(report,indent=2))
assert report['final_actors']==31 and not report['error'];print(json.dumps({k:v for k,v in report.items() if k not in ['test_spawn','new_parking_destination']},indent=2))
