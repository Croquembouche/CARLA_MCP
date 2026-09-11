"""Check target intersection entry; several spawn paths start in a different upstream junction."""
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import bootstrap,carla
c=carla.Client('127.0.0.1',2000);c.set_timeout(10);wm=c.get_world().get_map();s=json.loads((root/'data/optimization-before.json').read_text());out=root/'data/signal-stop-audit';report=json.loads((out/'report.json').read_text())
for r in report:
 a=next(a for a in s['actors'] if a['id']==r['light']);path=a['movement_lanes'][r['movement']]['paths'][0]
 def wp(p):return wm.get_waypoint(carla.Location(x=p[0],y=p[1],z=p[2] if len(p)>2 else 0))
 target={wp(p).junction_id for p in path if wp(p).is_junction};assert target
 trace=json.loads((out/f"{r['light']}-{r['movement']}.json").read_text())
 for p in trace:p['junction_id']=wp(p['xy']).junction_id
 r['started_in_other_junction']=trace[0]['junction'] and trace[0]['junction_id'] not in target
 r['entered_target_junction']=any(p['junction'] and p['junction_id'] in target for p in trace)
 r['target_junction_ids']=sorted(target);r['pass']=r['stopped_at_expected_light'] and not r['entered_target_junction'];r.pop('entered_junction',None)
 (out/f"{r['light']}-{r['movement']}.json").write_text(json.dumps(trace))
(out/'report.json').write_text(json.dumps(report,indent=2));print('Correct target-junction checks:',sum(r['pass'] for r in report),'/',len(report));print([r for r in report if not r['pass']]);assert len(report)==34 and all(r['pass'] for r in report)
