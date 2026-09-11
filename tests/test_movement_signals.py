import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from movement_signals import MovementPrograms, pack, unpack, paths_conflict

XML='''<OpenDRIVE><road id="1"><signals><signalReference id="A"><validity fromLane="-1" toLane="-1"/><userData><vectorSignal turnRelation="Left"/></userData></signalReference></signals></road><road id="2"><signals><signalReference id="B"><validity fromLane="1" toLane="1"/><userData><vectorSignal turnRelation="Straight"/></userData></signalReference></signals></road></OpenDRIVE>'''

def manager():
    actors={i:SimpleNamespace(id=i,get_state=lambda:'Green',set_state=Mock(),set_movement_states=Mock(),freeze_group=Mock(),reset_group=Mock()) for i in (8,9)}
    world=SimpleNamespace(get_actor=actors.get)
    meta={i:{'group_id':8,'group_ids':[8,9],'opendrive_id':sign} for i,sign in [(8,'A'),(9,'B')]}
    lanes=[{'id':'1:0:-1','points':[[-5,0,0],[0,0,0],[5,0,0]]},{'id':'2:0:1','points':[[0,-5,0],[0,0,0],[0,5,0]]}]
    return MovementPrograms(world,XML,lanes,meta),actors


def test_conflicting_protected_rejected_before_mutation_and_permissive_accepted():
    m,a=manager();phase={'states':{'8':{'left':'Protected'},'9':{'straight':'Protected'}},'duration':10}
    with pytest.raises(ValueError,match='Conflicting'):m.apply({'group_id':8,'operation':'enable','phases':[phase]},0)
    a[8].freeze_group.assert_not_called()
    phase['states']['8']['left']='Permissive'
    m.apply({'group_id':8,'operation':'enable','phases':[phase]},0)
    m.update(3);m.update(5)
    assert unpack(a[8].set_movement_states.call_args.args[0])['left']=='Permissive'
    assert unpack(a[9].set_movement_states.call_args.args[0])['straight']=='Protected'


def test_initial_clearance_hold_transition_and_disable():
    m,a=manager();m.apply({'group_id':8,'operation':'enable'},10)
    assert m.snapshot()['8']['stage']=='yellow'
    m.update(12.9);assert m.snapshot()['8']['stage']=='yellow'
    m.update(13);assert unpack(a[8].set_movement_states.call_args.args[0])['left']=='Stop'
    m.update(15);assert unpack(a[8].set_movement_states.call_args.args[0])['left']=='Protected'
    m.apply({'group_id':8,'operation':'hold'},16);m.update(50);assert m.snapshot()['8']['index']==0
    m.apply({'group_id':8,'operation':'phase','index':1},50);assert m.snapshot()['8']['stage']=='yellow'
    m.update(53);m.update(55);assert unpack(a[9].set_movement_states.call_args.args[0])['straight']=='Protected'
    m.apply({'group_id':8,'operation':'disable'},55);a[8].reset_group.assert_not_called()
    m.update(58);m.update(60);assert not m.snapshot()['8']['active']
    a[8].set_movement_states.assert_called_with(0);a[8].freeze_group.assert_called_with(False)


def test_edit_waits_for_old_clearance_and_resets_phase_index():
    m,a=manager();m.apply({'group_id':8,'operation':'enable'},0);m.update(3);m.update(5)
    m.apply({'group_id':8,'operation':'update','phases':[{'name':'New','duration':4,'states':{'9':{'straight':'Protected'}}}],'yellow_time':1,'all_red_time':1},6)
    m.update(7);assert m.snapshot()['8']['stage']=='yellow'
    m.update(9);m.update(11)
    assert m.snapshot()['8']['phases'][0]['name']=='New'
    assert unpack(a[9].set_movement_states.call_args.args[0])['straight']=='Protected'


def test_flashing_uses_simulation_clock_and_unsupported_turns_rejected():
    moves={'left':'Permissive','straight':'Protected','right':'Off'}
    assert unpack(pack(moves,0))==moves
    assert (pack(moves,0)^pack(moves,.5))==0x4000
    assert unpack(0) is None
    m,a=manager()
    for states in [{'8':{'right':'Protected'}},{'9':{'straight':'Permissive'}}]:
        with pytest.raises(ValueError):m.apply({'group_id':8,'operation':'enable','phases':[{'states':states}]},0)
    assert not paths_conflict([[[0,0,0],[5,0,0]]],[[[0,0,10],[5,0,10]]])


def test_all_red_waits_for_crossing_actor_to_clear():
    m,a=manager();ped=SimpleNamespace(type_id='walker.pedestrian.0001',get_location=lambda:SimpleNamespace(x=0.,y=0.,z=1.))
    m.world.get_actors=lambda:[ped]
    m.apply({'group_id':8,'operation':'enable'},0);m.update(3);m.update(5)
    assert m.snapshot()['8']['stage']=='all-red' and m.snapshot()['8']['waiting_for_clearance']
    m.world.get_actors=lambda:[];m.update(5.05)
    assert m.snapshot()['8']['stage']=='green'


def test_replay_stop_replaces_native_owner_process(monkeypatch,tmp_path):
    import json
    import controller
    owner=controller.Controller.__new__(controller.Controller)
    owner.world=object();owner.mode='native-replay';owner.running=True;owner.state={};owner.last_gpus='0,1,2,3'
    timer=Mock();monkeypatch.setattr(controller,'DATA',tmp_path);monkeypatch.setattr(controller.threading,'Timer',lambda delay,callback:timer)
    result=owner.command('replay-stop',{})
    assert result['restarting_owner'] and owner.state['phase']=='restarting'
    assert json.loads((tmp_path/'restart-live-request.json').read_text())['gpus']=='0,1,2,3'
    timer.start.assert_called_once()
