"""Optical defaults are persisted while explicit legacy/RT opt-outs survive."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controller import validate_loadout
from sensor_loadouts import default_ego_loadout

def sensor(kind,attrs=None):
    return dict(name='test_sensor',type=kind,mount={},attributes=attrs or {})

def test_lidar_default_and_legacy_override():
    assert validate_loadout([sensor('sensor.lidar.ray_cast')])[0]['attributes']['material_model']=='true'
    assert validate_loadout([sensor('sensor.lidar.ray_cast',{'material_model':'false'})])[0]['attributes']['material_model']=='false'
    assert 'material_model' not in validate_loadout([sensor('sensor.lidar.ray_cast_semantic')])[0]['attributes']

def test_rgb_reflections_default_and_explicit_opt_out():
    assert validate_loadout([sensor('sensor.camera.rgb')])[0]['attributes']['use_ray_tracing']=='true'
    assert validate_loadout([sensor('sensor.camera.rgb',{'use_ray_tracing':'false'})])[0]['attributes']['use_ray_tracing']=='false'
    cabin=next(s for s in default_ego_loadout('vehicle.lincoln.mkz') if s['name']=='cabin_overview')
    assert cabin['attributes']['use_ray_tracing']=='true'
