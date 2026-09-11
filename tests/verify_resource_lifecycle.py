import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import bootstrap,carla,httpx
h=httpx.Client(base_url='http://127.0.0.1:8095',timeout=120,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=h.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
c=carla.Client('127.0.0.1',2000);c.set_timeout(10);w=c.get_world();m=h.get('/api/map').json();s=h.get('/api/status').json();assert not s['managed']
aid=cmd('spawn',{'role':'ego','planner':'tm','model':'vehicle.lincoln.mkz','spawn':m['spawn_points'][0]})['id'];s=h.get('/api/status').json();assert str(aid) in s['managed'];assert not s['sensors']
w.get_actor(aid).destroy();h.get('/api/configuration').raise_for_status()
for ticks in range(1,4):
 cmd('step');s=h.get('/api/status').json();assert s['phase']=='connected' and not s['error']
 if str(aid) not in s['managed']:break
assert str(aid) not in s['managed'];assert s['removed_actors'][-1]['id']==aid
r={'new_ego_sensor_count':0,'configuration_export_after_native_removal':'passed','removed_actor_cleanup':'passed','ticks_to_cleanup':ticks,'test_actor':aid};(root/'data/resource-lifecycle-live.json').write_text(json.dumps(r,indent=2));print(r,flush=True)
