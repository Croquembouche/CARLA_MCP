"""Paused-boundary renderer scaling and measured end-to-end frame timings."""
import collections
import hashlib
import json
import math
import statistics
import time
import uuid
from pathlib import Path

GPU_POOL = [3, 2, 1, 0]  # Vulkan adapter identifiers, not nvidia-smi ordinals.

def read_manifest(path):
    # Logs live on a mounted filesystem whose replace can briefly hide the name.
    deadline=time.monotonic()+3
    while True:
        try:return json.loads(path.read_text())
        except (FileNotFoundError,json.JSONDecodeError) as error:
            if time.monotonic()>=deadline:raise RuntimeError(f'Renderer status file is unavailable: {path}') from error
            time.sleep(.02)

def gpu_sensor(config):
    return config['type'].startswith(('sensor.camera.', 'sensor.lidar.')) or config['type'] == 'sensor.other.radar'

def sensor_cost(config):
    a=config.get('attributes', {}); kind=config['type']
    if kind.startswith('sensor.camera.'): return 4*float(a.get('image_size_x',800))*float(a.get('image_size_y',600))/(640*360)
    if kind.startswith('sensor.lidar.'): return 2*float(a.get('points_per_second',56000))/200000
    if kind=='sensor.other.radar': return .5*float(a.get('points_per_second',1500))/10000
    return 0.

def loadout_key(configs):
    values=sorted(json.dumps(c,sort_keys=True) for c in configs if gpu_sensor(c))
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()[:20]

def desired_workers(configs, profile='auto', measured=None):
    heavy=[c for c in configs if gpu_sensor(c)]
    if not heavy: return 0
    maximum=min(4,len(heavy))
    if profile!='auto': return min(maximum,int(profile))
    if measured is not None: return max(1,min(maximum,int(measured)))
    return min(maximum,max(1,math.ceil(sum(sensor_cost(c) for c in heavy)/4)))

def summary(rows):
    if not rows:return {}
    return {key:{'mean':round(statistics.mean(r[key] for r in rows),2),
                 'p95':round(sorted(r[key] for r in rows)[max(0,math.ceil(.95*len(rows))-1)],2)} for key in rows[0]}

