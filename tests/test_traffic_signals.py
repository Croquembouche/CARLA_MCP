import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import carla
import traffic_signals

def world():
    actors=[SimpleNamespace(id=i,type_id='traffic.traffic_light',freeze_group=Mock(),set_state=Mock(),reset_group=Mock(),set_green_time=Mock(),set_yellow_time=Mock(),set_red_time=Mock()) for i in (8,9,10)]
    for a in actors:a.get_group_traffic_lights=lambda:actors
    return SimpleNamespace(get_actor=lambda aid:next((a for a in actors if a.id==aid),None)),actors

def test_hold_uses_only_selected_group_and_sets_other_heads_red():
    w,a=world();traffic_signals.apply(w,{'id':8,'operation':'state','state':'Green','hold':True})
    a[0].freeze_group.assert_called_once_with(True)
    assert a[0].set_state.call_args.args==(carla.TrafficLightState.Green,)
    for other in a[1:]:other.set_state.assert_called_once_with(carla.TrafficLightState.Red);other.freeze_group.assert_not_called()

def test_duration_validation_precedes_any_mutation():
    w,a=world()
    for value in [float('nan'),float('inf'),0,-1,601,True,'10']:
        with pytest.raises(ValueError):traffic_signals.apply(w,{'id':8,'operation':'timing','green_time':10,'yellow_time':3,'red_time':value})
    for actor in a:actor.set_green_time.assert_not_called();actor.reset_group.assert_not_called()

def test_all_intersection_times_and_resume():
    w,a=world();traffic_signals.apply(w,{'id':8,'operation':'timing','scope':'intersection','green_time':12,'yellow_time':3,'red_time':4})
    for actor in a:actor.set_green_time.assert_called_once_with(12.);actor.set_yellow_time.assert_called_once_with(3.);actor.set_red_time.assert_called_once_with(4.)
    a[0].reset_group.assert_called_once();a[0].freeze_group.assert_called_once_with(False)

def test_one_shot_does_not_freeze_or_touch_other_states():
    w,a=world();traffic_signals.apply(w,{'id':8,'operation':'state','state':'Off','hold':False})
    a[0].set_state.assert_called_once_with(carla.TrafficLightState.Off);a[0].freeze_group.assert_not_called()
    for other in a[1:]:other.set_state.assert_not_called()

def test_dormant_signal_does_not_request_unavailable_geometry():
    actor=SimpleNamespace(id=1,is_dormant=True,get_light_boxes=Mock(side_effect=RuntimeError('unloaded tile')),get_location=lambda:SimpleNamespace(x=0,y=0,z=0),get_opendrive_id=lambda:'7')
    actor.get_group_traffic_lights=lambda:[actor]
    meta=traffic_signals.metadata(actor,'Carla/Maps/Town11/Town11')
    assert meta['dormant'] and meta['heads']==[] and meta['opendrive_id']=='7'
    actor.get_light_boxes.assert_not_called()

def test_dormant_signal_rejects_controls_before_mutation():
    w,a=world();a[0].is_dormant=True
    with pytest.raises(ValueError,match='unloaded map tile'):
        traffic_signals.apply(w,{'id':8,'operation':'state','state':'Green'})
    a[0].freeze_group.assert_not_called()

def test_exported_town10_heads_do_not_leak_to_other_towns(monkeypatch):
    monkeypatch.setattr(traffic_signals,'_HEADS',[{'pose':dict(x=0,y=0,z=0),'heads':[{'x':9}], 'pedestrian_heads':[], 'push_buttons':[]}])
    actor=SimpleNamespace(id=1,is_dormant=False,get_light_boxes=lambda:[],get_location=lambda:SimpleNamespace(x=0,y=0,z=0),get_opendrive_id=lambda:'7')
    actor.get_group_traffic_lights=lambda:[actor]
    assert traffic_signals.metadata(actor,'Carla/Maps/Town02_Opt')['heads']==[]
    assert traffic_signals.metadata(actor,'Carla/Maps/Town10HD_Opt')['heads']==[{'x':9}]
