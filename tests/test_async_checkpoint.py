import copy,json,threading,time
from types import SimpleNamespace
from unittest.mock import patch
import pytest
import reliability,recording

def owner(tmp_path):
    config={'actors':[{'spawn':{'x':1}}]}
    return SimpleNamespace(mode='live',worker_fault=None,resizing_workers=False,state={'frame':4,'time':.2,'recovery_operation':None},resource_data=tmp_path,export_config=lambda:config),config

def test_checkpoint_freezes_frame_and_keeps_only_one_pending_write(tmp_path):
    o,config=owner(tmp_path);entered=threading.Event();release=threading.Event();original=recording.dump
    def slow(path,value):
        entered.set();assert release.wait(5);original(path,value)
    with patch.object(recording,'dump',side_effect=slow) as writer:
        try:
            reliability.checkpoint(o);assert entered.wait(2)
            assert 'recovery_checkpoint' not in o.state
            o.state['frame']=8;config['actors'][0]['spawn']['x']=9;o.checkpoint_at=0
            reliability.checkpoint(o);assert writer.call_count==1
        finally:release.set();reliability.finish_checkpoint(o)
    saved=json.loads((tmp_path/'recovery-checkpoint.json').read_text())
    assert saved['frame']==4 and saved['configuration']['actors'][0]['spawn']['x']==1
    assert o.state['recovery_checkpoint']['frame']==4

def test_failed_checkpoint_preserves_previous_file_and_is_reported(tmp_path):
    o,_=owner(tmp_path);path=tmp_path/'recovery-checkpoint.json';path.write_text('{"frame":2}')
    with patch.object(recording,'dump',side_effect=OSError('disk failure')):
        reliability.checkpoint(o)
        with pytest.raises(OSError,match='disk failure'):reliability.finish_checkpoint(o)
    assert json.loads(path.read_text())=={'frame':2}
    assert 'recovery_checkpoint' not in o.state

@pytest.mark.parametrize('had_checkpoint',[False,True])
def test_cleanup_ticks_do_not_restart_closed_writer(tmp_path,had_checkpoint):
    o,_=owner(tmp_path)
    if had_checkpoint:reliability.checkpoint(o)
    reliability.finish_checkpoint(o)
    o.checkpoint_at=0
    with patch.object(recording,'dump') as writer:
        reliability.checkpoint(o)
        writer.assert_not_called()
