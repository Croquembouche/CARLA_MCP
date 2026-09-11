import json,time
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1]
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p)
 if not r.is_success:raise RuntimeError(a+': '+r.text)
 return r.json()
s=c.get('/api/status').json();ego=next(int(i) for i,m in s['managed'].items() if m['role']=='ego')
defaults=c.get('/api/catalog').json()['defaults'];types=list(c.get('/api/catalog').json()['sensors'])
report=[]
try:
 for i,kind in enumerate(types):
  attrs={'image_size_x':'320','image_size_y':'180'} if 'camera.' in kind else {'channels':'16','range':'40','points_per_second':'20000','rotation_frequency':'20'} if 'lidar.' in kind else {'range':'40','points_per_second':'1000'} if kind.endswith('radar') else {}
  cmd('sensors',{'id':ego,'sensors':[{'name':f'format_{i}','type':kind,'mount':{'z':2.5},'attributes':attrs}]})
  rec=cmd('record-start',{'rosbag':True})
  for _ in range(3):cmd('step')
  done=cmd('record-stop');assert done['status']=='complete' and done['frames']==3
  state=c.get(f'/api/sessions/{rec["id"]}/frame/0').json();assert state['sensor_files'][0]['type']==kind
  assert any(t.endswith('/metadata') for t in done['ros_topics'])
  report.append({'type':kind,'passed':True,'session':rec['id']});print(kind,'PASS',flush=True)
finally:
 (root/'data/sensor-format-report.json').write_text(json.dumps(report,indent=2))
 if len(report)==len(types):cmd('sensors',{'id':ego,'sensors':defaults})
