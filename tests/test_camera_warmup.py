import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import pytest
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
from controller import Controller

def owner():
    c=Controller.__new__(Controller)
    c.state={};c.stop_event=Event();c.tick=Mock()
    return c

def sensor(kind):
    return {'type':kind,'actor':SimpleNamespace(id=56)}

def test_camera_frames_warm_before_reporting_ready():
    c=owner();observed=[]
    c.tick.side_effect=lambda **kw:observed.append((c.state['camera_warmup']['stage'],kw))
    c.warm_sensor_views([sensor('sensor.camera.rgb'),sensor('sensor.other.imu')])
    assert observed==[('warming',{'publish':False})]*30
    assert c.state['camera_warmup']=={'stage':'ready','sensor_ids':[56],'completed':30,'total':30}
    assert c.state['gpu_operation']['stage']=='ready'

def test_non_camera_loadouts_only_need_delivery_check():
    c=owner();c.warm_sensor_views([sensor('sensor.lidar.ray_cast')])
    c.tick.assert_called_once_with(publish=False)
    assert 'camera_warmup' not in c.state

def test_failed_capture_is_never_marked_ready():
    c=owner();c.tick.side_effect=RuntimeError('worker unavailable')
    with pytest.raises(RuntimeError,match='worker unavailable'):
        c.warm_sensor_views([sensor('sensor.camera.rgb')])
    assert c.state['camera_warmup']['stage']=='failed'
    assert c.state['gpu_operation']['stage']=='failed'

def test_shutdown_interrupts_warmup():
    c=owner();c.stop_event.set()
    with pytest.raises(RuntimeError,match='cancelled'):
        c.warm_sensor_views([sensor('sensor.camera.rgb')])
    c.tick.assert_not_called()
