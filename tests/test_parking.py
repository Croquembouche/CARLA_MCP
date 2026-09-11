import sys,json,math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,carla,parking
from controller import Controller

@pytest.fixture
def spaces():
    source=Path('data/map-cache.xodr').read_text();w=carla.Map('Town10HD_Opt',source)
    return parking.build_parking(w,source,Path('data/parking/Town10HD_Opt.json'))['parking_spaces']

def test_surveyed_bays_follow_curb_geometry_without_claiming_painted_divisions(spaces):
    assert len(spaces)==180 and len({p['id'] for p in spaces})==180
    assert all(p['estimated'] and p['source']=='surveyed_curb_position' for p in spaces)
    assert all(1.8<=p['width']<=2.8 for p in spaces)
    assert all('planning' in p['boundary_note'] for p in spaces)
    assert all(5<=p['length']<=7.5 for p in spaces)
    assert all(len(p['polygon'])==4 for p in spaces)

def test_wrong_map_does_not_inherit_town10_parking():
    assert not parking.build_parking(SimpleNamespace(name='Town01'),'',Path('data/parking/Town10HD_Opt.json'))['parking_spaces']

def test_occupancy_detects_rotated_scenery_and_live_vehicles_but_not_other_floors():
    p={'id':'P011','polygon':parking.corners(0,0,7,2.5,45),'z':0}
    box={'name':'static car','polygon':parking.corners(0,0,4,2,45),'z':1,'height':2}
    assert parking.occupancy([p],[box],[])['P011']['kind']=='scenery'
    box['z']=6;assert parking.occupancy([p],[box],[])['P011'] is None
    actor={'id':9,'type':'vehicle.test','pose':{'x':1,'y':1,'z':0,'yaw':45},'extent':{'x':2,'y':1,'z':1}}
    assert parking.occupancy([p],[],[actor])['P011']=={'kind':'actor','id':9}
    actor['pose']['x']=20;assert parking.occupancy([p],[],[actor])['P011'] is None

def parking_owner(spaces,occupied=False,width=1):
    c=Controller.__new__(Controller);c.managed={};c.map_data={'parking_spaces':spaces};c.state={'parking':{'occupied':{'P011':{'kind':'scenery'} if occupied else None}},'managed':{}};c.running=False;c.recording=None;c.mode='live'
    c.refresh=Mock();c.tick=Mock();c.world=Mock();a=Mock();a.id=123;a.bounding_box.extent=SimpleNamespace(x=2,y=width,z=1);c.world.try_spawn_actor.return_value=a
    c.world.get_blueprint_library.return_value.find.return_value.id='vehicle.test'
    def refresh():c.state['managed']={str(k):{x:y for x,y in m.items() if x!='actor'} for k,m in c.managed.items()}
    c.refresh.side_effect=refresh
    return c,a

def test_spawn_parked_stays_off_tm_and_applies_handbrake(spaces):
    c,a=parking_owner(spaces);r=c.spawn({'role':'background','model':'vehicle.test','parking_space':'P011'})
    assert r['id']==123 and c.managed[123]['parked']
    a.set_autopilot.assert_called_once_with(False,8005)
    control=a.apply_control.call_args.args[0];assert control.hand_brake and control.brake==1
    # Destinations now delegate to the parking maneuver controller.
    c.parking_driver=Mock();c.destination(123,dict(x=0,y=0));c.parking_driver.assign.assert_called_once_with(123,dict(x=0,y=0))

def test_occupied_and_oversized_bays_reject_without_leaking_actor(spaces):
    c,a=parking_owner(spaces,occupied=True)
    with pytest.raises(ValueError,match='occupied'):c.spawn_parked({'model':'vehicle.test','parking_space':'P011'})
    c.world.try_spawn_actor.assert_not_called()
    c,a=parking_owner(spaces,width=2)
    with pytest.raises(ValueError,match='Vehicle needs'):c.spawn_parked({'model':'vehicle.test','parking_space':'P011'})
    a.destroy.assert_called_once();assert not c.managed

def test_parking_placement_rejects_running_and_recording(spaces):
    c,_=parking_owner(spaces);c.running=True
    with pytest.raises(ValueError,match='Pause'):c.spawn_parked({'model':'vehicle.test','parking_space':'P011'})
    c.running=False;c.recording=object()
    with pytest.raises(ValueError,match='Stop recording'):c.spawn_parked({'model':'vehicle.test','parking_space':'P011'})


def test_validated_bays_keep_ids_exclude_junction_space_and_do_not_overlap(spaces):
    assert len([p for p in spaces if p['id'].startswith('P')])==41
    assert len([p for p in spaces if p['id'].startswith('R')])==139
    assert not [(a['id'],b['id']) for i,a in enumerate(spaces) for b in spaces[i+1:] if parking.overlaps(a['polygon'],b['polygon'])]
    assert next(p for p in spaces if p['id']=='P011')['x']>-26
    assert 'P020' in {p['id'] for p in spaces}

def test_changed_opendrive_does_not_silently_reuse_validated_spaces():
    result=parking.build_parking(SimpleNamespace(name='Town10HD_Opt'),'changed map',Path('data/parking/Town10HD_Opt.json'))
    assert result['parking_spaces']==[]
    assert 'revalidation' in result['parking_source']


def test_unknown_space_cannot_be_spawned_or_used_as_destination(spaces):
    from parking_driving import ParkingDriving
    c,a=parking_owner(spaces)
    with pytest.raises(ValueError,match='Choose a parking bay'):
        c.spawn_parked({'model':'vehicle.test','parking_space':'missing'})
    c.world.try_spawn_actor.assert_not_called()
    c.managed[123]={'actor':a,'role':'background'}
    with pytest.raises(ValueError,match='Choose a parking bay'):
        ParkingDriving(c).bay(123,'missing')
    a.set_autopilot.assert_not_called()


def test_reload_parking_preserves_world_and_actors_while_running(spaces):
    c=Controller.__new__(Controller);c.world=Mock();c.wmap=SimpleNamespace(name='Town10HD_Opt');c.opendrive=Path('data/map-cache.xodr').read_text();c.recording=None;c.mode='live';c.running=True
    c.map_data={'name':'Town10HD_Opt','lanes':['unchanged'],'parking_source':'old'};c.refresh=Mock();c.managed={'existing':object()};managed=c.managed
    from unittest.mock import patch
    with patch('controller.dump'):
        result=c.command('reload-parking',{})
    assert result=={'selectable':180,'excluded':0}
    assert c.managed is managed and c.running and c.map_data['lanes']==['unchanged']
    c.world.tick.assert_not_called();c.world.load_world.assert_not_called();c.refresh.assert_called_once()
    c.recording=object()
    with pytest.raises(ValueError,match='Stop recording'):
        c.command('reload-parking',{})


def test_policy_opens_formerly_withheld_bays_without_changing_geometry(spaces):
    import json
    original=json.loads(Path('data/parking/Town10HD_Opt.json').read_text())['validated_spaces']
    assert spaces==original
    assert {'P009','P012','P020','P033'} <= {p['id'] for p in spaces}
    assert not any(p.get('restriction_reasons') for p in spaces)
