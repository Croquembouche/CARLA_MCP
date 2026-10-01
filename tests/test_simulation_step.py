"""A 10 Hz configuration must change physics stepping, not only reported FPS."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap
from controller import Controller, validate_loadout


@pytest.mark.parametrize('step', [.05, .1])
def test_world_step_has_sufficient_physics_substeps(step):
    owner = Controller.__new__(Controller)
    settings = SimpleNamespace()
    owner.world = Mock()
    owner.world.get_settings.return_value = settings
    owner.set_simulation_step(step)
    applied = owner.world.apply_settings.call_args.args[0]
    assert applied.synchronous_mode and applied.substepping
    assert applied.fixed_delta_seconds == owner.fixed_delta_seconds == step
    assert applied.max_substep_delta_time <= .01
    assert applied.max_substeps * applied.max_substep_delta_time >= step


@pytest.mark.parametrize('step', [0, -.1, .2, float('nan'), float('inf'), True])
def test_invalid_step_does_not_mutate_world(step):
    owner = Controller.__new__(Controller)
    owner.world = Mock()
    with pytest.raises(ValueError):
        owner.set_simulation_step(step)
    owner.world.apply_settings.assert_not_called()


def test_sensor_cadence_matches_world():
    sensor = dict(name='front', type='sensor.camera.rgb', attributes={'sensor_tick': '.1'})
    assert validate_loadout([sensor], .1)[0]['attributes']['sensor_tick'] == '0.0'
    with pytest.raises(ValueError):
        validate_loadout([sensor], .05)


def test_step_changes_measured_worker_profile_key():
    owner = Controller.__new__(Controller)
    owner.state = {'map': 'Town02', 'weather': {}}
    owner.managed = {}
    old = owner.profile_key([])
    owner.fixed_delta_seconds = .1
    assert owner.profile_key([]) != old


def test_timing_summary_handles_recording_stage_appearing_and_disappearing():
    from gpu_resources import summary
    assert summary([{'total_ms':10},{'total_ms':20,'ros_serialize_ms':3},{'total_ms':12}])=={
        'total_ms':{'mean':14.,'p95':20},'ros_serialize_ms':{'mean':3.,'p95':3}}
    assert summary([{'total_ms':20,'ros_serialize_ms':3},{'total_ms':10}])['ros_serialize_ms']['mean']==3
