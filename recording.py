import json
import hashlib
import concurrent.futures
import os
from verification import seal, verify_session
import struct
import time
from pathlib import Path
from uuid import uuid4
from physical_lidar import is_physical, metadata as physical_metadata


def recording_storage(root):
    """Optional fast durable storage; the existing session catalog stays stable."""
    configured=os.environ.get('CARLA_RECORDING_STORAGE')
    return Path(configured).expanduser().resolve() if configured else Path(root).resolve()


def dump(path, value):
    target=Path(path); temp=target.with_suffix(target.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)); temp.replace(target)


def sensor_payload(sample):
    """Read the native property once and retain immutable bytes for this frame."""
    data=sample['data']
    frame,timestamp=getattr(data,'frame',None),getattr(data,'timestamp',None)
    cached=sample.get('_captured_payload')
    if cached is None or cached[0] is not data or cached[1:3]!=(frame,timestamp):
        raw=getattr(data,'raw_data',None)
        cached=(data,frame,timestamp,None if raw is None else bytes(raw))
        sample['_captured_payload']=cached
    return cached[3]


def sensor_metadata(sample):
    data=sample['data']
    result={'type':sample['type'],'name':sample['config']['name'],'parent':sample['parent'],
            'frame':data.frame,'timestamp':data.timestamp,'transform':sample['pose'],
            'attributes':sample['config']['attributes'],'mount':sample['config'].get('mount',{})}
    if hasattr(data,'width'):result.update(width=data.width,height=data.height,fov=data.fov)
    if hasattr(data,'channels'):
        result.update(channels=data.channels,horizontal_angle=data.horizontal_angle)
        if is_physical(data):result.update(physical_metadata(data,sensor_payload(sample)))
        else:result['point_counts']=[data.get_point_count(i) for i in range(data.channels)]
    if hasattr(data,'compass'):result['compass']=data.compass
    return result


def write_sensor_payload(target,payload,atomic):
    started=time.perf_counter()
    if atomic:
        temp=target.with_suffix(target.suffix+'.tmp');temp.write_bytes(payload);temp.replace(target)
    else:target.write_bytes(payload)
    disk_ms=(time.perf_counter()-started)*1000
    started=time.perf_counter();sha256=hashlib.sha256(payload).hexdigest()
    return sha256,disk_ms,(time.perf_counter()-started)*1000


