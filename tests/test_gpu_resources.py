import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gpu_resources import desired_workers, sensor_cost, loadout_key, summary

def camera(w=640,h=360):return {'type':'sensor.camera.rgb','attributes':{'image_size_x':str(w),'image_size_y':str(h)}}
LIDAR={'type':'sensor.lidar.ray_cast','attributes':{'points_per_second':'200000'}}
RADAR={'type':'sensor.other.radar','attributes':{'points_per_second':'10000'}}

def test_no_gpu_sensors_release_every_worker_even_manual_policy():
 for mode in ('auto','1','2','3','4'):
  assert desired_workers([],mode)==0
  assert desired_workers([{'type':'sensor.other.imu'},{'type':'sensor.other.gnss'}],mode)==0

def test_cost_policy_preserves_parallelism_without_idle_workers():
 assert desired_workers([camera(),LIDAR,RADAR])==2
 assert desired_workers([camera(1920,1080)],'4')==1
 assert desired_workers([camera()]*8)==4
 assert sensor_cost(camera(1280,720))==4*sensor_cost(camera())

def test_measured_count_overrides_estimate_and_caps_to_available_work():
 assert desired_workers([camera(),LIDAR,RADAR],'auto',1)==1
 assert desired_workers([camera(),LIDAR,RADAR],'auto',10)==3
 assert desired_workers([camera(),LIDAR,RADAR],'2',1)==2

def test_cache_changes_with_loadout_not_order():
 assert loadout_key([camera(),LIDAR])==loadout_key([LIDAR,camera()])
 assert loadout_key([camera()])!=loadout_key([camera(1280,720)])

def test_p95_and_mean_measurements():
 result=summary([{'total_ms':x} for x in range(1,101)])['total_ms']
 assert result=={'mean':50.5,'p95':95}

def test_external_server_rejected_before_touching_sensor_loadout():
 from gpu_resources import GpuResources
 from unittest.mock import Mock
 import pytest
 c=GpuResources();c.worker_manifest=None;c.current_loadouts=Mock()
 with pytest.raises(ValueError,match='started by this interface'):c.apply_gpu_profile('auto')
 with pytest.raises(ValueError,match='started by this interface'):c.benchmark_gpu_profile()
 c.current_loadouts.assert_not_called()

def test_shutdown_does_not_start_rollback_workers():
 from gpu_resources import GpuResources
 from unittest.mock import Mock
 import pytest
 c=GpuResources();c.current_loadouts=Mock(return_value={});c.state={'worker_count':1};c.stop_event=Mock();c.stop_event.is_set.return_value=True
 c.drop_sensor_streams=Mock();c.resize_pool=Mock(side_effect=RuntimeError('shutdown'))
 with pytest.raises(RuntimeError,match='shutdown'):c.reallocate_sensors({},2)
 c.drop_sensor_streams.assert_called_once();c.resize_pool.assert_called_once_with(2)
 assert c.resizing_workers is False

def test_manifest_transient_replace_gap_is_retried():
 from gpu_resources import read_manifest
 from unittest.mock import Mock,patch
 p=Mock();p.read_text.side_effect=[FileNotFoundError(),'{', '{"ready":true}']
 with patch('gpu_resources.time.sleep'):
  assert read_manifest(p)=={'ready':True}
 assert p.read_text.call_count==3
