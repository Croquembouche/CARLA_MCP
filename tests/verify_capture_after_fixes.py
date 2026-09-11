import httpx,time,json
from pathlib import Path
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def get(path):r=c.get('/api/'+path);r.raise_for_status();return r.json()
def cmd(a,p={}):r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
report={};external=None
try:
 cmd('pause');m=get('map');catalog=get('catalog')
 external=cmd('spawn',{'role':'ego','planner':'external','model':catalog['vehicles'][0]['id'],'spawn':m['spawn_points'][30],'sensors':[]})['id']
 def control():cmd('control',{'id':external,'throttle':.3,'steer':0,'brake':0})
 control();cmd('step');time.sleep(1.1);cmd('step');cmd('step')
 a=next(a for a in get('status')['actors'] if a['id']==external);assert a['control']['brake']==1
 control();cmd('step');cmd('step')
 a=next(a for a in get('status')['actors'] if a['id']==external);assert abs(a['control']['throttle']-.3)<.001 and a['control']['brake']==0
 report['same_control_after_watchdog']='passed'
 cmd('delete',{'id':external});external=None;cmd('step')
 rec=cmd('record-start',{'rosbag':True})
 for _ in range(3):cmd('step')
 result=cmd('record-stop');assert result['frames']==3 and result['status']=='complete'
 for i in range(3):
  f=get(f'sessions/{rec["id"]}/frame/{i}');assert len(f['sensor_files'])==5
  assert all(s['frame']==f['frame'] and abs(s['timestamp']-f['time'])<1e-5 for s in f['sensor_files'])
 assert all(count==3 for count in result['ros_topics'].values())
 report.update(passed=True,session=rec['id'],frames=3,sensors=5,ros_topics=result['ros_topics'])
finally:
 if external:cmd('delete',{'id':external})
 Path('data/capture-after-fixes-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
