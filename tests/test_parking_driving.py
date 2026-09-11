import math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest,parking
from parking_driving import Obstacles,maneuver,angle,ParkingDriving

def test_clear_departure_and_arrival_have_continuous_curvature_paths():
    obstacles=Obstacles([],4.8,1.8)
    for start,goal in [({'x':0,'y':3,'yaw':0},{'x':15,'y':0,'yaw':0}),({'x':0,'y':0,'yaw':0},{'x':15,'y':3,'yaw':0})]:
        path=maneuver(start,goal,obstacles,5)
        assert len(path)>30 and abs(path[-1]['yaw'])<.01
        assert all(math.hypot(b['x']-a['x'],b['y']-a['y'])<.5 for a,b in zip(path,path[1:]))
        assert all(obstacles.clear(p['x'],p['y'],math.radians(p['yaw'])) for p in path)

def test_obstructed_start_and_destination_are_rejected():
    obstacle=Obstacles([parking.corners(0,0,5,3,0)],4.8,1.8)
    with pytest.raises(ValueError,match='current position'):maneuver({'x':0,'y':0,'yaw':0},{'x':15,'y':0,'yaw':0},obstacle)
    with pytest.raises(ValueError,match='destination'):maneuver({'x':15,'y':0,'yaw':0},{'x':0,'y':0,'yaw':0},obstacle)

def test_reverse_path_keeps_body_orientation():
    path=maneuver({'x':0,'y':0,'yaw':0},{'x':-8,'y':0,'yaw':0},Obstacles([],4,1.8),5)
    assert all(p['reverse'] for p in path)
    assert abs(path[-1]['yaw'])<.01

def test_rotated_vehicle_footprint_and_body_offset_are_checked():
    obstacles=Obstacles([parking.corners(4,0,1,1,0)],4,2,1)
    assert obstacles.clear(0,0,0)
    assert not obstacles.clear(1,0,0)
    assert obstacles.clear(1,0,math.pi)

from types import SimpleNamespace
from unittest.mock import Mock

def bay_driver():
    space=dict(id='P001',x=10,y=0,z=0,yaw=0,length=6,width=2.5,polygon=parking.corners(10,0,6,2.5,0))
    a=Mock();a.bounding_box.extent=SimpleNamespace(x=2.4,y=.9);a.bounding_box.location.x=0
    m=dict(actor=a,role='background',parked=True,destination=None)
    owner=SimpleNamespace(managed={1:m},state={'actors':[]},map_data={'parking_spaces':[space]},parking_static=[])
    return ParkingDriving(owner),owner,a

def test_parking_reservation_and_oversize_vehicle_rejections():
    driver,o,a=bay_driver();o.managed[2]={'parking_trip':{'bay':'P001'}}
    with pytest.raises(ValueError,match='reserved by vehicle 2'):driver.bay(1,'P001')
    del o.managed[2];a.bounding_box.extent.x=4
    with pytest.raises(ValueError,match='Vehicle needs'):driver.bay(1,'P001')
    a.set_autopilot.assert_not_called()

def test_own_vehicle_is_ignored_but_other_vehicle_blocks_destination():
    driver,o,a=bay_driver()
    row={'id':1,'type':'vehicle.test','pose':dict(x=10,y=0,z=0,yaw=0),'extent':dict(x=2.4,y=.9,z=.8)}
    o.state['actors']=[row];assert driver.bay(1,'P001')['id']=='P001'
    o.state['actors']=[dict(row,id=2)]
    with pytest.raises(ValueError,match='occupied'):driver.bay(1,'P001')

def test_failed_planning_preserves_old_destination_and_control():
    driver,o,a=bay_driver();old={'x':20,'y':0};o.managed[1]['destination']=old
    import carla
    a.get_transform.return_value=carla.Transform();driver.geometry=Mock(return_value=(2.8,70,4));driver.obstacles=Mock(return_value=Obstacles([],4.8,1.8))
    with pytest.raises(ValueError,match='Choose a parking bay'):driver.assign(1,{'parking_space':'unknown'})
    assert o.managed[1]['destination'] is old and o.managed[1]['parked']
    a.set_autopilot.assert_not_called();a.set_simulate_physics.assert_not_called()


