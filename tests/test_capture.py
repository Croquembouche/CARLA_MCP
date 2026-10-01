import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import json
import struct
from types import SimpleNamespace
import numpy as np
import pytest
import carla
from controller import validate_loadout
from rosio import sensor_message, quaternion
from recording import Recording, read_frame


def test_loadout_rejects_duplicate_names_and_resource_overflow():
    c={'name':'front','type':'sensor.camera.rgb','attributes':{},'mount':{}}
    with pytest.raises(ValueError):validate_loadout([c,c])
    with pytest.raises(ValueError):validate_loadout([{**c,'attributes':{'image_size_x':9000}}])
    assert validate_loadout([c])[0]['attributes']['sensor_tick']=='0.0'


def test_lidar_ros_handedness_preserves_intensity():
    raw=np.array([[1,2,3,.75]],dtype='<f4').tobytes()
    msg,kind=sensor_message({'type':'sensor.lidar.ray_cast','data':SimpleNamespace(timestamp=1.25,raw_data=raw)},'ego_1/lidar')
    assert kind=='sensor_msgs/msg/PointCloud2'
    assert list(np.frombuffer(bytes(msg.data),dtype='<f4'))==[1,-2,3,.75]
    assert msg.header.stamp.nanosec==250000000


def test_semantic_ids_stay_uint32():
    raw=struct.pack('<ffffII',1,2,3,.5,4294967294,17)
    msg,_=sensor_message({'type':'sensor.lidar.ray_cast_semantic','data':SimpleNamespace(timestamp=0.,raw_data=raw)},'ego_1/semantic')
    assert struct.unpack('<ffffII',bytes(msg.data))==(1,-2,3,.5,4294967294,17)


def test_ros_yaw_conversion():
    q=quaternion(carla.Transform(rotation=carla.Rotation(yaw=90)))
    from scipy.spatial.transform import Rotation
    assert Rotation.from_quat(q).as_euler('xyz',degrees=True)[2]==pytest.approx(-90,abs=1e-5)


@pytest.mark.parametrize('external_storage',[False,True])
def test_recording_exact_bytes_and_index(tmp_path,monkeypatch,external_storage):
    if external_storage:monkeypatch.setenv('CARLA_RECORDING_STORAGE',str(tmp_path/'fast'))
    else:monkeypatch.delenv('CARLA_RECORDING_STORAGE',raising=False)
    class Client:
        def start_recorder(self,*args):return 'Recording started'
        def stop_recorder(self):pass
    class Ros:
        def stop_bag(self):return {}
    rec=Recording(tmp_path,Client(),Ros(),{}, {'name':'test'},'opendrive',False)
    raw=b'\0\xffexact\0bytes'
    sample={'data':SimpleNamespace(raw_data=raw,frame=31,timestamp=1.55),'type':'sensor.lidar.ray_cast','parent':1,'config':{'name':'lidar','attributes':{}},'pose':{}}
    rec.write({'frame':31,'time':1.55,'actors':[]},[sample])
    manifest=rec.close()
    assert rec.path.is_symlink() == external_storage
    assert manifest['frames']==1 and manifest['status']=='complete'
    frame=read_frame(rec.path,0)
    assert (rec.path/frame['sensor_files'][0]['path']).read_bytes()==raw
    with pytest.raises(ValueError):read_frame(rec.path,1)


