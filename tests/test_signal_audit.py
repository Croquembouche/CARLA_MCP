import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from signal_audit import crosses_entry,SignalAudit
import pytest

def vehicle(x,y=0,yaw=0):return {'id':1,'type':'vehicle.test','pose':{'x':x,'y':y,'z':0,'yaw':yaw},'extent':{'x':1}}

def test_entry_detects_front_bumper_and_rejects_adjacent_or_opposite_lane():
 path=[[0,0,0,3.5],[10,0,0,3.5]]
 assert crosses_entry(vehicle(-2),vehicle(0),path)
 assert not crosses_entry(vehicle(-2,5),vehicle(0,5),path)
 assert not crosses_entry(vehicle(-2,0,180),vehicle(0,0,180),path)

def test_red_entry_and_protected_entry_are_distinguished():
 for indication,violations in [('Stop',1),('Protected',0)]:
  light={'id':8,'type':'traffic.traffic_light','movements':{'straight':indication},'movement_lanes':{'straight':{'paths':[[[0,0,0,3.5],[10,0,0,3.5]]]}}}
  audit=SignalAudit();audit.observe({'frame':1,'actors':[vehicle(-2),light]})
  result=audit.observe({'frame':2,'actors':[vehicle(0),light]})
  assert len(result['violations'])==violations and result['entries_observed']==1

def test_offset_connectors_select_route_before_entry_and_do_not_double_count():
 light={'id':8,'group_id':8,'type':'traffic.traffic_light','movements':{'left':'Stop','straight':'Protected'},'movement_lanes':{
  'left':{'paths':[[[0,0,0,3.5],[5,5,0,3.5]]]},
  'straight':{'paths':[[[2,0,0,3.5],[10,0,0,3.5]]]}}}
 route=[{'x':2,'y':0},{'x':10,'y':0}]
 audit=SignalAudit()
 for frame,x in enumerate((-2,0,2,4)):
  result=audit.observe({'frame':frame,'actors':[vehicle(x),light],'managed':{'1':{'route':route}}})
 assert result['entries_observed']==1
 assert result['recent_entries'][0]['movement']=='straight'
 assert result['violation_count']==0

@pytest.mark.parametrize('movements',[None,{}, {'left':'Protected'}])
@pytest.mark.parametrize('colour,violations',[('Red',1),('Green',0),('Yellow',0)])
def test_native_signal_colour_applies_without_a_separate_turn_indication(movements,colour,violations):
 light={'id':8,'type':'traffic.traffic_light','state':colour,'movements':movements,
        'movement_lanes':{'straight':{'paths':[[[0,0,0,3.5],[10,0,0,3.5]]]}}}
 audit=SignalAudit();audit.observe({'frame':758,'actors':[vehicle(-2),light]})
 result=audit.observe({'frame':759,'actors':[vehicle(0),light]})
 assert result['entries_observed']==1
 assert result['recent_entries'][0]['indication']==colour
 assert result['violation_count']==violations
 # Continuing past the same entry must neither fail nor double-count it.
 continued=audit.observe({'frame':760,'actors':[vehicle(1),light]})
 assert continued['entries_observed']==1