@pytest.mark.parametrize('role',['background','ego'])
def test_running_vehicle_destination_bypasses_scenario_edit_guard(role):
    from controller import Controller
    c=Controller.__new__(Controller);c.mode='live';c.running=True;c.recording=object();c.world=object()
    c.managed={1:dict(role=role,parked=True)};c.parking_driver=Mock();c.require_edit=Mock(side_effect=AssertionError('must not pause'))
    c.command('destination',dict(id=1,point={'parking_space':'P001'}))
    c.parking_driver.assign.assert_called_once_with(1,{'parking_space':'P001'});c.require_edit.assert_not_called()


def test_reverse_entry_pulls_past_and_finishes_backwards():
    from parking_driving import parking_entry
    target=dict(x=0,y=3,z=0,yaw=0,length=7.5,width=2.5)
    obstacles=Obstacles([],4.5,1.8)
    path=parking_entry(dict(x=10,y=0,z=0,yaw=0),target,obstacles,5,2.7)
    assert all(p['reverse'] for p in path)
    assert path[-1]['x']==pytest.approx(0) and path[-1]['y']==pytest.approx(3)
    assert abs(path[-1]['yaw'])<.01
    assert all(obstacles.clear(p['x'],p['y'],math.radians(p['yaw'])) for p in path)


def test_reverse_entry_does_not_require_empty_neighbor_bay():
    from parking_driving import parking_entry
    # The old seven-metre alignment point occupied the car ahead of the bay.
    obstacles=Obstacles([parking.corners(7.5,3,4.5,1.8,0)],4.5,1.8)
    target=dict(x=0,y=3,z=0,yaw=0,length=7.5,width=2.5)
    path=parking_entry(dict(x=10,y=0,z=0,yaw=0),target,obstacles,5,2.7)
    assert path[-1]['reverse']
    assert all(obstacles.clear(p['x'],p['y'],math.radians(p['yaw'])) for p in path)


def test_final_reverse_constraint_can_include_forward_setup():
    path=maneuver(dict(x=-5,y=0,z=0,yaw=0),dict(x=0,y=3,z=0,yaw=0),Obstacles([],4.5,1.8),5,budget=4,final_reverse=True)
    assert path[-1]['reverse'] and any(not p['reverse'] for p in path)


def test_reverse_gear_is_not_engaged_while_still_moving_forward():
    import carla
    driver,o,a=bay_driver();path=[dict(x=-i*.25,y=0,z=0,yaw=0,reverse=True) for i in range(21)]
    m=o.managed[1];m['parking_trip']=dict(stage='entering',index=0,entry=path,wheelbase=2.8,rear_axle=1.4,max_steer=35,target=dict(x=-5,y=0,yaw=0,length=7,width=2.5),blocked=None)
    snap=Mock();snap.get_transform.return_value=carla.Transform();snap.get_velocity.return_value=carla.Vector3D(x=1)
    a.get_control.return_value=carla.VehicleControl(reverse=False);driver.obstacles=Mock(return_value=Obstacles([],4.8,1.8))
    control=driver.tick(m,snap)
    assert control.brake==1 and control.throttle==0 and not control.reverse
    assert m['parking_trip']['motion']=='changing_gear'


