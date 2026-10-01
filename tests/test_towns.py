import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from towns import available_towns, resolve_town
from controller import Controller


def test_stop_blocks_new_start_until_controller_restarts():
    c=Controller.__new__(Controller);c.state={'phase':'connected'}
    c.disconnect=Mock()
    assert c.command('shutdown',{})=={'stopped':True}
    c.disconnect.assert_called_once_with(stop_process=True)
    assert c.state['phase']=='stopping'
    with pytest.raises(ValueError,match='controller to restart'):
        c.command('start',{'town':'Town02_Opt'})


def test_catalog_excludes_tiles_and_resolves_exact_packages(tmp_path):
    for name in ['Town01_Opt.umap', 'Town10HD_Opt.umap', 'Town01_Tile_0_0.umap', 'Town_C.umap']:
        (tmp_path / name).touch()
    (tmp_path / 'Town12').mkdir()
    (tmp_path / 'Town12/Town12.umap').touch()
    assert [t['name'] for t in available_towns(tmp_path)] == ['Town01_Opt', 'Town10HD_Opt', 'Town12']
    assert resolve_town('Town12', tmp_path) == '/Game/Carla/Maps/Town12/Town12'
    assert resolve_town('Carla/Maps/Town01_Opt', tmp_path) == '/Game/Carla/Maps/Town01_Opt'
    with pytest.raises(ValueError):resolve_town('../../Town01_Opt', tmp_path)


@pytest.mark.parametrize('running,recording,mode,owned', [(True,None,'live',True),(False,object(),'live',True),(False,None,'native-replay',True),(False,None,'live',False)])
def test_switch_rejects_unsafe_lifecycle_states(running,recording,mode,owned):
    c=Controller.__new__(Controller)
    c.world=object();c.running=running;c.recording=recording;c.mode=mode
    c.proc=object() if owned else None;c.state={'phase':'connected'}
    c.export_config=Mock()
    with pytest.raises(ValueError):c.command('switch-town',{'town':'Town02_Opt'})
    c.export_config.assert_not_called()


def test_switch_saves_old_scene_and_restarts_in_new_town(tmp_path,monkeypatch):
    import controller
    monkeypatch.setattr(controller,'DATA',tmp_path)
    timer=Mock();monkeypatch.setattr(controller.threading,'Timer',timer)
    c=Controller.__new__(Controller)
    c.world=object();c.running=False;c.recording=None;c.mode='live';c.proc=object()
    c.state={'phase':'connected'};c.last_gpus='0,1,2,3';c.gpu_profile='2'
    c.wmap=SimpleNamespace(name='Carla/Maps/Town10HD_Opt')
    c.export_config=Mock(return_value={'map':c.wmap.name,'actors':[{'id':10}]})
    result=c.command('switch-town',{'town':'Town02_Opt'})
    import json
    request=json.loads((tmp_path/'restart-live-request.json').read_text())
    assert request['town']=='/Game/Carla/Maps/Town02_Opt'
    assert request['gpus']=='0,1,2,3'
    assert request['gpu_profile']=='2'
    assert 'configuration' not in request, 'Do not spawn old coordinates in a new town'
    assert json.loads(Path(result['saved_configuration']).read_text())['actors']==[{'id':10}]
    assert c.state['phase']=='restarting'
    timer.return_value.start.assert_called_once()


def test_late_gpu_workers_use_same_town_as_primary():
    import os
    path=Path(os.environ.get('CARLA_MULTIGPU_LAUNCHER', '/mnt/simulations/carla/carlab/host-setup/scripts/carla-multigpu.py'))
    spec=importlib.util.spec_from_file_location('town_launcher',path)
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    commands=launcher.commands([3,2,1,0],2000,'gpu','/Game/Carla/Maps/Town02_Opt')
    assert len(commands)==5
    for role,args in commands:
        assert args[1]=='/Game/Carla/Maps/Town02_Opt'
        if role!='primary':
            assert '-quality-level=High' in args
            assert '-ini:Engine:[DevOptions.Shaders]:bAllowAsynchronousShaderCompiling=False' in args
            assert any(arg.startswith('-ShaderWorkingDir=') for arg in args)


def test_native_replay_rejects_another_town_before_clearing_scene(tmp_path):
    import json
    (tmp_path/'manifest.json').write_text(json.dumps({'status':'complete','map':'Carla/Maps/Town01_Opt'}))
    c=Controller.__new__(Controller)
    c.world=object();c.running=False;c.recording=None;c.mode='live';c.proc=object()
    c.state={'phase':'connected'};c.wmap=SimpleNamespace(name='Carla/Maps/Town02_Opt')
    c.session=Mock(return_value=tmp_path);c.schedule=Mock();c.clear_managed=Mock()
    with pytest.raises(ValueError,match='Switch to Town01_Opt'):
        c.command('replay-native',{'id':'test'})
    c.schedule.stop.assert_not_called();c.clear_managed.assert_not_called()
