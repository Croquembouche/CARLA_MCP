import sys,time,json,httpx,subprocess,os,socket,struct,statistics,copy,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));import bootstrap,carla
OUT=ROOT/'data/multicamera-benchmark'; c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=15)
def status():return c.get('/api/status').json()
def cmd(name,p={}):
 r=c.post('/api/command/'+name,json=p,headers={'X-Control-Client':'carla-control-center'},timeout=240);
 if r.is_error:save('command-error.json',{'command':name,'response':r.text,'status':status()})
 r.raise_for_status();return r.json()
def save(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2))
def console(port,command):
 b=command.encode();method=b'console_command';packet=b'\x94\x00\x01\xdb'+struct.pack('>I',len(method))+method+b'\x92\x91\xc2\xdb'+struct.pack('>I',len(b))+b
 with socket.create_connection(('127.0.0.1',port),timeout=30) as s:s.sendall(packet);reply=s.recv(65536)
 if reply.hex()!='940101c0919201c3':raise RuntimeError(('console',command,reply.hex()))
GROUPS=['ViewDistance','AntiAliasing','Shadow','GlobalIllumination','Reflection','PostProcess','Texture','Effects','Foliage','Shading','Landscape']
MAX=['r.RayTracing.ExternalQueryBounds 1']+[f'sg.{x}Quality 3' for x in GROUPS]+['r.ScreenPercentage 100','r.ViewDistanceScale 1','r.SkeletalMeshLODBias 0','r.MaxAnisotropy 8','r.VT.MaxAnisotropy 8','r.Lumen.Reflections.DownsampleFactor 1','r.Lumen.Reflections.MaxBounces 2','r.Streaming.PoolSize 4000','r.Shadow.Virtual.MaxPhysicalPages 8192','r.RayTracing.ForceAllRayTracingEffects 0','carla.Camera.UseRayTracing -1']
def resources():
 gpu=subprocess.check_output(['nvidia-smi','--query-gpu=index,utilization.gpu,utilization.memory,memory.used,power.draw','--format=csv,noheader,nounits'],text=True)
 gs=[dict(zip(['index','gpu_percent','memory_controller_percent','vram_mib','power_watts'],map(float,line.split(',')))) for line in gpu.strip().splitlines()]
 mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.split(':')[0] in ['MemTotal','MemAvailable']}
 cg=Path('/sys/fs/cgroup')/subprocess.check_output(['systemctl','--user','show','carla-control-center.service','-p','ControlGroup','--value'],text=True).strip().lstrip('/')
 cpu=dict(line.split() for line in (cg/'cpu.stat').read_text().splitlines());memory=int((cg/'memory.current').read_text())
 return {'gpus':gs,'service_memory_gib':memory/2**30,'host_used_gib':(mem['MemTotal']-mem['MemAvailable'])/2**30,'host_available_gib':mem['MemAvailable']/2**30,'cpu_usage_usec':int(cpu['usage_usec'])}
def check(r):
 if r['host_available_gib']<10:save('resource-limit.json',r);raise RuntimeError('Stopped benchmark: less than 10 GiB available system RAM')
 if max(g['vram_mib'] for g in r['gpus'])>10800:save('resource-limit.json',r);raise RuntimeError('Stopped benchmark: GPU memory above 10,800 MiB')
def measure(name,seconds):
 cmd('run');start=time.monotonic();warm_start=status()['frame'];last=warm_start
 warmup=[]
 while status()['frame']<warm_start+30:
  resource=resources();warmup.append(resource);save(name+'-warmup.json',warmup);check(resource)
  if time.monotonic()-start>180:raise RuntimeError('Warmup exceeded 180 seconds')
  time.sleep(1)
 rows=[];start=time.monotonic();s=status();startframe=s['last_complete_frame'];last=startframe;advanced=start;maxgap=0
 while time.monotonic()-start<seconds:
  t=time.monotonic();s=status();now=time.monotonic();r=resources();check(r)
  if s.get('error'):raise RuntimeError(s['error'])
  f=s.get('last_complete_frame',s['frame'])
  if f!=last:maxgap=max(maxgap,now-advanced);advanced=now;last=f
  if now-advanced>30:raise RuntimeError('Frame delivery stopped for 30 seconds')
  r.update(seconds=now-start,wall=time.time(),frame=f,http_ms=(now-t)*1000,timings=s.get('performance',{}).get('last_frame_ms'),health=s.get('stream_health'));rows.append(r)
  # Request both visible camera previews at the same rate in every case.
  for sensor in s['sensors']:
   if sensor['type']=='sensor.camera.rgb':c.get(f"/api/preview/{sensor['id']}?width=960").raise_for_status()
  if len(rows)%15==1:print(name,json.dumps({'frame':f,'ram':r['service_memory_gib'],'vram':[g['vram_mib'] for g in r['gpus']],'gpu':[g['gpu_percent'] for g in r['gpus']]}),flush=True)
  save(name+'.json',{'name':name,'start_frame':startframe,'last_frame':last,'max_observed_frame_gap_s':maxgap,'samples':rows})
  time.sleep(.8)
 cmd('pause')
 for sensor in status()['sensors']:
  if sensor['type']=='sensor.camera.rgb':(OUT/(name+'-'+sensor['name']+'.jpg')).write_bytes(c.get(f"/api/preview/{sensor['id']}?width=960").content)
 print('COMPLETE',name,last-startframe,flush=True)
