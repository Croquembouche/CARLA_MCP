"""Destination changes are owner-thread commands allowed between running frames."""
from types import SimpleNamespace
from unittest.mock import Mock
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,carla,pytest
from controller import Controller


def owner(planner='tm',recording=None):
    c=Controller.__new__(Controller)
    a=Mock();a.get_location.return_value=carla.Location(x=10)
    c.managed={28:dict(actor=a,role='ego',planner=planner,destination={'x':1,'y':0,'z':0},route=[],arrived=True,approach_slowdown=True)}
    c.world=object();c.mode='live';c.running=True;c.recording=recording;c.state={'frame':321};c.tm=Mock();c.tm.get_all_actions.return_value=[];c.refresh=Mock()
    c.require_edit=Mock(side_effect=AssertionError('Running destination must bypass scenario edit guard'))
    c.waypoint=lambda p:SimpleNamespace(transform=carla.Transform(carla.Location(**p)),road_id=7,section_id=0,lane_id=-2,is_junction=False)
    c.planner=Mock();c.planner.trace_route.side_effect=lambda origin,target:[(c.waypoint(dict(x=origin.x,y=origin.y,z=origin.z)),None),(c.waypoint(dict(x=target.x,y=target.y,z=target.z)),None)]
    return c,a


def test_running_recording_reroute_replaces_path_from_current_location():
    c,a=owner(recording=object())
    for revision,x in enumerate([30,60],1):
        a.get_location.return_value=carla.Location(x=revision*10)
        result=c.command('destination',{'id':28,'point':dict(x=x,y=0,z=0)})
        assert c.running and c.recording
        assert c.planner.trace_route.call_args.args[0].x==revision*10
        assert result['route_update']==dict(revision=revision,frame=321,execution='traffic_manager',preserved_junction=False)
        assert c.tm.set_path.call_args.args[2] is True  # replace, never append
        assert c.tm.set_path.call_args.args[1][-1].x==x
        assert not c.managed[28]['arrived'] and not c.managed[28]['approach_slowdown']
        c.tm.vehicle_percentage_speed_difference.assert_called_with(a,0)
    c.require_edit.assert_not_called()


def test_external_goal_does_not_take_over_vehicle_control():
    c,a=owner('external')
    r=c.command('destination',{'id':28,'point':dict(x=30,y=0,z=0)})
    assert r['route_update']['execution']=='external'
    a.set_autopilot.assert_not_called();c.tm.set_path.assert_not_called()


def test_invalid_route_keeps_previous_destination_and_control():
    c,a=owner();c.planner.trace_route.side_effect=None;c.planner.trace_route.return_value=[]
    with pytest.raises(ValueError,match='No drivable route'):c.command('destination',{'id':28,'point':dict(x=30,y=0,z=0)})
    assert c.managed[28]['destination']['x']==1
    a.set_autopilot.assert_not_called();c.tm.set_path.assert_not_called()


def test_native_replay_still_rejects_live_destination():
    c,_=owner();c.mode='native-replay'
    with pytest.raises(ValueError,match='Stop replay'):c.command('destination',{'id':28,'point':dict(x=30,y=0,z=0)})


def test_town10_reroute_inside_overlapping_connectors_retains_tm_movement():
    from agents.navigation.global_route_planner import GlobalRoutePlanner
    from lane_map import vehicle_route,traffic_path
    import json
    wmap=carla.Map('Town10',Path('data/map-cache.xodr').read_text());planner=GlobalRoutePlanner(wmap,2.)
    points=json.loads(Path('data/map-cache.json').read_text())['spawn_points']
    loc=lambda i:carla.Location(**{k:points[i][k] for k in ('x','y','z')})
    # The moving ego was committed straight through this intersection, while a
    # nearest-point replan incorrectly snapped onto the overlapping right turn.
    old=planner.trace_route(carla.Location(x=-70,y=-58),loc(96))
    front=min((w for w,_ in old if w.is_junction),key=lambda w:w.transform.location.distance(carla.Location(x=-58,y=-57)))
    target=loc(75)
    route,kept=vehicle_route(planner,carla.Location(x=-58,y=-57),target,front)
    assert kept and route[0][0].id==front.id
    exit_index=next(i for i,(w,_) in enumerate(route) if not w.is_junction)
    assert exit_index>0
    assert all(w.road_id==front.road_id for w,_ in route[:exit_index])
    assert (route[-1][0].road_id,route[-1][0].lane_id)==(wmap.get_waypoint(target).road_id,wmap.get_waypoint(target).lane_id)
    assert traffic_path(route,target)[-1].distance(target)<.01
    assert len(route)>30  # The legitimate route must go around to this missed turn.