class Recording:
    def __init__(self, root, client, ros, config, map_data, opendrive, bag):
        root=Path(root);root.mkdir(parents=True,exist_ok=True)
        name=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6]
        storage=recording_storage(root);storage.mkdir(parents=True,exist_ok=True)
        self.path=root/name
        physical_path=storage/name
        physical_path.mkdir()
        if storage!=root.resolve():
            try:self.path.symlink_to(physical_path,target_is_directory=True)
            except Exception:
                physical_path.rmdir()
                raise
        self.ros=ros; self.client=client; self.closed=False;self.pending_batch=None
        self.manifest={'id':self.path.name,'created':time.time(),'status':'recording','frames':0,
                       'map':map_data['name'],'configuration':config,'rosbag':bag,
                       'sensor_format':'Unmodified CARLA raw_data bytes, or JSON for IMU/GNSS; per-frame index includes type, dimensions, pose and timestamp.',
                       'coordinates':'Raw states and sensor files use CARLA metres and left-handed axes. ROS messages use right-handed x forward, y left, z up; camera optical frame x right, y down, z forward.',
                       'replay':'Use states.jsonl and original sensor files for exact captured values; carla.log is native actor replay, not bit-identical regenerated sensors.'}
        dump(self.path/'manifest.json',self.manifest); dump(self.path/'map.json',map_data)
        dump(self.path/'configuration.json',config)
        from reliability import provenance
        dump(self.path/'provenance.json',provenance(Path(__file__).parent,config,opendrive))
        (self.path/'map.xodr').write_text(opendrive)
        self.directories=set()
        self.events=(self.path/'events.jsonl').open('a')
        self.states=(self.path/'states.jsonl').open('wb'); self.index=(self.path/'frames.idx').open('wb')
        try:
            if bag: ros.start_bag(self.path/'rosbag2')
            result=client.start_recorder(str(self.path/'carla.log'),True)
            if not result or 'error' in result.lower(): raise RuntimeError('CARLA recorder failed: '+result)
            self.manifest['native_recorder']=result
        except Exception:
            self.close('failed'); raise

    def event(self,action,payload,frame,simulation_time):
        self.events.write(json.dumps({'action':action,'payload':payload,'frame':frame,'time':simulation_time},allow_nan=False)+'\n');self.events.flush()

    def prepare(self,samples,prepared=None):
        if self.closed:raise RuntimeError('Recording is closed')
        if prepared is None:
            if self.pending_batch is not None:raise RuntimeError('Previous raw sensor batch is not committed')
            items=[];pending=[]
            timings=dict(raw_copy_ms=0.,raw_disk_ms=0.,raw_hash_ms=0.,raw_metadata_ms=0.)
            payload_started=time.perf_counter()
            self.pending_batch=(pending,items,timings,payload_started)
            self.pending_frame=None
        elif prepared is not self.pending_batch:
            raise RuntimeError('Raw sensor batch does not belong to this recording')
        pending,items,timings,payload_started=self.pending_batch
        if not hasattr(self,'raw_executor'):
            self.raw_executor=concurrent.futures.ThreadPoolExecutor(max_workers=4,thread_name_prefix='raw-sensor-writer')
        try:
            for sample in samples:
                data=sample['data']; cfg=sample['config']
                identity=(data.frame,data.timestamp)
                if self.pending_frame is not None and identity!=self.pending_frame:
                    raise RuntimeError('Raw sensor batch cannot mix frames or timestamps')
                if any(item['parent']==sample['parent'] and item['name']==cfg['name'] for item in items):
                    raise RuntimeError('Duplicate sensor in raw frame batch')
                self.pending_frame=identity
                directory=self.path/'sensors'/f"ego_{sample['parent']}"/cfg['name']
                if directory not in self.directories:
                    directory.mkdir(parents=True,exist_ok=True);self.directories.add(directory)
                started=time.perf_counter();payload=sensor_payload(sample)
                timings['raw_copy_ms']+=(time.perf_counter()-started)*1000
                suffix='.bin' if payload is not None else '.json'
                target=directory/(f'{data.frame:010d}'+suffix)
                if suffix=='.json':
                    value={'latitude':data.latitude,'longitude':data.longitude,'altitude':data.altitude} if sample['type'].endswith('gnss') else {
                        'accelerometer':[data.accelerometer.x,data.accelerometer.y,data.accelerometer.z],
                        'gyroscope':[data.gyroscope.x,data.gyroscope.y,data.gyroscope.z],'compass':data.compass}
                    payload=json.dumps(value,indent=2,allow_nan=False).encode()
                future=self.raw_executor.submit(write_sensor_payload,target,payload,suffix=='.json')
                pending.append(future)
                started=time.perf_counter()
                item=dict(sensor_metadata(sample),path=str(target.relative_to(self.path)),bytes=len(payload))
                timings['raw_metadata_ms']+=(time.perf_counter()-started)*1000
                if hasattr(data,'width'): item.update(width=data.width,height=data.height)
                items.append(item)
        except BaseException:
            concurrent.futures.wait(pending)
            raise
        return self.pending_batch

    def write(self,state,samples,prepared=None):
        if prepared is None:prepared=self.prepare(samples)
        if prepared is not self.pending_batch:raise RuntimeError('Raw sensor batch does not belong to this recording')
        pending,items,timings,payload_started=prepared
        # Preparation follows arrival order; the committed frame retains the
        # configured sensor order regardless of which GPU completed first.
        by_sensor={(item['parent'],item['name']):(item,future) for item,future in zip(items,pending)}
        keys=[(sample['parent'],sample['config']['name']) for sample in samples]
        if set(keys)!=set(by_sensor) or len(keys)!=len(items):raise RuntimeError('Raw sensor batch coverage mismatch')
        ordered=[by_sensor[key] for key in keys]
        record=dict(state);record['sensor_files']=[item for item,_ in ordered]
        try:
            # Keep sensor order deterministic regardless of completion order.
            for item,future in ordered:
                item['sha256'],disk_ms,hash_ms=future.result()
                timings['raw_disk_ms']+=disk_ms;timings['raw_hash_ms']+=hash_ms
        finally:
            # Never return with writes in flight, including after an error. The
            # queue is bounded to this one validated sensor frame; index commit
            # happens only after every payload and hash succeeds.
            concurrent.futures.wait(pending)
            self.pending_batch=None
        timings['raw_payload_wall_ms']=(time.perf_counter()-payload_started)*1000
        started=time.perf_counter()
        offset=self.states.tell()
        self.states.write((json.dumps(record,separators=(',',':'),allow_nan=False)+'\n').encode())
        self.states.flush();self.index.write(struct.pack('<Q',offset));self.index.flush()
        timings['raw_index_ms']=(time.perf_counter()-started)*1000
        self.last_write_timings=timings
        self.manifest['frames']+=1
        self.manifest.setdefault('first_frame',state['frame']);self.manifest.setdefault('start_sim_time',state['time'])
        self.manifest['last_frame']=state['frame'];self.manifest['end_sim_time']=state['time']

    def close(self,status='complete',error=None):
        if self.closed:return
        self.closed=True
        if self.pending_batch is not None:
            error=error or 'Uncommitted raw sensor frame';status='failed'
        if hasattr(self,'raw_executor'):self.raw_executor.shutdown(wait=True)
        self.pending_batch=None
        try:self.client.stop_recorder()
        except Exception as e:error=error or str(e);status='failed'
        try:self.manifest['ros_topics']=self.ros.stop_bag()
        except Exception as e:error=error or str(e);status='failed'
        bag_stats=getattr(self.ros,'last_bag_stats',None)
        if self.manifest['rosbag'] and isinstance(bag_stats,dict):self.manifest['bag_writer']=dict(bag_stats)
        self.states.close();self.index.close();self.events.close()
        self.manifest.update(status=status,ended=time.time(),error=error)
        dump(self.path/'manifest.json',self.manifest)
        seal(self.path)
        self.manifest['verification']=verify_session(self.path)
        dump(self.path/'manifest.json',self.manifest)
        return self.manifest


def read_frame(path,index):
    with (path/'frames.idx').open('rb') as f:
        f.seek(index*8); data=f.read(8)
    if len(data)!=8:raise ValueError('Frame index outside recording')
    with (path/'states.jsonl').open('rb') as f:
        f.seek(struct.unpack('<Q',data)[0]); return json.loads(f.readline())
