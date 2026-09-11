import sys,json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,carla
from scene_vehicles import SceneVehicles,discover,model_for
from controller import Controller

def environment(name,id,x=0,size=(2,1,1)):
    b=carla.BoundingBox(carla.Location(x=x,z=1),carla.Vector3D(*size))
    return NS(name=name,id=id,bounding_box=b)

def owner(objects=()):
    c=Mock();c.world.get_environment_objects.side_effect=lambda label:list(objects) if label==carla.CityObjectLabel.Car else []
    c.world.get_actors.return_value.filter.return_value=[]
    c.world.get_map.return_value.get_spawn_points.return_value=[]
    c.world.get_blueprint_library.return_value.filter.return_value=[NS(id='vehicle.lincoln.mkz')]
    c.map_data={'parking_spaces':[]};c.worker_manifest=None;c.tm_port=8005;c.managed={};c.parking_static=[]
    c.scene_vehicles=SceneVehicles(c);return c

def test_body_and_glass_form_one_vehicle_and_uint64_ids_stay_exact():
    c=owner([environment('BP_Test_SM_0',2**63+91),environment('BP_Test_SM_1',2**63+92,size=(1,.8,.4))])
    assert len(c.scene_vehicles.sources)==1
    s=c.scene_vehicles.sources[0];assert len(s['ids'])==2 and s['length']==4
    c.scene_vehicles.hidden.add(s['key'])
    assert c.scene_vehicles.snapshot()['hidden'][0]['ids']==[str(2**63+91),str(2**63+92)]

def test_distinct_instances_are_not_merged():
    c=owner([environment('Foliage_Inst_0_0',1),environment('Foliage_Inst_0_1',2,x=10)])
    assert len(c.scene_vehicles.sources)==2

def test_multiple_vehicles_in_one_scenery_actor_roll_back_together():
    c=owner([environment('Lot_SM_0',1),environment('Lot_SM_1',2,x=10)])
    assert len(c.scene_vehicles.sources)==1 and c.scene_vehicles.snapshot()['total']==2
    a=Mock(id=75);a.bounding_box=carla.BoundingBox(carla.Location(z=.5),carla.Vector3D(2,1,.8))
    c.world.try_spawn_actor.side_effect=[a,None]
    r=c.scene_vehicles.convert()
    assert r['remaining']==2 and not r['created'] and not c.managed
    a.destroy.assert_called_once()
    assert c.world.enable_environment_objects.call_args.args==({1,2},True)

def test_missing_legacy_model_is_explicitly_substituted_with_same_vehicle_class():
    assert model_for({'key':'BP_TeslaM3_Parked_C_1','label':'Car'},{'vehicle.lincoln.mkz'})==('vehicle.lincoln.mkz',True)
    assert model_for({'key':'BP_LincolnMKZ_Parked_C_1','label':'Car'},{'vehicle.lincoln.mkz'})==('vehicle.lincoln.mkz',False)
    assert model_for({'key':'unknown','label':'Bus'},{'vehicle.lincoln.mkz'})==(None,True)

def test_failed_spawn_restores_scenery_and_reports_failure():
    c=owner([environment('BP_Test_SM_0',1)]);c.world.try_spawn_actor.return_value=None
    r=c.scene_vehicles.convert()
    assert not r['created'] and r['remaining']==1 and r['failures']
    assert c.world.enable_environment_objects.call_args_list[0].args==({1},False)
    assert c.world.enable_environment_objects.call_args_list[1].args==({1},True)
    assert not c.managed

def test_conversion_sleeps_physics_keeps_collision_actor_and_is_idempotent():
    c=owner([environment('BP_Test_SM_0',1)]);a=Mock(id=75);a.bounding_box=carla.BoundingBox(carla.Location(z=.5),carla.Vector3D(2,1,.8));c.world.try_spawn_actor.return_value=a
    r=c.scene_vehicles.convert();assert r['created']==[75] and r['remaining']==0
    a.set_autopilot.assert_called_with(False,8005);a.set_simulate_physics.assert_called_with(False)
    assert a.apply_control.call_args.args[0].hand_brake
    assert c.managed[75]['scene_source']=='BP_Test' and c.managed[75]['model_substituted']
    assert c.scene_vehicles.convert()['created']==[]
    assert c.world.try_spawn_actor.call_count==1

def test_road_release_rejects_occupied_point_without_moving_vehicle():
    c=owner();a=Mock();c.managed={5:{'actor':a,'parked':True}};c.waypoint.return_value.transform=carla.Transform();c.world.try_spawn_actor.return_value=None
    with pytest.raises(ValueError,match='occupied'):c.scene_vehicles.release_to_road(5,dict(x=0,y=0))
    a.set_transform.assert_not_called()

