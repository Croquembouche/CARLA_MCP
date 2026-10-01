"""Prepared sensor values preserve wire data and never publish partial frames."""
import sys,struct
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import pytest
from rclpy.serialization import deserialize_message
from rosio import prepare_sensor,sensor_message,RosIO


def lidar(frame=7,timestamp=.7,x=1.):
    return {'type':'sensor.lidar.ray_cast','parent':3,'config':{'name':'lidar'},
        'data':SimpleNamespace(frame=frame,timestamp=timestamp,raw_data=struct.pack('<ffff',x,2.,3.,.5))}


def test_preparation_reuses_same_capture_and_invalidates_new_identity_frame_time_name_and_mode():
    sample=lidar();name='ego_3/lidar'
    original=prepare_sensor(sample,name,True)
    assert prepare_sensor(sample,name,True) is original
    reference,_=sensor_message(sample,name)
    assert deserialize_message(original.value,original.message_type)==reference
    renamed=prepare_sensor(sample,'ego_3/renamed',True)
    assert renamed is not original and renamed.sample_header.frame_id=='ego_3/renamed'
    plain=prepare_sensor(sample,name,False)
    assert not plain.serialized and plain.value==reference
    sample['data']=lidar(x=9.)['data']  # Same frame/time, new immutable object
    replacement=prepare_sensor(sample,name,True)
    assert replacement.value!=original.value
    sample['data'].frame=8;sample['data'].raw_data=lidar(x=4.)['data'].raw_data
    next_frame=prepare_sensor(sample,name,True)
    assert next_frame.value!=replacement.value
    sample['data'].timestamp=.8
    next_time=prepare_sensor(sample,name,True)
    assert next_time.sample_header.stamp.nanosec==800000000
    assert next_time is not next_frame


@pytest.mark.parametrize('recording',[False,True])
def test_prepare_sample_does_not_publish_or_enqueue_bag_data(recording):
    io=RosIO.__new__(RosIO);io.writer=object() if recording else None
    def unexpected(*args):raise AssertionError('Preparation must not publish or enqueue')
    io.emit=unexpected;io.emit_serialized=unexpected
    value=io.prepare_sample(lidar())
    assert value.serialized is recording
    assert value.typename=='sensor_msgs/msg/PointCloud2'
