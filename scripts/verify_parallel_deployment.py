import httpx,time,subprocess,json
from pathlib import Path
root=Path('/mnt/simulations/control-center')
c=httpx.Client(timeout=2000,headers={'X-Control-Client':'carla-control-center'})
for _ in range(180):
 try:
  s=c.get('http://127.0.0.1:8095/api/status',timeout=5).json()
  if s['phase']=='connected':break
  if s.get('error'):raise RuntimeError(s['error'])
 except httpx.HTTPError:pass
 time.sleep(1)
else:raise RuntimeError('Scene did not connect')
subprocess.run([str(root/'.venv/bin/python'),str(root/'scripts/restore_parallel_scenario.py')],check=True)
print('STARTING_BENCHMARK',flush=True)
r=c.post('http://127.0.0.1:8095/api/command/gpu-benchmark',json={})
if r.is_error:raise RuntimeError(r.text)
(root/'data/parallel-benchmark-result.json').write_text(json.dumps(r.json(),indent=2))
print('BENCHMARK_COMPLETE',r.json()['selected_workers'],flush=True)
subprocess.run([str(root/'.venv/bin/python'),str(root/'tests/verify_parallel_pool.py')],check=True)
print('PARALLEL_ACCEPTANCE_COMPLETE',flush=True)