def test_recovery_restores_hidden_set_and_removed_scenery_stays_removed():
    c=owner([environment('BP_Test_SM_0',1)]);c.scene_vehicles.restore({'hidden':['BP_Test']})
    assert c.scene_vehicles.hidden=={'BP_Test'}
    assert c.scene_vehicles.convert()['created']==[]

def test_cleaned_map_accepts_old_hidden_keys_but_rejects_unrelated_missing_sources():
    c=owner([environment('BP_Test_SM_0',1)])
    c.scene_vehicles.removed=[{'source':'DeletedCar','pose':dict(key='DeletedCar',x=5,y=0,z=1,yaw=0,length=4,width=2,height=2)}]
    c.scene_vehicles.restore({'hidden':['BP_Test','DeletedCar']})
    assert c.scene_vehicles.hidden=={'BP_Test'}
    assert c.scene_vehicles.was_removed('DeletedCar:0')
    assert not c.scene_vehicles.was_removed(None)
    assert c.scene_vehicles.snapshot()['removed'][0]['key']=='DeletedCar'
    with pytest.raises(ValueError,match='UnknownCar'):
        c.scene_vehicles.restore({'hidden':['UnknownCar']})

def test_old_configuration_does_not_respawn_permanently_deleted_vehicles(monkeypatch):
    import controller
    c=Mock();c.managed={};c.state={'map':'Carla/Maps/Town10HD_Opt'}
    c.scene_vehicles.was_removed.side_effect=lambda source:source=='DeletedCar'
    def restored_spawn(payload):
        aid=len(c.managed)+1;c.managed[aid]={'role':payload['role'],'planner':'external'};return {'id':aid}
    c.spawn.side_effect=restored_spawn
    config={'map':c.state['map'],'scene_vehicles':{'hidden':['DeletedCar']},'weather':{},'actors':[
        {'id':1,'scene_source':'DeletedCar','role':'background'},
        {'id':2,'scene_source':'RetainedCar','role':'background'},
        {'id':3,'role':'ego'}]}
    monkeypatch.setattr(controller.reliability,'checkpoint',Mock())
    Controller.restore_configuration(c,config)
    assert c.spawn.call_count==2
    assert c.spawn.call_args_list[0].args[0]['scene_source']=='RetainedCar'
    assert c.spawn.call_args_list[1].args[0]['role']=='ego'

def test_late_gpu_worker_receives_visibility_using_its_own_ids(tmp_path,monkeypatch):
    c=owner([environment('BP_Test_SM_0',1)]);c.scene_vehicles.visibility({'BP_Test'},False)
    path=tmp_path/'workers.json';worker={'role':'gpu-3','pid':123,'initialized':True,'command':['sim','-carla-rpc-port=2010']};path.write_text(json.dumps({'children':[worker]}));c.worker_manifest=path
    sync=Mock();monkeypatch.setattr(c.scene_vehicles,'sync_worker',sync)
    c.scene_vehicles.sync_workers();assert sync.call_args.args==(2010,{'BP_Test_SM_0'},{'BP_Test_SM_0'})
    c.scene_vehicles.sync_workers();assert sync.call_count==1
    worker['pid']=124;path.write_text(json.dumps({'children':[worker]}));c.scene_vehicles.sync_workers();assert sync.call_count==2


def test_reenabling_scenery_restores_parking_occupancy_sources():
    c=owner([environment('BP_Test_SM_0',1)]);c.scene_vehicles.original_parking_static=[{'name':'BP_Test_SM_0'}]
    c.scene_vehicles.visibility({'BP_Test'},False);assert not c.parking_static
    c.scene_vehicles.restore({});assert c.parking_static==[{'name':'BP_Test_SM_0'}]

@pytest.mark.parametrize('role',['background','pedestrian','ego'])
def test_remove_cleans_actor_controllers_and_sensor_resources(role):
    c=Controller.__new__(Controller);a=Mock();sensor=Mock();walker=Mock() if role=='pedestrian' else None
    c.managed={7:{'actor':a,'role':role,'controller':walker}};c.sensors={8:{'actor':sensor,'parent':7,'config':{'name':'rgb'}}} if role=='ego' else {};c.previews={8:object()} if role=='ego' else {};c.ros=Mock()
    c.delete(7);a.destroy.assert_called_once();assert not c.managed and not c.sensors and not c.previews
    if walker:walker.stop.assert_called_once();walker.destroy.assert_called_once()
    if role=='ego':sensor.stop.assert_called_once();sensor.destroy.assert_called_once()