def test_geometry_uses_real_axle_bones_when_rpc_offsets_are_zero():
    driver,o,a=bay_driver();a.id=1
    a.get_physics_control.return_value.wheels=[SimpleNamespace(location=SimpleNamespace(x=0),max_steer_angle=70)]*4
    a.get_bone_names.return_value=['Wheel_Front_Left','Wheel_Front_Right','Wheel_Rear_Left','Wheel_Rear_Right']
    a.get_bone_relative_transforms.return_value=[SimpleNamespace(location=SimpleNamespace(x=x)) for x in [1.3,1.3,-1.6,-1.6]]
    wb,steer,radius=driver.geometry(a)
    assert wb==pytest.approx(2.9) and driver.rear_axles[1]==1.6 and steer==70


def test_rear_reference_interpolates_without_crossing_a_gear_change():
    from parking_driving import rear_reference
    path=[dict(x=0,y=0,yaw=0,reverse=True),dict(x=-1,y=0,yaw=0,reverse=True),dict(x=0,y=2,yaw=0,reverse=False)]
    error,index,x,y,yaw,curvature=rear_reference(path,0,1,dict(x=-.4,y=.2,yaw=0),1.2)
    assert error==pytest.approx(.2) and x==pytest.approx(-1.6) and y==0 and yaw==0 and curvature==0


@pytest.mark.parametrize('reverse,gear',[(False,1),(True,-1)])
def test_local_motion_explicitly_selects_gear_after_physics_wakes(reverse,gear):
    import carla
    driver,o,a=bay_driver();sign=-1 if reverse else 1
    path=[dict(x=sign*i*.25,y=0,z=0,yaw=0,reverse=reverse) for i in range(21)]
    m=o.managed[1];m['parking_trip']=dict(stage='entering',index=0,entry=path,wheelbase=2.8,rear_axle=1.4,max_steer=35,target=dict(x=sign*5,y=0,yaw=0,length=7,width=2.5),blocked=None)
    snap=Mock();snap.get_transform.return_value=carla.Transform();snap.get_velocity.return_value=carla.Vector3D()
    a.get_control.return_value=carla.VehicleControl(gear=0)
    driver.obstacles=Mock(return_value=Obstacles([],4.8,1.8));o.world=Mock()
    o.world.get_snapshot.return_value.timestamp.elapsed_seconds=0
    control=driver.tick(m,snap)
    assert control.manual_gear_shift and control.gear==gear and control.reverse==reverse
    assert control.throttle>0 and control.brake==0


def test_braking_preserves_reverse_gear():
    import carla
    a=Mock();a.get_control.return_value=carla.VehicleControl(reverse=True,gear=-1)
    control=ParkingDriving.hold(a)
    assert control.brake==1 and control.throttle==0
    assert control.reverse and control.manual_gear_shift and control.gear==-1

@pytest.mark.parametrize('role',['background','ego'])
@pytest.mark.parametrize('stage',['parked','entering','leaving','driving','arrived','blocked'])
def test_new_goal_replaces_every_parking_stage_and_releases_parking_hold(stage,role,monkeypatch):
    import carla,parking_driving
    driver,o,a=bay_driver();a.id=1
    start=carla.Transform(carla.Location(x=10))
    a.get_transform.return_value=start;a.get_location.return_value=start.location
    a.get_velocity.return_value=carla.Vector3D()
    a.get_control.return_value=carla.VehicleControl(hand_brake=True,reverse=True,gear=-1)
    m=o.managed[1];m['role']=role;old=dict(stage=stage,bay='P001',blocked='old blockage')
    m.update(parking_trip=old,parked=stage=='parked',physics_sleeping=stage=='parked',arrived=stage in ('parked','arrived'),_restore_hold=True,route_update={'revision':4})
    def wp(x):
        w=SimpleNamespace(transform=carla.Transform(carla.Location(x=x)),road_id=1,section_id=0,lane_id=-1,is_junction=False)
        w.next=lambda n:[wp(x+n)]
        return w
    o.wmap=Mock();o.wmap.get_waypoint.return_value=wp(10);o.waypoint=lambda p:wp(p['x'])
    o.tm=Mock();o.tm.get_all_actions.return_value=[];o.planner=Mock();o.refresh=Mock()
    o.client=Mock();o.client.apply_batch_sync.return_value=[]
    driver.geometry=Mock(return_value=(2.8,35,5));driver.rear_axles[1]=1.4;driver.merge_points=[]
    driver.obstacles=Mock(return_value=Obstacles([],4.8,1.8));driver.check_junctions=Mock()
    monkeypatch.setattr(parking_driving,'vehicle_route',lambda *args:([(wp(20),None),(wp(100),None)],False))
    monkeypatch.setattr(carla.command,'ApplyVehicleControl',lambda aid,control:SimpleNamespace(id=aid,control=control))
    result=driver.assign(1,dict(x=100,y=0,z=0))
    assert m['parking_trip'] is not old and m['parking_trip']['bay'] is None
    assert result['destination']['x']==100 and result['route_update']['revision']==5
    assert not m['arrived'] and not m['parked'] and not m['physics_sleeping'] and '_restore_hold' not in m
    initial=o.client.apply_batch_sync.call_args.args[0][0].control
    assert not initial.hand_brake and initial.manual_gear_shift and initial.gear==1
    if stage=='parked':a.set_simulate_physics.assert_called_once_with(True)
    assert old['bay']=='P001'  # the old plan is replaced, never appended

