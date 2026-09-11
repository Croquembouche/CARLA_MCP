import json,httpx,math
from pathlib import Path
root=Path(__file__).resolve().parent;c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=30,headers={'X-Control-Client':'carla-control-center'});s=c.get('/api/status').json();assert s['recovery_operation']['stage']=='ready' and not s['error'];cfg=c.get('/api/configuration').json();m=c.get('/api/map').json();old=json.loads((root/'parked-configuration.json').read_text());before=json.loads((root/'restore-configuration.json').read_text());ego=next(a for a in cfg['actors'] if a['role']=='ego');old_ego=next(a for a in old['actors'] if a['role']=='ego');managed=s['managed'][str(ego['id'])]
assert len(cfg['actors'])==28 and len(s['sensors'])==6;assert ego['planner']=='tm' and ego['parked'] and ego['parking_space']=='P024';assert ego['sensors']==old_ego['sensors'];assert managed['parking_trip']['stage']=='parked';assert cfg['weather']==old['weather']==before['weather'];assert len(s['scene_vehicles']['removed'])==13
assert not any(a.get('scene_source') in {'BP_Carlacola_Parked_C_7','BP_Carlacola_Parked_C_9','BP_EuropeanHGV_Parked_C_8'} for a in cfg['actors'])
a=next(a for a in s['actors'] if a['id']==ego['id']);bay=next(b for b in m['parking_spaces'] if b['id']=='P024');heading=math.radians(a['pose']['yaw']);angle=math.radians(bay['yaw']);x,y=a['pose']['x'],a['pose']['y'];ex,ey=a['extent']['x'],a['extent']['y'];corners=[(x+u*math.cos(heading)-v*math.sin(heading),y+u*math.sin(heading)+v*math.cos(heading)) for u,v in [(-ex,-ey),(ex,-ey),(ex,ey),(-ex,ey)]]
assert all(abs((px-bay['x'])*math.cos(angle)+(py-bay['y'])*math.sin(angle))<=bay['length']/2 and abs(-(px-bay['x'])*math.sin(angle)+(py-bay['y'])*math.cos(angle))<=bay['width']/2 for px,py in corners)
assert s['parking']['occupied']['P024']['id']==ego['id']
if json.loads((root/'pre-deploy-status.json').read_text())['running']:
 r=c.post('/api/command/run',json={});r.raise_for_status()
s=c.get('/api/status').json();report=dict(ego=ego['id'],role=ego['role'],planner=ego['planner'],bay='P024',parked=True,footprint_inside_bay=True,parking_survived_restart=True,six_sensors_preserved=True,weather_preserved=True,actor_count=28,removed_trucks_still_absent=True,running=s['running'],error=s['error'])
(root/'final-verification.json').write_text(json.dumps(report,indent=2));(root/'final-configuration.json').write_text(json.dumps(cfg,indent=2));print(json.dumps(report,indent=2))
