import sys,math,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,carla
from agents.navigation.global_route_planner import GlobalRoutePlanner
from lane_map import build_lanes,traffic_path

def test_real_opendrive_driving_direction_and_turns():
    world_map=carla.Map('Town10',Path('data/map-cache.xodr').read_text())
    lanes,_,marks=build_lanes(world_map)
    assert len(lanes)>100
    for lane in lanes:
        for a,b in zip(lane['points'],lane['points'][1:]):
            yaw=math.radians(a[4])
            assert (b[0]-a[0])*math.cos(yaw)+(b[1]-a[1])*math.sin(yaw)>-.01
    assert {'left','right','straight'}<={t for l in lanes for t in l['maneuvers']}
    assert all(m['turns'] for m in marks if m['kind']=='turns')
    # Known opposite travel directions must both exist.
    assert any(float(l['id'].split(':')[-1])>0 for l in lanes)
    assert any(float(l['id'].split(':')[-1])<0 for l in lanes)

def test_tm_anchors_target_exit_roads_and_exact_destination():
    world_map=carla.Map('Town10',Path('data/map-cache.xodr').read_text())
    points=[carla.Location(x=p['x'],y=p['y'],z=p['z']) for p in json.loads(Path('data/map-cache.json').read_text())['spawn_points']];target=world_map.get_waypoint(points[20]).transform.location
    path=GlobalRoutePlanner(world_map,2.).trace_route(points[10],target)
    anchors=traffic_path(path,target)
    assert 1<len(anchors)<len(path)/3
    assert anchors[-1].distance(target)<.001
    assert all(not world_map.get_waypoint(p).is_junction for p in anchors)

def test_arrived_tm_actor_holds_brake_each_frame():
    from types import SimpleNamespace
    from controller import Controller
    controls=[]
    actor=SimpleNamespace(id=31,apply_control=lambda _: (_ for _ in ()).throw(AssertionError("Sticky actor control path used")))
    owner=Controller.__new__(Controller)
    owner.schedule=SimpleNamespace(update=lambda now:None);owner.scheduled_walkers=[]
    owner.movements=None;owner.mode='live';owner.managed={31:{'actor':actor,'role':'background','planner':'tm','arrived':True,'destination':{'x':0,'y':0}}}
    owner.world=SimpleNamespace(tick=lambda timeout:1,get_snapshot=lambda:SimpleNamespace(frame=1,timestamp=SimpleNamespace(elapsed_seconds=0)))
    owner.client=SimpleNamespace(apply_batch_sync=lambda batch,tick:controls.append(batch) or [])
    owner.sensors={};owner.ros=None;owner.recording=None;owner.refresh=lambda snap:None
    owner.prune_removed_actors=lambda:None
    owner.vehicle_lighting=SimpleNamespace(update=lambda owner:None)
    owner.world.get_snapshot=lambda:SimpleNamespace(frame=1,timestamp=SimpleNamespace(elapsed_seconds=0),find=lambda aid:actor)
    owner.frame_timings=__import__('collections').deque(maxlen=120);owner.state={}
    owner._tick();owner._tick()
    assert len(controls)==2 and all(len(batch)==1 for batch in controls)

def test_sidewalk_sections_and_crosswalks_from_real_opendrive():
    from lane_map import build_pedestrian_lanes,pedestrian_point
    source=Path('data/map-cache.xodr').read_text();world_map=carla.Map('Town10',source)
    data=build_pedestrian_lanes(world_map,source)
    assert len(data['pedestrian_lanes'])==74
    assert len(data['crosswalks'])==16
    for lane in data['pedestrian_lanes']:
        assert lane['bidirectional']
        assert all(math.dist(a[:3],b[:3])<3.0 for a,b in zip(lane['points'],lane['points'][1:]))
        p=lane['points'][len(lane['points'])//2]
        snapped=pedestrian_point(data,dict(x=p[0]+.1,y=p[1]+.1,z=0))
        assert math.hypot(snapped['x']-p[0],snapped['y']-p[1])<.2
    import pytest
    with pytest.raises(ValueError):pedestrian_point(data,{'x':10000,'y':10000})
    with pytest.raises(ValueError):pedestrian_point(data,{'x':float('nan'),'y':0})
    data['pedestrian_points']=[{'x':1000,'y':1000,'z':4}]
    assert pedestrian_point(data,{'x':1000,'y':1000})==data['pedestrian_points'][0]

def test_new_destination_restarts_arrived_pedestrian():
    from types import SimpleNamespace
    from controller import Controller
    calls=[]
    ctrl=SimpleNamespace(get_navigation_path=lambda p:[carla.Location(),p],start=lambda:calls.append('start'),set_max_speed=lambda speed:calls.append(speed),go_to_location=lambda p:calls.append((p.x,p.y)))
    owner=Controller.__new__(Controller);owner.map_data={'pedestrian_points':[{'x':10,'y':20,'z':1}]}
    owner.managed={25:{'role':'pedestrian','arrived':True,'actor':SimpleNamespace(get_location=lambda:carla.Location()),'controller':ctrl}}
    owner.refresh=lambda:None
    result=owner.destination(25,{'x':10,'y':20})
    assert calls==['start',1.4,(10,20)]
    assert not owner.managed[25]['arrived']
    assert result['destination']=={'x':10,'y':20,'z':1}
    assert owner.managed[25]['route_source']=='CARLA navigation mesh'