@pytest.mark.parametrize('role',['ego','background'])
def test_both_vehicle_roles_can_target_a_bay(role):
    driver,o,a=bay_driver();o.managed[1]['role']=role
    assert driver.bay(1,'P001')['id']=='P001'
    o.managed[1]['role']='pedestrian'
    with pytest.raises(ValueError,match='require a vehicle'):driver.bay(1,'P001')


def test_external_ego_parking_goal_preserves_its_control_policy(monkeypatch):
    import carla,parking_driving
    driver,o,a=bay_driver();m=o.managed[1];m.update(role='ego',planner='external',parked=False,route_update={'revision':2})
    wp=SimpleNamespace(transform=carla.Transform(carla.Location(x=10,y=-3),carla.Rotation(yaw=15)),is_junction=False)
    o.wmap=Mock();o.wmap.get_waypoint.return_value=wp;o.planner=Mock();o.refresh=Mock()
    monkeypatch.setattr(parking_driving,'vehicle_route',lambda *args:([(wp,None)],False))
    result=driver.assign(1,{'parking_space':'P001'})
    assert result['destination']==dict(x=10,y=0,z=0,yaw=15,parking_space='P001')
    assert m['planner']=='external' and 'parking_trip' not in m
    assert result['route_update']['execution']=='external' and result['route_update']['revision']==3
    a.set_autopilot.assert_not_called();a.apply_control.assert_not_called();a.set_simulate_physics.assert_not_called()
    o.managed[2]=dict(destination=result['destination'])
    with pytest.raises(ValueError,match='reserved by vehicle 2'):driver.bay(1,'P001')


def test_restore_parked_ego_keeps_role_sensors_and_parking_hold(monkeypatch):
    import controller
    from controller import Controller
    c=Mock();c.managed={};c.state={'map':'Carla/Maps/Town10HD_Opt','time':0}
    c.scene_vehicles.was_removed.return_value=False;c.running=False
    vehicle=Mock()
    def spawn(payload):
        assert payload['role']=='ego' and payload['planner']=='tm'
        assert payload['_restore_exact_pose'] and payload['sensors']==[{'name':'front_rgb'}]
        c.managed[7]=dict(actor=vehicle,role='ego',planner='tm',_restore_hold=True)
        return {'id':7}
    c.spawn.side_effect=spawn
    config=dict(map=c.state['map'],weather={},scene_vehicles={},actors=[dict(id=52,role='ego',model='vehicle.lincoln.mkz',planner='parked',saved_offroad_pose=True,parking_space='P024',destination=None,sensors=[{'name':'front_rgb'}])])
    monkeypatch.setattr(controller.reliability,'checkpoint',Mock())
    Controller.restore_configuration(c,config)
    m=c.managed[7];assert m['role']=='ego' and m['parked'] and m['parking_space']=='P024'
    assert m['parking_trip']['stage']=='parked' and m['planner']=='tm'
    vehicle.set_autopilot.assert_not_called();c.destination.assert_not_called()