def test_failed_native_removal_does_not_claim_actor_is_gone():
    c=Controller.__new__(Controller);a=Mock();a.destroy.return_value=False;c.managed={7:{'actor':a,'controller':None}};c.sensors={};c.ros=None
    with pytest.raises(RuntimeError,match='did not remove'):c.delete(7)
    assert 7 in c.managed


def test_saved_parked_scene_pose_can_restore_through_free_staging_position():
    c=owner();a=Mock(id=88);a.type_id='vehicle.harley.low_rider'
    c.world.try_spawn_actor.side_effect=[None,a]
    c.world.get_map.return_value.get_spawn_points.return_value=[carla.Transform(carla.Location(x=100,z=1))]
    saved=dict(x=7,y=8,z=9,yaw=90,pitch=2,roll=1)
    restored=c.scene_vehicles.spawn(a.type_id,saved,source='DisplayCar',saved_pose=True)
    assert restored is a
    pose=a.set_transform.call_args.args[0]
    assert (pose.location.x,pose.location.y,pose.location.z)==(7,8,9)
    assert (pose.rotation.yaw,pose.rotation.pitch,pose.rotation.roll)==(90,2,1)
    assert c.managed[88]['physics_preset']=='approximate_motorcycle'
    a.set_simulate_physics.assert_called_once_with(False)


def test_replica_visibility_resolves_names_to_worker_local_ids():
    from scene_vehicle_worker import apply_visibility
    world=Mock();world.get_environment_objects.side_effect=lambda label:[environment('Hidden_SM_0',2**63+9),environment('Shown_SM_0',98)] if label==carla.CityObjectLabel.Car else []
    apply_visibility(world,{'Hidden_SM_0','Shown_SM_0'},{'Hidden_SM_0'})
    assert world.enable_environment_objects.call_args_list[0].args==({98},True)
    assert world.enable_environment_objects.call_args_list[1].args==({2**63+9},False)


def test_worker_helper_receives_primary_ticks_and_releases_process(monkeypatch):
    import scene_vehicles
    c=owner();child=Mock();child.poll.side_effect=[None,0,0];child.returncode=0
    factory=Mock(return_value=child);monkeypatch.setattr(scene_vehicles.subprocess,'Popen',factory)
    c.scene_vehicles.sync_worker(2010,{'Body'},{'Body'})
    c.tick.assert_called_once_with(publish=False)
    payload=json.loads(child.stdin.write.call_args.args[0]);assert payload['port']==2010 and payload['hidden_names']==['Body']
    child.stdin.close.assert_called_once();child.kill.assert_not_called()


def test_sidewalk_bike_is_hidden_and_not_restored_but_bay_bike_is_kept():
    from scene_vehicles import traffic_surface
    wmap=Mock();wmap.get_waypoint.return_value=NS(lane_type=carla.LaneType.Sidewalk)
    bay={'x':0,'y':0,'yaw':0,'length':7,'width':2}
    assert not traffic_surface(wmap,dict(x=0,y=0),[bay])
    wmap.get_waypoint.return_value=None
    assert not traffic_surface(wmap,dict(x=0,y=3),[bay])
    assert traffic_surface(wmap,dict(x=0,y=0),[bay])
    wmap.get_waypoint.return_value=NS(lane_type=carla.LaneType.Biking)
    assert traffic_surface(wmap,dict(x=0,y=3),[])
    c=owner([environment('SM_Yamaha_424_SM_0',1)])
    assert c.scene_vehicles.excluded=={'SM_Yamaha_424'}
    assert c.scene_vehicles.was_removed('SM_Yamaha_424')
    assert not c.scene_vehicles.convert()['created']
    c.scene_vehicles.restore({'hidden':[]})
    assert c.scene_vehicles.hidden=={'SM_Yamaha_424'}
    c.world.try_spawn_actor.assert_not_called()

def test_offroad_trucks_stay_removed_when_old_hidden_sources_are_restored():
    targets={'BP_Carlacola_Parked_C_7','BP_Carlacola_Parked_C_9','BP_EuropeanHGV_Parked_C_8'}
    c=owner([environment('RetainedTruck_SM_0',1)])
    c.world.get_map.return_value.name='Carla/Maps/Town10HD_Opt'
    scene=SceneVehicles(c)
    assert targets <= {r['source'] for r in scene.removed}
    scene.restore({'hidden':[*targets,'RetainedTruck']})
    assert scene.hidden=={'RetainedTruck'}
    assert all(scene.was_removed(source) for source in targets)
    assert not scene.was_removed('RetainedTruck')
