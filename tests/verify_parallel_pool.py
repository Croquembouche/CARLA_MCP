"""Live pool lifecycle acceptance; restores the ego's original sensor loadout."""
import json,time,subprocess,sys,sqlite3,re
from pathlib import Path
import httpx
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from gpu_resources import gpu_sensor
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=2000,headers={'X-Control-Client':'carla-control-center'})
def command(action,p={}):
 r=c.post('/api/command/'+action,json=p)
 if r.is_error:raise RuntimeError(f'{action}: {r.status_code} {r.text}')
 return r.json()
def state():return c.get('/api/status').json()
def steps(n):
 for _ in range(n):command('step')
 s=state();assert s['phase']=='connected' and not s.get('error');return s
s=state();assert not s['running'] and not s.get('recording')
ego=next(int(i) for i,m in s['managed'].items() if m['role']=='ego')
original=[{k:v for k,v in x.items() if k not in ('id','parent')} for x in s['sensors'] if x['parent']==ego]
actor_ids=set(s['managed']);report={}
manifest=max(Path('/mnt/simulations/carla/carlab/host-setup/logs').glob('multigpu-*/processes.json'),key=lambda p:p.stat().st_mtime)
def memory():
 result=[]
 for ch in json.loads(manifest.read_text())['children']:
  lines=Path(f"/proc/{ch['pid']}/smaps_rollup").read_text().splitlines()
  result.append({'role':ch['role'],'pid':ch['pid'],'pss_gib':round(next(int(x.split()[1]) for x in lines if x.startswith('Pss:'))/1024**2,3)})
 return result
try:
 # Four GPU streams exercise every worker, while CPU sensors stay on primary.
 extra={'name':'parallel_test_rgb','type':'sensor.camera.rgb','mount':{'z':2.2,'yaw':90},'attributes':{'image_size_x':'320','image_size_y':'180','fov':'90'}}
 command('sensors',{'id':ego,'sensors':original+[extra]})
 command('gpu-profile',{'profile':'4'})
 s=steps(20);assert s['worker_count']==4 and len(s['sensors'])==len(original)+1
 sockets=subprocess.check_output(['ss','-tnp'],text=True)
 ports=[port for port in (2011,2021,2031,2041) if f':{port} ' in sockets]
 assert len(ports)==4,ports
 routes=[dict(zip(('actor','primary_stream','worker_port','local_stream','cost'),values)) for values in re.findall(r'GPU_SENSOR_ROUTE actor=(\d+) stream=(\d+) worker_port=(\d+) local_stream=(\d+) cost=([0-9.]+)',(manifest.parent/'primary.log').read_text(errors='replace'))[-4:]]
 assert len({r['worker_port'] for r in routes})==4,routes
 assert {int(r['actor']) for r in routes}=={x['id'] for x in s['sensors'] if gpu_sensor(x)}
 report['native_routes']=routes
 report['four_workers']={'frame':s['frame'],'sensors':len(s['sensors']),'streaming_ports':ports,'memory':memory(),'performance':s['performance']}
 print('FOUR_GPU_STREAMS_VERIFIED',flush=True)
 rec=command('record-start',{'rosbag':True});steps(10);done=command('record-stop')
 session=root/'data/recordings'/done['id'];report['recording']={'id':done['id'],'frames':done['frames'],'status':done['status']}
 assert done['status']=='complete' and done['frames']==10
 frames=[json.loads(line) for line in (session/'states.jsonl').read_text().splitlines()]
 assert len(frames)==10 and all(len(f['sensor_files'])==len(original)+1 for f in frames)
 assert all(len([a for a in f['actors'] if a['type'].startswith('traffic.traffic_light')])==15 for f in frames)
 assert all((session/item['path']).is_file() and (session/item['path']).stat().st_size==item['bytes'] for f in frames for item in f['sensor_files'])
 db=next((session/'rosbag2').glob('*.db3'))
 with sqlite3.connect(db) as connection:
  counts=connection.execute('select t.name,count(*) from messages m join topics t on t.id=m.topic_id group by t.name').fetchall()
 assert all(n==10 for _,n in counts),counts
 sensor_topics=[(topic,n) for topic,n in counts if topic.startswith(f'/carla/ego_{ego}/') and topic.endswith(('/image','/points','/data'))]
 assert len(sensor_topics)==len(original)+1,sensor_topics
 report['recording']['sensor_topic_counts']=sensor_topics
 clouds=[item for frame in frames for item in frame['sensor_files'] if item['type']=='sensor.lidar.ray_cast']
 for item in clouds:
  points=np.fromfile(session/item['path'],dtype='<f4').reshape(-1,4)
  assert len(points)>100 and np.isfinite(points).all()
  assert np.linalg.norm(points[:,:3],axis=1).max()<=81
 images=[item for frame in frames for item in frame['sensor_files'] if item['type']=='sensor.camera.rgb']
 for item in images:
  pixels=np.fromfile(session/item['path'],dtype=np.uint8).reshape(-1,4)
  assert len(pixels)==item['width']*item['height'] and pixels[:,:3].std()>5
 report['recording']['lidar_and_camera_payloads_valid']=True
 print('ROS_RECORDING_VERIFIED',flush=True)
 cpu=[cfg for cfg in original if not gpu_sensor(cfg)]
 command('sensors',{'id':ego,'sensors':cpu})
 s=steps(20);assert s['worker_count']==0 and len(s['sensors'])==len(cpu)
 report['zero_workers']={'frame':s['frame'],'cpu_sensor_count':len(cpu),'memory':memory(),'performance':s['performance']}
 print('ZERO_GPU_CPU_SENSORS_VERIFIED',flush=True)
finally:
 if state().get('recording'):command('record-stop')
 command('gpu-profile',{'profile':'auto'})
 command('sensors',{'id':ego,'sensors':original})
 s=steps(20)
 report['restored']={'frame':s['frame'],'worker_count':s['worker_count'],'sensor_count':len(s['sensors']),'actor_ids':list(s['managed'])}
 assert set(s['managed'])==actor_ids
 assert len(s['sensors'])==len(original)
 (root/'data/parallel-pool-acceptance.json').write_text(json.dumps(report,indent=2))
 print('ORIGINAL_LOADOUT_RESTORED',flush=True)
