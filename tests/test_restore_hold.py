"""Restoring one vehicle must not start it while later vehicles/sensors load."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import controller

def test_restore_stages_all_actors_before_enabling_drivers(monkeypatch):
    owner=controller.Controller.__new__(controller.Controller);owner.managed={};owner.state={'map':'Town10','time':0};events=[]
    owner.command=lambda *a:None;owner.refresh=lambda:None
    owner.movements=NS(snapshot=lambda:{})
    def spawn(payload):
        assert payload['_restore_exact_pose'] and payload['destination'] is None
        aid=len(owner.managed)+1;events.append(('spawn',aid))
        actor=NS(apply_control=lambda c:None,set_autopilot=lambda enabled,port:events.append(('drive',aid)))
        owner.managed[aid]={'actor':actor,'role':'background','planner':'tm','_restore_hold':True}
        return {'id':aid}
    owner.spawn=spawn;owner.destination=lambda aid,p:events.append(('destination',aid))
    owner.tick=lambda:events.append(('tick',len(owner.managed)))
    monkeypatch.setattr(controller.reliability,'checkpoint',lambda _:None)
    config={'map':'Town10','weather':{},'scene_vehicles':{},'actors':[{'id':1,'role':'background','destination':{'x':1}},{'id':2,'role':'background','destination':{'x':2}}]}
    owner.restore_configuration(config)
    assert events[:2]==[('spawn',1),('spawn',2)]
    assert all('_restore_hold' not in m for m in owner.managed.values())
    assert events[-1]==('tick',2) and owner.state['recovery_operation']['stage']=='ready'
