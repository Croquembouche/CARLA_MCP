"""Exercise real junction holds, timing changes, cycle progression and capture."""
import json,time,httpx
from pathlib import Path
root=Path(__file__).resolve().parents[1];c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(op,p={}):
 r=c.post('/api/command/'+op,json=p);r.raise_for_status();return r.json()
def state():return c.get('/api/status').json()
def lights():return {a['id']:a for a in state()['actors'] if a['type'].startswith('traffic.traffic_light')}
original=lights();assert len(original)>=10;aid=min(original);group=set(original[aid]['group_ids']);outside=set(original)-group;assert outside
report={'selected':aid,'group':sorted(group),'outside':sorted(outside),'states':{},'timings':{},'cycle_states':[]}
try:
 for name in ['Green','Yellow','Red','Off']:
  cmd('traffic-light',{'id':aid,'operation':'state','state':name,'hold':True});s=lights();assert s[aid]['state']==name and all(s[i]['frozen'] for i in group);assert all(s[i]['state']=='Red' for i in group-{aid});assert all(s[i]['frozen']==original[i]['frozen'] for i in outside);report['states'][name]='passed'
 # Held signal stays fixed while other intersections advance through simulation time.
 outside_elapsed={i:lights()[i]['elapsed'] for i in outside}
 for _ in range(5):cmd('step')
 s=lights();assert s[aid]['state']=='Off';assert any(abs(s[i]['elapsed']-outside_elapsed[i])>.05 for i in outside)
 cmd('traffic-light',{'id':aid,'operation':'timing','scope':'intersection','green_time':.3,'yellow_time':.2,'red_time':.2});s=lights()
 for i in group:
  assert not s[i]['frozen'];assert abs(s[i]['green_time']-.3)<1e-5 and abs(s[i]['yellow_time']-.2)<1e-5 and abs(s[i]['red_time']-.2)<1e-5
 for i in outside:
  for field in ['green_time','yellow_time','red_time']:assert s[i][field]==original[i][field]
 report['timings']='applied only to selected intersection'
 seen=set()
 for _ in range(60):cmd('step');seen.update(a['state'] for i,a in lights().items() if i in group)
 assert {'Green','Yellow','Red'}<=seen;report['cycle_states']=sorted(seen)
 cmd('traffic-light',{'id':aid,'operation':'state','state':'Green','hold':True})
 rec=cmd('record-start',{'rosbag':True});cmd('step');cmd('step');stopped=cmd('record-stop');sid=rec['id']
 f=c.get(f'/api/sessions/{sid}/frame/0').json();signal=next(a for a in f['actors'] if a['id']==aid);assert signal['state']=='Green' and signal['frozen'] and abs(signal['green_time']-.3)<1e-5
 report['recording']={'id':sid,'frames':2,'signalState':signal['state'],'frozen':signal['frozen'],'rosbag':True}
finally:
 if state().get('recording'):cmd('record-stop')
 for i in group:
  a=original[i];cmd('traffic-light',{'id':i,'operation':'timing','scope':'signal',**{k:a[k] for k in ['green_time','yellow_time','red_time']}})
 # Restore the prior displayed states; normal cycling remains enabled.
 for i in group:cmd('traffic-light',{'id':i,'operation':'state','state':original[i]['state'],'hold':False})
 cmd('pause')
report['result']='passed';(root/'data/signal-controls-live-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
