import sys
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
from vehicle_lighting import automatic_state,L,AutomaticVehicleLights

def weather(**kw):return NS(**({'sun_altitude_angle':45,'precipitation':0,'fog_density':0}|kw))
def control(**kw):return NS(**({'brake':0,'reverse':False,'gear':1,'steer':0}|kw))
def test_day_night_rain_fog_and_preserved_special_lights():
    assert automatic_state(int(L.LowBeam),weather(),control())==0
    for w in [weather(sun_altitude_angle=-10),weather(precipitation=90),weather(fog_density=30)]:
        value=automatic_state(int(L.Special1),w,control());assert value&int(L.LowBeam) and value&int(L.Position) and value&int(L.Special1)
    assert automatic_state(0,weather(fog_density=30),control())&int(L.Fog)
    assert automatic_state(0,weather(sun_altitude_angle=25),control())==int(L.Position)
def test_braking_reverse_turn_and_parked_clearing():
    value=automatic_state(0,weather(),control(brake=.8,reverse=True,gear=-1,steer=-.5));assert value&int(L.Brake) and value&int(L.Reverse) and value&int(L.LeftBlinker)
    assert automatic_state(value,weather(),control(),parked=True)==0
    assert automatic_state(0,weather(),control(),arrived=True)&int(L.Brake)
def test_tm_transitions_and_no_redundant_light_writes():
    class Actor:
        type_id='vehicle.test'
        def get_control(self):return control()
    actor=Actor();m={'actor':actor,'planner':'tm'};calls=[];batches=[]
    owner=NS(state={},mode='live',world=NS(get_weather=lambda:weather(),get_vehicles_light_states=lambda:{1:L.NONE},get_snapshot=lambda:NS(has_actor=lambda aid:True)),managed={1:m},tm=NS(update_vehicle_lights=lambda a,on:calls.append(on)),client=NS(apply_batch_sync=lambda b,t:batches.append(b) or []))
    policy=AutomaticVehicleLights();policy.update(owner);policy.update(owner);assert calls==[True] and batches==[]
    m['arrived']=True;policy.update(owner);assert calls==[True,False] and len(batches)==1
    owner.mode='native-replay';policy.update(owner);assert len(batches)==1


def lighting_owner(actor,present=True,parked=False):
    from unittest.mock import Mock
    world=NS(get_weather=lambda:weather(sun_altitude_angle=0),get_vehicles_light_states=lambda:{1:L.NONE},get_snapshot=lambda:NS(has_actor=lambda aid:present))
    client=Mock();client.apply_batch_sync.return_value=[]
    return NS(state={},mode='live',world=world,managed={1:{'actor':actor,'planner':'external','parked':parked}},tm=Mock(),client=client)

def test_new_actor_before_first_snapshot_does_not_read_controls_or_update_tm():
    from unittest.mock import Mock
    actor=Mock(type_id='vehicle.test');actor.get_control.side_effect=RuntimeError('std::exception')
    owner=lighting_owner(actor,present=False);AutomaticVehicleLights().update(owner)
    actor.get_control.assert_not_called();owner.tm.update_vehicle_lights.assert_not_called()
    assert owner.state['vehicle_lighting']['status']=='ready'

def test_parked_actors_do_not_require_control_snapshot():
    from unittest.mock import Mock
    actor=Mock(type_id='vehicle.test');actor.get_control.side_effect=RuntimeError('std::exception')
    owner=lighting_owner(actor,parked=True);AutomaticVehicleLights().update(owner)
    actor.get_control.assert_not_called();owner.client.apply_batch_sync.assert_called_once()

def test_one_actor_control_failure_is_reported_without_aborting_spawn_tick():
    from unittest.mock import Mock
    actor=Mock(type_id='vehicle.test');actor.get_control.side_effect=RuntimeError('std::exception')
    owner=lighting_owner(actor);policy=AutomaticVehicleLights();policy.update(owner)
    assert owner.state['vehicle_lighting']=={'status':'degraded','warnings':[{'id':1,'model':'vehicle.test','detail':'std::exception'}]}
    actor.get_control.side_effect=None;actor.get_control.return_value=control();policy.update(owner)
    assert owner.state['vehicle_lighting']=={'status':'ready','warnings':[]}

def test_light_write_failure_reports_the_actor_without_aborting_world_tick():
    from unittest.mock import Mock
    actor=Mock(type_id='vehicle.test');actor.get_control.return_value=control()
    owner=lighting_owner(actor);owner.client.apply_batch_sync.return_value=[NS(error='actor no longer exists')]
    AutomaticVehicleLights().update(owner)
    assert owner.state['vehicle_lighting']['warnings']==[{'id':1,'detail':'actor no longer exists'}]