def test_json_recording_hash_and_size_match_written_bytes(tmp_path,monkeypatch):
    from unittest.mock import Mock
    import hashlib
    monkeypatch.delenv('CARLA_RECORDING_STORAGE',raising=False)
    client=Mock();client.start_recorder.return_value='Recording started'
    ros=Mock();ros.stop_bag.return_value={}
    rec=Recording(tmp_path,client,ros,{}, {'name':'test'},'opendrive',False)
    sample={'data':SimpleNamespace(latitude=12.,longitude=34.,altitude=56.,frame=1,timestamp=.1),'type':'sensor.other.gnss','parent':1,'config':{'name':'gnss','attributes':{}},'pose':{}}
    rec.write({'frame':1,'time':.1,'actors':[]},[sample]);rec.close()
    item=read_frame(rec.path,0)['sensor_files'][0]
    payload=(rec.path/item['path']).read_bytes()
    assert item['bytes']==len(payload) and item['sha256']==hashlib.sha256(payload).hexdigest()
    assert json.loads(payload)=={'latitude':12.,'longitude':34.,'altitude':56.}


def test_parallel_raw_writes_commit_in_order_and_reject_failed_frame(tmp_path,monkeypatch):
    import recording
    import threading
    from unittest.mock import Mock
    monkeypatch.delenv('CARLA_RECORDING_STORAGE',raising=False)
    client=Mock();client.start_recorder.return_value='Recording started'
    ros=Mock();ros.stop_bag.return_value={}
    rec=Recording(tmp_path,client,ros,{}, {'name':'test'},'opendrive',False)
    samples=[{'data':SimpleNamespace(raw_data=bytes([i])*4096,frame=31,timestamp=1.55),
        'type':'sensor.lidar.ray_cast','parent':1,'config':{'name':f'lidar{i}','attributes':{}},'pose':{}} for i in range(2)]
    original=recording.write_sensor_payload
    barrier=threading.Barrier(2)
    def overlapping(target,payload,atomic):
        barrier.wait(timeout=5)
        return original(target,payload,atomic)
    monkeypatch.setattr(recording,'write_sensor_payload',overlapping)
    rec.write({'frame':31,'time':1.55,'actors':[]},samples)
    assert [x['name'] for x in read_frame(rec.path,0)['sensor_files']]==['lidar0','lidar1']
    finished=threading.Event()
    def failing(target,payload,atomic):
        if target.parent.name=='lidar0':raise OSError('injected disk failure')
        original(target,payload,atomic);finished.set()
        return 'unused',0.,0.
    monkeypatch.setattr(recording,'write_sensor_payload',failing)
    for sample in samples:sample['data'].frame=32
    with pytest.raises(OSError,match='injected disk failure'):
        rec.write({'frame':32,'time':1.65,'actors':[]},samples)
    assert finished.is_set()  # failure drains other tasks before returning
    assert rec.manifest['frames']==1 and (rec.path/'frames.idx').stat().st_size==8
    rec.close('failed','injected disk failure')


def test_raw_prepare_is_bounded_and_close_rejects_uncommitted_frame(tmp_path,monkeypatch):
    from unittest.mock import Mock
    monkeypatch.delenv('CARLA_RECORDING_STORAGE',raising=False)
    client=Mock();client.start_recorder.return_value='Recording started'
    ros=Mock();ros.stop_bag.return_value={}
    rec=Recording(tmp_path,client,ros,{}, {'name':'test'},'opendrive',False)
    sample={'data':SimpleNamespace(raw_data=b'complete',frame=1,timestamp=.1),
        'type':'sensor.lidar.ray_cast','parent':1,'config':{'name':'lidar','attributes':{}},'pose':{}}
    batch=rec.prepare([sample])
    assert rec.manifest['frames']==0 and (rec.path/'frames.idx').stat().st_size==0
    with pytest.raises(RuntimeError,match='not committed'):rec.prepare([sample])
    manifest=rec.close()
    assert manifest['status']=='failed' and manifest['error']=='Uncommitted raw sensor frame'
    assert batch[0][0].done()