class GpuResources:
    def init_resources(self, data):
        self.resource_data=data;self.worker_manifest=None;self.gpu_profile='auto';self.resizing_workers=False
        self.frame_timings=collections.deque(maxlen=120)
        path=data/'gpu-benchmarks.json'
        try:self.gpu_benchmarks=json.loads(path.read_text())
        except (OSError,ValueError):self.gpu_benchmarks={}

    def profile_key(self, configs):
        context={'renderer_version':'sensor-view-overhead-v1','sensors':loadout_key(configs),'map':self.state.get('map'),'weather':self.state.get('weather'),
                 'models':sorted(m['actor'].type_id for m in self.managed.values())}
        return hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()[:20]

    def process_memory(self):
        result=[]
        for child in read_manifest(self.worker_manifest)['children']:
            try:
                lines=Path(f"/proc/{child['pid']}/smaps_rollup").read_text().splitlines()
                pss=next(int(line.split()[1]) for line in lines if line.startswith('Pss:'))
                result.append({'role':child['role'],'pid':child['pid'],'pss_gib':round(pss/1024**2,3)})
            except (OSError,StopIteration):pass
        return result

    def resource_snapshot(self):
        if not self.worker_manifest:return
        manifest=read_manifest(self.worker_manifest)
        workers=[c for c in manifest['children'] if c['role']!='primary']
        self.state.update(worker_count=len(workers),gpu_profile=self.gpu_profile,
                          gpu_workers=[{'adapter':int(c['role'].split('-')[1]),'pid':c['pid'],'initialized':c['initialized']} for c in workers],
                          physics_backend='Chaos CPU',resource_policy='Measured profile when available; otherwise estimated sensor cost')
        if manifest.get('error'):raise RuntimeError(manifest['error'])
        if self.state.get('gpu_benchmark',{}).get('stage')!='running':
            cached=self.gpu_benchmarks.get(self.profile_key([s['config'] for s in self.sensors.values()]))
            if cached:self.state['gpu_benchmark']={'stage':'complete',**cached}
            elif self.state.get('gpu_benchmark',{}).get('stage')=='complete':self.state.pop('gpu_benchmark',None)

    def resize_pool(self, count):
        if not self.worker_manifest:raise ValueError('Worker scaling requires a simulator started by this interface')
        self.resource_snapshot()
        if self.state['worker_count']==count:return
        request={'id':uuid.uuid4().hex,'gpus':GPU_POOL[:count]}
        self.state['gpu_operation']={'stage':'loading' if count else 'releasing','detail':f'Preparing {count} GPU render workers', 'started':time.time()}
        path=self.worker_manifest.parent/'workers-request.json';tmp=path.with_suffix('.next')
        tmp.write_text(json.dumps(request));tmp.replace(path)
        deadline=time.monotonic()+1800
        while True:
            if self.stop_event.is_set():raise RuntimeError('GPU operation cancelled during shutdown')
            manifest=read_manifest(self.worker_manifest)
            if manifest.get('error'):raise RuntimeError(manifest['error'])
            if self.proc.poll() is not None:raise RuntimeError('Renderer supervisor stopped during scaling')
            self.resource_snapshot()
            if manifest.get('request_id')==request['id'] and not manifest.get('resizing'):break
            if time.monotonic()>deadline:raise RuntimeError('GPU worker initialization timed out')
            time.sleep(.25)
        # Publish a full replicated world to late joiners, then drain their startup frames.
        # No client sensor subscriptions exist during this boundary.
        if count:
            if getattr(self,'scene_vehicles',None):self.scene_vehicles.sync_workers()
            self.state['gpu_operation']['stage']='warming'
            self.state['gpu_operation']['detail']='Synchronizing renderer scenes'
            for _ in range(10):self.tick(publish=False);time.sleep(.05)

    def current_loadouts(self):
        return {aid:[s['config'] for s in self.sensors.values() if s['parent']==aid]
                for aid,m in self.managed.items() if m['role']=='ego'}

    def drop_sensor_streams(self):
        for sid,s in list(self.sensors.items()):
            s['actor'].stop();s['actor'].destroy();self.sensors.pop(sid);self.previews.pop(sid,None)
            if self.ros:self.ros.remove_prefix(f"/carla/ego_{s['parent']}/{s['config']['name']}/")
        self.tick(publish=False)

    def reallocate_sensors(self, loadouts, count):
        previous=self.current_loadouts();old_count=self.state.get('worker_count',0)
        self.resizing_workers=True
        try:
            self.drop_sensor_streams();self.resize_pool(count)
            self.state['gpu_operation']={'stage':'verifying','detail':'Checking synchronized sensor frames','started':time.time()}
            # Expensive loadouts first; the native router balances sensor costs across workers.
            for aid,configs in sorted(loadouts.items(),key=lambda x:-sum(sensor_cost(c) for c in x[1])):
                self.configure_sensors(aid,sorted(configs,key=sensor_cost,reverse=True))
            self.resource_snapshot();self.refresh()
            self.state['gpu_operation']={'stage':'ready','detail':f'{count} GPU workers ready; sensor frames verified','started':time.time()}
        except Exception as error:
            if self.stop_event.is_set():raise
            self.state['gpu_operation']={'stage':'failed','detail':str(error),'started':time.time()}
            try:
                self.drop_sensor_streams();self.resize_pool(old_count)
                for aid,configs in previous.items():self.configure_sensors(aid,configs)
                self.refresh()
                self.state['gpu_operation']={'stage':'failed','detail':f'Previous loadout restored after: {error}','started':time.time()}
            except Exception as rollback:
                self.state['gpu_operation']['detail']+=f'; loadout recovery failed: {rollback}'
            raise
        finally:self.resizing_workers=False

    def reconcile_resources(self):
        if not self.worker_manifest or self.running or self.recording or self.mode!='live':return
        configs=[s['config'] for s in self.sensors.values()]
        count=desired_workers(configs,self.gpu_profile,self.gpu_benchmarks.get(self.profile_key(configs),{}).get('selected_workers'))
        if count!=self.state.get('worker_count'):self.apply_gpu_profile(self.gpu_profile)

    def apply_gpu_profile(self, profile):
        if not self.worker_manifest:raise ValueError('Worker scaling requires a simulator started by this interface')
        if profile not in ('auto','1','2','3','4'):raise ValueError('Choose auto or a maximum of one to four workers')
        loadouts=self.current_loadouts();configs=[c for v in loadouts.values() for c in v]
        result=self.gpu_benchmarks.get(self.profile_key(configs),{})
        count=desired_workers(configs,profile,result.get('selected_workers'))
        self.reallocate_sensors(loadouts,count);self.gpu_profile=profile;self.resource_snapshot()
        return {'workers':count,'profile':profile}

    def benchmark_gpu_profile(self):
        if not self.worker_manifest:raise ValueError('GPU profiling requires a simulator started by this interface')
        loadouts=self.current_loadouts();configs=[c for v in loadouts.values() for c in v]
        maximum=min(4,sum(gpu_sensor(c) for c in configs))
        if not maximum:raise ValueError('Add camera, LiDAR or radar sensors before profiling')
        results=[];original_count=self.state.get('worker_count',1)
        self.state['gpu_benchmark']={'stage':'running','results':results}
        try:
            for count in range(1,maximum+1):
                self.state['gpu_benchmark']['detail']=f'Measuring {count} GPU workers; simulation time advances'
                self.reallocate_sensors(loadouts,count)
                trials=[];all_rows=[]
                for repeat in range(3):
                    for _ in range(10):self.tick()
                    self.frame_timings.clear()
                    for _ in range(50):self.tick()
                    rows=list(self.frame_timings);all_rows.extend(rows)
                    trials.append({'repeat':repeat+1,'frames':50,'timings_ms':summary(rows)})
                stats=summary(all_rows)
                results.append({'workers':count,'frames':150,'trials':trials,'timings_ms':stats,'memory':self.process_memory()})
                self.state['gpu_benchmark']['results']=list(results)
                (self.resource_data/'gpu-benchmark-progress.json').write_text(json.dumps(self.state['gpu_benchmark'],indent=2))
            fastest=min(r['timings_ms']['total_ms']['mean'] for r in results)
            # Prefer lower memory when throughput is within 10% of the fastest measurement.
            selected=min(r['workers'] for r in results if r['timings_ms']['total_ms']['mean']<=fastest*1.10)
            report={'selected_workers':selected,'results':results,'measured_at':time.time(),
                    'selection':'Fewest workers within 10% of lowest mean frame time; Three 50-frame windows per profile; evolving-scene throughput sample'}
            self.gpu_benchmarks[self.profile_key(configs)]=report
            path=self.resource_data/'gpu-benchmarks.json';tmp=path.with_suffix('.next');tmp.write_text(json.dumps(self.gpu_benchmarks,indent=2));tmp.replace(path)
            self.reallocate_sensors(loadouts,selected);self.gpu_profile='auto';self.resource_snapshot()
            self.state['gpu_benchmark']={'stage':'complete',**report};return report
        except Exception:
            self.state['gpu_benchmark']['stage']='failed'
            if not self.stop_event.is_set():self.reallocate_sensors(loadouts,original_count)
            raise
