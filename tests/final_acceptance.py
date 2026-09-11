import httpx,time,subprocess,sys,json,tarfile,io
from pathlib import Path
root=Path(__file__).resolve().parents[1]
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def ready():
 deadline=time.monotonic()+1800;last=None
 while time.monotonic()<deadline:
  s=c.get('/api/status').json()
  if s['phase']!=last:print('PHASE',s['phase'],flush=True);last=s['phase']
  if s['phase']=='connected':return
  if s['phase']=='error':raise RuntimeError(s['error'])
  time.sleep(2)
 raise TimeoutError('Simulator startup')
def run(script):
 print('RUN',script,flush=True)
 subprocess.run([sys.executable,'tests/'+script],cwd=root,check=True)
r=c.post('/api/command/start',json={'gpus':'0,1,2,3'});r.raise_for_status();ready()
if '--skip-native' not in sys.argv:
 run('native_replay.py');ready()
else:
 assert json.loads((root/'data/native-replay-report.json').read_text())['passed']
 print('REUSE previously passed native replay and fresh-scene restart check',flush=True)
run('live_workflow.py');run('verify_bag.py');run('sensor_formats.py')
for _ in range(3):
 r=c.post('/api/command/step',json={});r.raise_for_status()
for script in ('browser.cjs','browser-live.cjs'):
 print('RUN',script,flush=True);subprocess.run(['node','tests/'+script],cwd=root,check=True)
s=c.get('/api/status').json();assert s['phase']=='connected' and not s['running'] and not s['error']
report=json.loads((root/'data/live-workflow-report.json').read_text());session=report['session']
# Read an archive as a stream; no second full recording copy is written.
class Download:
 def __init__(self,response):self.it=response.iter_bytes(1024*1024);self.buf=b''
 def read(self,n):
  while len(self.buf)<n:
   try:self.buf+=next(self.it)
   except StopIteration:break
  data,self.buf=self.buf[:n],self.buf[n:];return data
with c.stream('GET',f'/api/sessions/{session}/archive') as response:
 response.raise_for_status()
 with tarfile.open(fileobj=Download(response),mode='r|') as tar:
  names=[m.name for m in tar]
assert any(n.endswith('rosbag2_0.db3') for n in names) and any('/sensors/' in n for n in names)
result={'native_report_reused':'--skip-native' in sys.argv,'passed':True,'session':session,'archive_files':len(names),'live_workflow':True,'rosbag_readback':True,'native_replay_and_fresh_restart':True,'sensor_formats':11,'browser_desktop_mobile_3d_mesh_replay':True,'state':{'phase':s['phase'],'map':s['map'],'actors':len(s['managed']),'sensors':len(s['sensors'])}}
(root/'data/acceptance-report.json').write_text(json.dumps(result,indent=2));print('ALL_ACCEPTANCE_CHECKS_PASSED',json.dumps(result),flush=True)