def test_native_payload_is_read_once_for_recording_metadata_and_ros(tmp_path):
    from recording import sensor_payload,sensor_metadata
    from unittest.mock import Mock
    class Camera:
        frame=1;timestamp=.1;width=2;height=1;fov=90
        reads=0
        storage=bytearray(range(8))
        @property
        def raw_data(self):
            self.reads+=1
            return memoryview(self.storage)
    data=Camera()
    sample={'data':data,'type':'sensor.camera.rgb','parent':1,'config':{'name':'camera','attributes':{}},'pose':{}}
    client=Mock();client.start_recorder.return_value='Recording started'
    ros=Mock();ros.stop_bag.return_value={}
    rec=Recording(tmp_path,client,ros,{}, {'name':'test'},'opendrive',False)
    batch=rec.prepare([sample])
    payload=sensor_payload(sample)
    data.storage[:]=b'changed!'
    msg,_=sensor_message(sample,'ego_1/camera')
    sensor_metadata(sample)
    assert data.reads==1 and bytes(msg.data)==payload==bytes(range(8))
    rec.write({'frame':1,'time':.1,'actors':[]},[sample],prepared=batch)
    rec.close()
    item=read_frame(rec.path,0)['sensor_files'][0]
    assert (rec.path/item['path']).read_bytes()==payload
    data.frame=2;data.timestamp=.2
    assert sensor_payload(sample)==b'changed!' and data.reads==2
    # Replacing the native object also invalidates the memo, even at one timestamp.
    other=Camera();sample['data']=other
    assert sensor_payload(sample)==b'changed!' and other.reads==1


def test_incremental_raw_batch_overlaps_arrivals_but_commits_in_configured_order(tmp_path,monkeypatch):
    import recording,threading
    from unittest.mock import Mock
    monkeypatch.delenv('CARLA_RECORDING_STORAGE',raising=False)
    client=Mock();client.start_recorder.return_value='Recording started'
    ros=Mock();ros.stop_bag.return_value={}
    rec=Recording(tmp_path,client,ros,{}, {'name':'test'},'opendrive',False)
    samples=[{'data':SimpleNamespace(raw_data=bytes([i])*4096,frame=7,timestamp=.7),
        'type':'sensor.lidar.ray_cast','parent':1,'config':{'name':f'lidar{i}','attributes':{}},'pose':{}} for i in range(2)]
    original=recording.write_sensor_payload;started=threading.Event();release=threading.Event()
    def delayed(target,payload,atomic):
        if target.parent.name=='lidar1':
            started.set();assert release.wait(timeout=2)
        return original(target,payload,atomic)
    monkeypatch.setattr(recording,'write_sensor_payload',delayed)
    try:
        batch=rec.prepare([samples[1]])
        assert started.wait(timeout=2)  # write begins before the other sensor arrives
        assert rec.prepare([samples[0]],prepared=batch) is batch
        assert rec.manifest['frames']==0
    finally:release.set()
    with pytest.raises(RuntimeError,match='Duplicate'):rec.prepare([samples[0]],prepared=batch)
    rec.write({'frame':7,'time':.7,'actors':[]},samples,prepared=batch)
    assert [x['name'] for x in read_frame(rec.path,0)['sensor_files']]==['lidar0','lidar1']
    assert rec.close()['status']=='complete'


def test_incremental_raw_batch_rejects_mixed_frames(tmp_path,monkeypatch):
    from unittest.mock import Mock
    monkeypatch.delenv('CARLA_RECORDING_STORAGE',raising=False)
    client=Mock();client.start_recorder.return_value='Recording started'
    ros=Mock();ros.stop_bag.return_value={}
    rec=Recording(tmp_path,client,ros,{}, {'name':'test'},'opendrive',False)
    def s(frame):return {'data':SimpleNamespace(raw_data=b'x',frame=frame,timestamp=frame*.1),
        'type':'sensor.lidar.ray_cast','parent':1,'config':{'name':f'lidar{frame}','attributes':{}},'pose':{}}
    batch=rec.prepare([s(1)])
    with pytest.raises(RuntimeError,match='cannot mix'):rec.prepare([s(2)],prepared=batch)
    assert rec.manifest['frames']==0
    assert rec.close()['status']=='failed'
