import sys,json,time,threading
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reliability import watch_workers

def test_missing_worker_stops_run_and_preserves_last_frame(tmp_path):
 p=tmp_path/'processes.json';p.write_text(json.dumps({'children':[{'pid':999999999,'role':'gpu-3'}]}))
 owner=SimpleNamespace(stop_event=threading.Event(),worker_manifest=p,resizing_workers=False,worker_fault=None,running=True,resource_data=tmp_path,state={'phase':'connected','frame':42})
 t=threading.Thread(target=watch_workers,args=(owner,));t.start()
 try:
  deadline=time.monotonic()+3
  while not owner.worker_fault and time.monotonic()<deadline:time.sleep(.02)
  assert owner.worker_fault and not owner.running
  assert owner.state['worker_health']['last_complete_frame']==42
 finally:owner.stop_event.set();t.join(2)

def test_partial_recovery_does_not_overwrite_checkpoint(tmp_path):
 from reliability import checkpoint
 saved=tmp_path/'recovery-checkpoint.json';saved.write_text('saved full scene')
 owner=SimpleNamespace(mode='live',worker_fault=None,resizing_workers=False,state={'recovery_operation':{'stage':'restoring'}},resource_data=tmp_path)
 checkpoint(owner)
 assert saved.read_text()=='saved full scene'
