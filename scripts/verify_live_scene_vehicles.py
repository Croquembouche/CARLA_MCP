"""Validate restored actors and a short complete recording on the paused UI scene."""
import json,math,sys
from pathlib import Path
import httpx,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verification import verify_session
root=Path(__file__).resolve().parents[1];c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
s=c.get('/api/status').json();old=json.loads((root/'data/parking/before-configuration.json').read_text());cfg=c.get('/api/configuration').json()
assert s['phase']=='connected' and not s['running'] and not s['recording']
assert len(s['managed'])==51 and len(s['sensors'])==5 and s['scene_vehicles']['remaining']==0
assert cfg['weather']==old['weather']
original=[a for a in cfg['actors'] if not a.get('scene_source')]
assert len(original)==len(old['actors'])
for a,b in zip(original,old['actors']):
    assert (a['role'],a['model'],a['sensors'])==(b['role'],b['model'],b['sensors'])
    assert math.dist([a['destination'][k] for k in ('x','y','z')],[b['destination'][k] for k in ('x','y','z')])<.001
(root/'data/scene-vehicles/restored-configuration.json').write_text(json.dumps(cfg,indent=2))
r=c.post('/api/command/record-start',json={'rosbag':True});r.raise_for_status();sid=r.json()['id'];print('STARTED',sid,flush=True)
try:
    for _ in range(5):c.post('/api/command/step',json={}).raise_for_status()
finally:
    r=c.post('/api/command/record-stop',json={});r.raise_for_status()
path=root/'data/recordings'/sid;report=verify_session(path)
assert report['status']=='verified',report
rows=[json.loads(line) for line in (path/'states.jsonl').read_text().splitlines()]
report['sensor_payloads']={}
for sample in rows[-1]['sensor_files']:
    if sample['type'].startswith('sensor.lidar.') or sample['type']=='sensor.other.radar':
        points=np.fromfile(path/sample['path'],dtype=np.float32).reshape(-1,4)
        assert len(points)>0 and np.isfinite(points).all()
        report['sensor_payloads'][sample['name']]={'detections':len(points),'finite':True}
    if sample['type']=='sensor.camera.rgb':
        pixels=np.fromfile(path/sample['path'],dtype=np.uint8).reshape(sample['height'],sample['width'],4)
        assert pixels[:,:,:3].std()>2
        report['sensor_payloads'][sample['name']]={'width':sample['width'],'height':sample['height'],'std':float(pixels[:,:,:3].std())}
for row in rows:
    assert len(row['managed'])==51
    assert len([a for a in row['actors'] if a['type']=='traffic.traffic_light'])==15
report['managed_actors_per_frame']=51;report['traffic_lights_per_frame']=15
(root/'data/scene-vehicles/live-recording-verification.json').write_text(json.dumps(report,indent=2))
# Keep acceptance captures with developer evidence, outside the user's Sessions list.
target=root/'data/scene-vehicles/live-acceptance-recording';assert not target.exists();path.rename(target)
s=c.get('/api/status').json();assert not s.get('error');(root/'data/scene-vehicles/restored-status.json').write_text(json.dumps(s,indent=2))
print(json.dumps(report,indent=2))
