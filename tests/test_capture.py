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


def test_recording_exact_bytes_and_index(tmp_path):
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
    assert manifest['frames']==1 and manifest['status']=='complete'
    frame=read_frame(rec.path,0)
    assert (rec.path/frame['sensor_files'][0]['path']).read_bytes()==raw
    with pytest.raises(ValueError):read_frame(rec.path,1)
