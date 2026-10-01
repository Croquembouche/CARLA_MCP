"""Runtime evidence, worker health and configuration recovery helpers."""
import hashlib,json,time,threading,os,copy,concurrent.futures
from pathlib import Path
from verification import digest

def provenance(root,config,opendrive):
    sources=[root/'controller.py',root/'movement_signals.py',root/'recording.py',root/'physical_lidar.py',root/'bag_writer.py',root/'native/bag_native.cpp',root/'rosio.py',root/'gpu_resources.py',root/'verification.py',
      Path('/mnt/simulations/carla/Unreal/CarlaUnreal/Plugins/Carla/Shaders/Private/CarlaSensorTrace.usf'),
      Path('/mnt/simulations/carla/LibCarla/source/carla/nav/Navigation.cpp'),
      Path('/mnt/simulations/carla/LibCarla/source/carla/nav/WalkerManager.cpp'),
      Path('/mnt/simulations/carla/LibCarla/source/carla/nav/WalkerEvent.cpp'),
      Path('/mnt/simulations/carla/LibCarla/source/carla/trafficmanager/TrafficLightStage.cpp'),
      Path('/mnt/simulations/carla/Unreal/CarlaUnreal/Plugins/Carla/Source/Carla/Recorder/CarlaReplayer.cpp')]
    return {'captured_at':time.time(),'sources':{str(p):digest(p) for p in sources if p.exists()},
            'map_sha256':hashlib.sha256(opendrive.encode()).hexdigest(),
            'configuration_sha256':hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),
            'carla_version':config.get('server_version'),'fixed_delta_seconds':config.get('fixed_delta_seconds'),
            'tm_seed':config.get('tm_seed'),'pedestrian_seed':config.get('pedestrian_seed'),
            'binaries':{str(p):digest(p) for p in [*root.glob('_bag_native*.so'),Path('/mnt/simulations/venvs/carla/lib/python3.10/site-packages/carla.cpython-310-x86_64-linux-gnu.so'),Path('/mnt/simulations/carla/Unreal/CarlaUnreal/Plugins/Carla/Binaries/Linux/libUnrealEditor-Carla.so')] if p.exists()},'note':'Custom source, native plugin and installed native client fingerprints'}

def watch_workers(owner):
    while not owner.stop_event.wait(.5):
        if not owner.worker_manifest or owner.resizing_workers or owner.state.get('phase') not in ('connected','error'):continue
        try:
            from gpu_resources import read_manifest
            manifest=read_manifest(owner.worker_manifest)
            failure=manifest.get('error')
            for child in manifest.get('children',[]):
                stat=Path(f"/proc/{child['pid']}/stat")
                if not stat.exists() or stat.read_text().rsplit(')',1)[-1].split()[0]=='Z':failure=f"{child['role']} process {child['pid']} stopped"
            if failure and not owner.worker_fault:
                owner.worker_fault=failure;owner.running=False
                owner.state={**owner.state,'phase':'error','running':False,'error':failure,'gpu_operation':{'stage':'failed','detail':failure},'recovery_operation':{'stage':'failed','detail':'Recover the saved configuration to resume; completed recording frames are preserved'},'worker_health':{'status':'failed','detail':failure,'last_complete_frame':owner.state.get('frame'),'recovery_available':(owner.resource_data/'recovery-checkpoint.json').exists()}}
            profiles=[]
            for child in manifest.get('children',[]):
                runtime=Path(os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))/'carla-sensor-profiles'
                p=runtime/f"{child['pid']}.json"
                if not p.exists():p=Path(f"/mnt/simulations/carla/Unreal/CarlaUnreal/Saved/SensorProfiles/{child['pid']}.json")
                if p.exists():profiles.append({'worker':child['role'],'age_seconds':round(time.time()-p.stat().st_mtime,1),**json.loads(p.read_text(encoding='utf-8-sig'))})
            owner.state={**owner.state,'native_profiles':profiles}
        except (OSError,ValueError,RuntimeError):pass

def _complete_checkpoint(owner,wait=False):
    future=getattr(owner,'_checkpoint_future',None)
    if future is None or (not wait and not future.done()):return
    # Surface write failures on the owner thread, and advertise only an
    # atomically published checkpoint as available for recovery.
    completed=future.result()
    owner.state['recovery_checkpoint']={'frame':completed['frame'],'created':completed['created']}
    owner._checkpoint_future=None

def checkpoint(owner):
    if getattr(owner,'_checkpoint_closed',False):return
    _complete_checkpoint(owner)
    if owner.mode!='live' or owner.worker_fault or owner.resizing_workers:return
    if (owner.state.get('recovery_operation') or {}).get('stage')=='restoring':return
    if getattr(owner,'_checkpoint_future',None) is not None:return
    if time.monotonic()-getattr(owner,'checkpoint_at',0)<5:return
    from recording import dump
    # Freeze the completed frame on the owner thread. JSON encoding and mounted
    # filesystem writes can stall for seconds; one bounded writer handles them.
    value=copy.deepcopy({'frame':owner.state['frame'],'time':owner.state['time'],
                         'configuration':owner.export_config(),'created':time.time()})
    if not hasattr(owner,'_checkpoint_executor'):
        owner._checkpoint_executor=concurrent.futures.ThreadPoolExecutor(max_workers=1,thread_name_prefix='recovery-checkpoint')
    def write():
        dump(owner.resource_data/'recovery-checkpoint.json',value)
        return value
    owner._checkpoint_future=owner._checkpoint_executor.submit(write)
    owner.checkpoint_at=time.monotonic()

def finish_checkpoint(owner):
    # Disconnect can tick the world while restoring hidden scene actors.
    # Those cleanup ticks must not submit to an already stopped executor.
    owner._checkpoint_closed=True
    executor=getattr(owner,'_checkpoint_executor',None)
    if executor is None:return
    try:_complete_checkpoint(owner,wait=True)
    finally:executor.shutdown(wait=True)

def walking_state(m,actor,now):
    if m.get('arrived'):return 'arrived'
    if not m.get('destination'):return 'idle'
    loc=actor.get_location();old=m.get('_walking_progress')
    if old is None or ((loc.x-old[0])**2+(loc.y-old[1])**2)>.04:m['_walking_progress']=(loc.x,loc.y,now)
    speed=actor.get_velocity().length()
    if speed>.1:return 'walking'
    return 'blocked or waiting' if now-m['_walking_progress'][2]>3 else 'starting'
