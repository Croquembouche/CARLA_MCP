"""Standard ROS Image decoding is the oracle for the direct CDR path."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import pytest
from builtin_interfaces.msg import Time
from std_msgs.msg import Header
from sensor_msgs.msg import Image
from rclpy.serialization import deserialize_message,serialize_message
from _bag_native import serialize_image


@pytest.mark.parametrize('frame',['','x','xy','xyz','ego_1/front_optical','camera_\u03b1'])
@pytest.mark.parametrize('encoding,bpp',[('bgra8',4),('32FC2',8),('mono8',1)])
def test_direct_image_decodes_like_standard_ros(frame,encoding,bpp):
    # Odd widths and row padding exercise CDR alignment independently of pixels.
    height,width,step=3,7,7*bpp+3
    raw=bytes((i*31)%256 for i in range(height*step))
    for sec,nsec,endian in [(-1,999999999,0),(2147483647,0,1),(0,1,0)]:
        original=Image(header=Header(stamp=Time(sec=sec,nanosec=nsec),frame_id=frame),
            height=height,width=width,encoding=encoding,is_bigendian=endian,step=step,data=raw)
        actual=serialize_image(sec,nsec,frame,height,width,encoding,endian,step,raw)
        assert deserialize_message(actual,Image)==deserialize_message(serialize_message(original),Image)
        assert bytes(deserialize_message(actual,Image).data)==raw


def test_direct_image_empty_payload_and_invalid_lengths():
    raw=serialize_image(0,0,'',0,0,'bgra8',0,0,b'')
    assert deserialize_message(raw,Image)==Image(encoding='bgra8')
    for args in [(0,1000000000,'',0,0,'bgra8',0,0,b''),
                 (0,0,'',1,1,'bgra8',0,4,b'bad'),
                 (0,0,'',1,1,'bgra8',2,4,b'abcd'),
                 (0,0,'bad\0frame',1,1,'bgra8',0,4,b'abcd')]:
        with pytest.raises(ValueError):serialize_image(*args)


@pytest.mark.parametrize('kind,bpp',[('sensor.camera.rgb',4),('sensor.camera.optical_flow',8)])
def test_frame_fast_path_and_optional_fallback_have_identical_messages(monkeypatch,kind,bpp):
    from types import SimpleNamespace
    import carla,rosio
    sample={'type':kind,'parent':7,'config':{'name':'front','attributes':{'fov':'90'}},
        'pose':{},'mount':carla.Transform(),
        'data':SimpleNamespace(frame=42,timestamp=1.25,width=7,height=3,fov=90.,raw_data=bytes(range(7*3*bpp)))}
    def frame_messages(native):
        monkeypatch.setattr(rosio,'_serialize_image',native)
        io=rosio.RosIO.__new__(rosio.RosIO);messages=[]
        io.emit=lambda topic,message,typename,timestamp:messages.append((topic,message,typename,timestamp))
        io.emit_serialized=lambda topic,payload,typename,timestamp,message_type:messages.append(
            (topic,deserialize_message(payload,message_type),typename,timestamp))
        io.frame(1.25,[],[sample])
        return messages
    assert frame_messages(serialize_image)==frame_messages(None)
