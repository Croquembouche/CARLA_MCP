from types import SimpleNamespace
import bootstrap
import app

def test_status_exposes_wait_age_without_mutating_owner_state(monkeypatch):
    import json
    state={'phase':'connected','running':True,'tick_progress':{'stage':'sensor','started':10.,'frame':42,'sensor':'front_rgb'}}
    monkeypatch.setattr(app,'engine',SimpleNamespace(state=state))
    monkeypatch.setattr(app.time,'monotonic',lambda:17.5)
    result=json.loads(app.status().body)
    assert result['stream_health']=={'stage':'sensor','frame':42,'sensor':'front_rgb','elapsed_seconds':7.5}
    assert 'stream_health' not in state
