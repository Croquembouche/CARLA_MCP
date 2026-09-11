import json
import hashlib
from verification import seal, verify_session
import struct
import time
from pathlib import Path
from uuid import uuid4


def dump(path, value):
    target=Path(path); temp=target.with_suffix(target.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)); temp.replace(target)


def sensor_metadata(sample):
    data=sample['data']
    result={'type':sample['type'],'name':sample['config']['name'],'parent':sample['parent'],
            'frame':data.frame,'timestamp':data.timestamp,'transform':sample['pose'],
            'attributes':sample['config']['attributes'],'mount':sample['config'].get('mount',{})}
    if hasattr(data,'width'):result.update(width=data.width,height=data.height,fov=data.fov)
    if hasattr(data,'channels'):
        result.update(channels=data.channels,horizontal_angle=data.horizontal_angle,
                      point_counts=[data.get_point_count(i) for i in range(data.channels)])
    if hasattr(data,'compass'):result['compass']=data.compass
    return result


class Recording:
    def __init__(self, root, client, ros, config, map_data, opendrive, bag):
        self.path=root/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6])
        self.path.mkdir(parents=True)
        self.ros=ros; self.client=client; self.closed=False
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

    def write(self,state,samples):
        record=dict(state); record['sensor_files']=[]
        for sample in samples:
            data=sample['data']; cfg=sample['config']; directory=self.path/'sensors'/f"ego_{sample['parent']}"/cfg['name']
            directory.mkdir(parents=True,exist_ok=True)
            suffix='.bin' if hasattr(data,'raw_data') else '.json'
            target=directory/(f'{data.frame:010d}'+suffix)
            if suffix=='.bin':
                payload=bytes(data.raw_data);target.write_bytes(payload)
            else:
                value={'latitude':data.latitude,'longitude':data.longitude,'altitude':data.altitude} if sample['type'].endswith('gnss') else {
                    'accelerometer':[data.accelerometer.x,data.accelerometer.y,data.accelerometer.z],
                    'gyroscope':[data.gyroscope.x,data.gyroscope.y,data.gyroscope.z],'compass':data.compass}
                dump(target,value)
            item=dict(sensor_metadata(sample),path=str(target.relative_to(self.path)),bytes=target.stat().st_size,sha256=hashlib.sha256(payload if suffix=='.bin' else target.read_bytes()).hexdigest())
            if hasattr(data,'width'): item.update(width=data.width,height=data.height)
            record['sensor_files'].append(item)
        offset=self.states.tell()
        self.states.write((json.dumps(record,separators=(',',':'),allow_nan=False)+'\n').encode())
        self.states.flush();self.index.write(struct.pack('<Q',offset));self.index.flush()
        self.manifest['frames']+=1
        self.manifest.setdefault('first_frame',state['frame']);self.manifest.setdefault('start_sim_time',state['time'])
        self.manifest['last_frame']=state['frame'];self.manifest['end_sim_time']=state['time']

    def close(self,status='complete',error=None):
        if self.closed:return
        self.closed=True
        try:self.client.stop_recorder()
        except Exception as e:error=error or str(e);status='failed'
        try:self.manifest['ros_topics']=self.ros.stop_bag()
        except Exception as e:error=error or str(e);status='failed'
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