@pytest.mark.parametrize('lane_id,can_enter',[(-1,True),(-2,True),(1,False)])
def test_parking_handoff_can_start_before_nominal_tm_staging_point(monkeypatch,lane_id,can_enter):
    import carla,parking_driving
    driver,o,a=bay_driver();a.id=1;o.world=Mock();o.world.get_snapshot.return_value.timestamp.elapsed_seconds=20
    o.wmap=Mock();o.wmap.get_waypoint.return_value=SimpleNamespace(road_id=1,section_id=0,lane_id=lane_id,is_junction=False)
    o.tm=Mock();a.get_control.return_value=carla.VehicleControl(gear=1)
    driver.geometry=Mock(return_value=(2.8,35,5));driver.obstacles=Mock(return_value=Obstacles([],4.8,1.8));driver.check_junctions=Mock()
    path=[dict(x=8-i*.25,y=0,z=0,yaw=0,reverse=True) for i in range(33)]
    monkeypatch.setattr(parking_driving,'parking_entry',lambda *args:path)
    m=o.managed[1];m['parking_trip']=dict(stage='driving',bay='P001',entry=path,road_goal=dict(x=16,y=0),road_goal_lane=[1,0,-1],target=dict(x=0,y=0,yaw=0,length=6,width=2.5),wheelbase=2.8,rear_axle=1.4,max_steer=35,index=0)
    snap=Mock();snap.get_transform.return_value=carla.Transform(carla.Location(x=8));snap.get_velocity.return_value=carla.Vector3D()
    control=driver.tick(m,snap)
    if not can_enter:
        assert control is None and m['parking_trip']['stage']=='driving'
        a.set_autopilot.assert_not_called()
        return
    assert m['parking_trip']['stage']=='entering'
    assert control.reverse and control.gear==-1 and control.throttle>0
    a.set_autopilot.assert_called_once_with(False,8005)
    driver.check_junctions.assert_called()


def test_tight_bay_uses_small_fit_margin_but_still_rejects_true_oversize():
    driver,o,a=bay_driver();bay=o.map_data['parking_spaces'][0];bay['width']=1.92
    a.bounding_box.extent.y=.918
    assert driver.bay(1,'P001')['width']==1.92
    a.bounding_box.extent.y=.98
    with pytest.raises(ValueError,match='Vehicle needs'):driver.bay(1,'P001')


@pytest.mark.parametrize('position,yaw',[(.12,0),(.025,2)])
def test_short_bay_does_not_stop_before_full_body_can_fit(position,yaw):
    import carla
    driver,o,a=bay_driver();o.world=Mock();o.world.get_snapshot.return_value.timestamp.elapsed_seconds=20
    a.get_control.return_value=carla.VehicleControl(reverse=True,gear=-1)
    driver.obstacles=Mock(return_value=Obstacles([],4.8,1.8))
    path=[dict(x=1-i*.05,y=0,z=0,yaw=0,reverse=True) for i in range(21)]
    m=o.managed[1];m['parking_trip']=dict(stage='entering',index=15,entry=path,wheelbase=2.8,rear_axle=1.4,max_steer=35,target=dict(x=0,y=0,yaw=0,length=4.9,width=2.5),blocked=None)
    snap=Mock();snap.get_transform.return_value=carla.Transform(carla.Location(x=position),carla.Rotation(yaw=yaw));snap.get_velocity.return_value=carla.Vector3D()
    control=driver.tick(m,snap)
    assert m['parking_trip']['stage']=='entering'
    assert not m['parking_trip'].get('alignment_attempts')
    assert control.throttle>0 and control.reverse
