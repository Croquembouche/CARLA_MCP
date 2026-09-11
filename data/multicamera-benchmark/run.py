from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument('--cameras',type=int,choices=[4,7,10],default=7);args=p.parse_args()
initial=status()
if initial.get('recording'):raise RuntimeError('A recording is active; benchmark must not interrupt it')
save('initial-status.json',initial);cmd('pause');config=c.get('/api/configuration').json();save('original.json',config)
ego_config=next(a for a in config['actors'] if a['role']=='ego');noncamera=[copy.deepcopy(x) for x in ego_config['sensors'] if not x['type'].startswith('sensor.camera.')]
original_cabin=next(x for x in ego_config['sensors'] if x['name']=='cabin_overview')
views= [('front_rgb',0),('front_right',60),('rear_right',120),('rear_rgb',180),('rear_left',-120),('front_left',-60)]
if args.cameras==4:views=[('front_rgb',0),('rear_rgb',180),('left_rgb',-90),('right_rgb',90)]
if args.cameras==10:views=[(f'exterior_{i}',yaw) for i,yaw in enumerate([0,40,80,120,160,-160,-120,-80,-40])]
def loadout(width,height):
 cams=[{'name':name,'type':'sensor.camera.rgb','mount':{'x':1.5 if yaw==0 else -1.4 if abs(yaw)==180 else 0,'y':0,'z':2.2,'yaw':yaw},'attributes':{'image_size_x':str(width),'image_size_y':str(height),'fov':'90','use_ray_tracing':'false','sensor_tick':'0.0'}} for name,yaw in views]
 if args.cameras!=4:
  cabin=copy.deepcopy(original_cabin);cabin['attributes'].update(image_size_x=str(width),image_size_y=str(height));cams.append(cabin)
 return cams+copy.deepcopy(noncamera)
# Two tiny cameras plus the existing ray sensors retain four workers while
# old HD cameras are released. This avoids an artificial old+new HD load spike.
staging=[{'name':f'bench_stage_{i}','type':'sensor.camera.rgb','mount':{'x':1.5,'z':2.2,'yaw':i*180},'attributes':{'image_size_x':'16','image_size_y':'16','fov':'90','use_ray_tracing':'false','sensor_tick':'0.0'}} for i in range(2)]+copy.deepcopy(noncamera)
def apply_quality(tier):
 vals={'High':(.8,1,4,2,1,2000),'Epic':(1,0,8,1,2,4000)}[tier];view,lod,aniso,down,bounces,pool=vals
 settings=['r.RayTracing.ForceAllRayTracingEffects 0','r.RayTracing.ExternalQueryBounds 1']+[f'sg.{g}Quality 3' for g in GROUPS]+['r.ScreenPercentage 100',f'r.ViewDistanceScale {view}',f'r.SkeletalMeshLODBias {lod}',f'r.MaxAnisotropy {aniso}',f'r.VT.MaxAnisotropy {aniso}',f'r.Lumen.Reflections.DownsampleFactor {down}',f'r.Lumen.Reflections.MaxBounces {bounces}',f'r.Streaming.PoolSize {pool}','carla.Camera.UseRayTracing -1']
 cmd('run')
 for port in [2010,2020,2030,2040]:
  for setting in settings:console(port,setting)
 cmd('pause');save(tier.lower()+'-settings.json',settings)
monitor_stop=threading.Event()
def monitor():
 with (OUT/'continuous-resources.jsonl').open('w') as f:
  while not monitor_stop.is_set():
   try:
    r=resources();r['wall']=time.time();f.write(json.dumps(r)+'\n');f.flush()
   except Exception:pass
   monitor_stop.wait(1)
monitor_thread=threading.Thread(target=monitor,daemon=True);monitor_thread.start()
try:
 cmd('gpu-profile',{'profile':'4'})
 for tier,width,height in [('High',1280,720),('Epic',1280,720),('High',1920,1080),('Epic',1920,1080)]:
  name=f'{tier.lower()}-{height}p';save('progress.json',{'stage':'configuring','case':name,'camera_count':args.cameras});print('CONFIGURING',name,args.cameras,'cameras',flush=True)
  ego=next(int(aid) for aid,m in status()['managed'].items() if m['role']=='ego')
  cmd('sensors',{'id':ego,'sensors':staging});check(resources())
  apply_quality(tier)
  cmd('sensors',{'id':ego,'sensors':loadout(width,height)})
  actual=status();assert len([x for x in actual['sensors'] if x['type']=='sensor.camera.rgb'])==args.cameras
  save(name+'-configuration.json',c.get('/api/configuration').json());save(name+'-start-status.json',actual)
  save('progress.json',{'stage':'measuring','case':name,'camera_count':args.cameras});measure(name,90)
  save(name+'-completed.json',{'completed':True,'camera_count':args.cameras,'frame':status()['frame']})
except BaseException as e:
 save('failure.json',{'error':repr(e)});print('BENCHMARK FAILURE',repr(e),flush=True)
finally:
 monitor_stop.set();monitor_thread.join(timeout=5)
 print('RESTORING ORIGINAL',flush=True);save('progress.json',{'stage':'restoring'})
 subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/restore_saved_scene.py'),str(OUT/'original.json')],cwd=ROOT,check=True)
 if initial.get('running'):cmd('run')
 save('restored-status.json',status());save('progress.json',{'stage':'complete'});print('RESTORED',flush=True)
