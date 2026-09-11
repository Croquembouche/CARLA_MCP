import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,carla,pytest
from unittest.mock import Mock
from sensor_loadouts import DEFAULT_SENSORS,default_ego_loadout,spawn_loadout

EXPECTED={'front_rgb','roof_lidar','imu','gnss','front_radar','cabin_overview'}

def test_default_contains_all_six_and_keeps_center_console_camera():
    sensors=default_ego_loadout('vehicle.lincoln.mkz_interior')
    assert len(sensors)==6 and {s['name'] for s in sensors}==EXPECTED
    assert len({s['type'] for s in sensors})==5
    cabin=next(s for s in sensors if s['name']=='cabin_overview')
    assert cabin['mount']==dict(x=.55,y=0,z=1.2,yaw=180,pitch=-8,roll=0)
    sensors[0]['mount']['x']=999
    assert DEFAULT_SENSORS[0]['mount']['x']==1.5

@pytest.mark.parametrize('role',['background','pedestrian'])
def test_other_roles_remain_sensor_free(role):
    assert spawn_loadout({'role':role,'model':'vehicle.test'})==[]

@pytest.mark.parametrize('loadout',[[],[{'name':'custom','type':'sensor.other.imu','mount':{},'attributes':{}}]])
def test_explicit_loadouts_are_preserved(loadout):
    assert spawn_loadout({'role':'ego','model':'vehicle.test','sensors':loadout})==loadout

def test_ambulance_retains_its_specific_cabin_mount():
    sensors=default_ego_loadout('vehicle.ambulance.ford')
    assert len(sensors)==6 and sensors[-1]['mount']['x']==1.6
    assert sensors[-1]['attributes']['post_process_profile']=='AmbulanceCabinObservation'

@pytest.mark.parametrize('explicit',[False,True])
def test_spawn_passes_default_or_explicit_loadout_to_sensor_configuration(explicit):
    from controller import Controller
    c=Controller.__new__(Controller);c.managed={};c.state={'managed':{'50':{'role':'ego'}}}
    c.world=Mock();bp=Mock();bp.id='vehicle.lincoln.mkz_interior';c.world.get_blueprint_library.return_value.find.return_value=bp
    actor=Mock();actor.id=50;actor.type_id=bp.id;c.world.try_spawn_actor.return_value=actor
    c.waypoint=Mock(return_value=Mock(transform=carla.Transform()));c.validate_blueprints=Mock();c.configure_sensors=Mock();c.tick=Mock();c.refresh=Mock();c.tm=Mock()
    payload=dict(role='ego',model=bp.id,planner='tm',spawn={'x':0,'y':0,'z':0})
    if explicit:payload['sensors']=[]
    assert c.spawn(payload)['id']==50
    configs=c.configure_sensors.call_args.args[1]
    assert configs==[] if explicit else {s['name'] for s in configs}==EXPECTED
