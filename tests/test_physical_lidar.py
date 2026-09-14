from types import SimpleNamespace
import numpy as np
import pytest
from physical_lidar import DTYPE, metadata, xyzi, ROS_FIELDS
from sensor_preview import encode_points, encode_preview


def sample():
    a=np.zeros(3,dtype=DTYPE)
    a['x']=[1,2,3];a['y']=[2,3,4];a['z']=[0,0,0];a['intensity']=[0,.5,1]
    a['channel']=[0,1,1];a['pulse_id']=[2**60+1,2**60+2,2**60+2];a['return_id']=[0,0,1];a['return_count']=[1,2,2]
    a['azimuth']=.2
    return SimpleNamespace(raw_data=a.tobytes(),channels=2,scan_start=10.,scan_end=10.05,pulse_count=2,
        flags=0,profile_crc=123,sequence=7,wavelength_nm=905,timestamp=10.05),a


def test_extended_schema_keeps_uint64_ids_and_metadata():
    data,a=sample();m=metadata(data)
    assert m['point_counts']==[1,2]
    assert m['point_stride']==64 and m['calibration_status']=='uncalibrated'
    np.testing.assert_array_equal(xyzi(data),np.array([[1,2,0,0],[2,3,0,.5],[3,4,0,1]]))
    assert int(np.frombuffer(data.raw_data,dtype=DTYPE)['pulse_id'][0])==2**60+1
    assert dict((n,o) for n,o,_ in ROS_FIELDS)['flags']==60
    assert len(data.raw_data)==192


def test_intensity_view_exposes_equal_height_material_differences():
    data,a=sample();before=data.raw_data
    height,_,_=encode_points('sensor.lidar.ray_cast',data,color='height')
    intensity,_,headers=encode_points('sensor.lidar.ray_cast',data,color='intensity')
    h=np.frombuffer(height,dtype='u1').reshape(-1,9)[:,6:]
    i=np.frombuffer(intensity,dtype='u1').reshape(-1,9)[:,6:]
    np.testing.assert_array_equal(h[0],h[2])
    assert not np.array_equal(i[0],i[2]) and headers['X-Preview-Color']=='intensity'
    assert data.raw_data==before
    payload,mime,_=encode_preview('sensor.lidar.ray_cast',data,color='intensity')
    assert mime=='image/jpeg' and len(payload)>100


def test_malformed_channel_rejected():
    data,a=sample();a['channel'][1]=5;data.raw_data=a.tobytes()
    with pytest.raises(ValueError,match='channel'):metadata(data)


def test_ros_extended_preserves_fields_and_converts_axes():
    from rosio import sensor_message
    data,a=sample()
    msg,kind=sensor_message({'data':data,'type':'sensor.lidar.ray_cast'},'roof')
    result=np.frombuffer(msg.data,dtype=DTYPE)
    np.testing.assert_array_equal(result['pulse_id'],a['pulse_id'])
    np.testing.assert_array_equal(result['y'],-a['y'])
    np.testing.assert_array_equal(result['azimuth'],-a['azimuth'])
    assert msg.point_step==64 and msg.row_step==192 and len(msg.fields)==18
    assert msg.header.stamp.sec==10 and msg.header.stamp.nanosec==50000000
    assert kind=='sensor_msgs/msg/PointCloud2'
