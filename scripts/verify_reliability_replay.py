"""Measure native actor/light replay against captured states, without regenerating sensors."""
import json,math,itertools,httpx
from pathlib import Path
root=Path(__file__).resolve().parents[1];data=root/'data';capture=json.loads((data/'reliability-capture-live.json').read_text());sid=capture['recording']['id'];path=data/'recordings'/sid
recorded=[json.loads(line) for line in (path/'states.jsonl').read_text().splitlines()]
config=json.loads((path/'configuration.json').read_text());ids={a['id'] for a in config['actors']}
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
cmd('replay-native',{'id':sid,'autoplay':False});observed=[]
for _ in recorded:
 cmd('step');observed.append(c.get('/api/status').json())
def distance(a,b):return math.dist([a['pose'][k] for k in ('x','y','z')],[b['pose'][k] for k in ('x','y','z')])
original=[a for a in recorded[0]['actors'] if a['id'] in ids];replayed=[a for a in observed[0]['actors'] if a['type'].startswith(('vehicle.','walker.pedestrian.'))]
assert len(original)==len(replayed)
matches=min((p for p in itertools.permutations(replayed) if all(a['type']==b['type'] for a,b in zip(original,p))),key=lambda p:sum(distance(a,b) for a,b in zip(original,p)))
mapping={a['id']:b['id'] for a,b in zip(original,matches)};errors=[];yaws=[];signal_errors=0;frame_errors=[]
for index,(ra,rb) in enumerate(zip(recorded,observed)):
 actual={a['id']:a for a in rb['actors']}
 for a in ra['actors']:
  if a['id'] in mapping:
   b=actual[mapping[a['id']]];error=distance(a,b);errors.append(error);frame_errors.append({'row':index,'actor':a['id'],'position_error_m':error});yaws.append(abs((a['pose']['yaw']-b['pose']['yaw']+180)%360-180))
 lights=lambda row:{a.get('opendrive_id',a['id']):(a['state'],a.get('movement_word')) for a in row['actors'] if a['type']=='traffic.traffic_light'}
 signal_errors+=lights(ra)!=lights(rb)
report={'recording':sid,'frames':len(observed),'actor_mapping':mapping,'position_max_m':max(errors),'position_rms_m':math.sqrt(sum(x*x for x in errors)/len(errors)),'yaw_max_deg':max(yaws),'largest_errors':sorted(frame_errors,key=lambda x:x['position_error_m'],reverse=True)[:10],'signal_mismatch_frames':signal_errors,'scope':'Native replay actor poses and signal states at matching relative frames; original sensor bytes are separately integrity-verified'}
report['passed']=report['position_max_m']<.05 and report['yaw_max_deg']<.5 and not signal_errors
(data/'reliability-native-replay.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True);assert report['passed'],report
