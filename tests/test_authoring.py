import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from authoring import ScenarioSchedule,validate
from test_movement_signals import manager


def test_schedule_uses_simulation_time_orders_actions_and_cleans_only_its_actors():
    calls=[];removed=[];arrivals=set();next_id=iter(range(100,110))
    def execute(e,refs):
        calls.append((e['id'],dict(refs)))
        return next(next_id) if e['action'].startswith('spawn') else None
    s=ScenarioSchedule(execute,lambda aid:aid in arrivals,removed.append)
    s.configure({'flows':[{'id':'flow','start':1,'interval':2,'count':2,'remove_arrived':True}], 'events':[{'id':'car','time':0,'action':'spawn_vehicle'},{'id':'dest','time':0,'action':'destination','actor':'car'}]})
    s.start(100);s.update(100);assert calls[1][1]['car']==100
    s.update(100);assert len(calls)==2
    s.update(101);assert calls[-1][0]=='flow';arrivals.add(101);s.update(102);assert removed==[101]
    s.update(103);assert s.flows[0]['spawned']==2
    s.stop();s.update(1000);assert len(calls)==4


def test_flow_occupied_spawn_retries_then_skips_without_backlog_burst():
    def fail(e,refs):raise ValueError('occupied')
    s=ScenarioSchedule(fail,lambda _:False,lambda _:None);s.configure({'flows':[{'id':'flow','start':0,'interval':1,'count':2,'remove_arrived':True}],'events':[]});s.start(0)
    s.update(0);s.update(.5);assert len(s.log)==1
    s.update(10);assert s.flows[0]['skipped']==1
    s.update(11);assert s.flows[0]['skipped']==2;assert not s.running


def test_invalid_plan_is_rejected_and_named_destinations_require_prior_spawn():
    kwargs=dict(catalog={'vehicles':[{'id':'vehicle.a'}],'walkers':['walker.a']},points=[{},{}],pedestrians=[{},{}],groups={8:[{}]},actor_ids=[25])
    base={'id':'car','time':2,'action':'spawn_vehicle','model':'vehicle.a','spawn':0,'destination':1}
    with pytest.raises(ValueError,match='follow'):validate({'events':[base,{'id':'dest','time':1,'action':'destination','actor':'car','destination':1}]},**kwargs)
    with pytest.raises(ValueError):validate({'flows':[{'id':'flow','start':0,'count':1,'interval':0,'model':'vehicle.a','spawn':0,'destination':1}]},**kwargs)
    assert validate({'events':[base,{'id':'dest','time':3,'action':'destination','actor':'car','destination':1}]},**kwargs)['events'][1]['actor']=='car'


def test_coordinated_offsets_and_cycle_recovery():
    m,a=manager();m.apply({'group_id':8,'operation':'enable'},0);m.update(3);m.update(5)
    m.network.configure({'mode':'coordinated','cycle_time':50,'offsets':{'8':7}},6)
    m.update(9);m.update(11);assert m.programs[8]['stage']=='all-red'
    m.update(18.05);assert m.programs[8]['stage']=='green';assert m.programs[8]['index']==0
    assert m.network.release[8]==pytest.approx(68.05)
    with pytest.raises(ValueError):m.network.configure({'mode':'coordinated','cycle_time':1},19)
    with pytest.raises(ValueError,match='Independent'):m.apply({'group_id':8,'operation':'update'},19)
    m.apply({'group_id':8,'operation':'hold'},19);assert m.network.config['mode']=='independent'


def test_adaptive_green_honors_minimum_gap_and_maximum():
    m,a=manager();m.apply({'group_id':8,'operation':'enable'},0);m.update(3);m.update(5)
    m.network.configure({'mode':'adaptive','min_green':4,'max_green':8,'gap':2,'distance':40},5)
    m.network.detect=lambda:{'8':0};m.update(8.9);assert m.programs[8]['stage']=='green'
    m.update(9);assert m.programs[8]['stage']=='yellow'
    m.update(12);m.update(14);m.network.detect=lambda:{'9':10}
    m.update(21.9);assert m.programs[8]['stage']=='green'
    m.update(22);assert m.programs[8]['stage']=='yellow'
