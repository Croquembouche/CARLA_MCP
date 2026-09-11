import json,time,httpx
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'data/movement-verification'
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
state=c.get('/api/status').json();assert not state.get('recording')
config=c.get('/api/configuration').json();(out/'before-replay-config.json').write_text(json.dumps(config,indent=2))
rec=json.loads((out/'report.json').read_text())['recording']['id'];raw=[json.loads(x) for x in (root/'data/recordings'/rec/'states.jsonl').read_text().splitlines()]
expected={next(a['movement_word'] for a in s['actors'] if a['id']==8) for s in raw}
result=cmd('replay-native',{'id':rec});cmd('pause');seen=[]
for i in range(22):
 cmd('step');s=c.get('/api/status').json();a=next(a for a in s['actors'] if a['id']==8)
 seen.append({'frame':s['frame'],'word':a['movement_word'],'movements':a['movements']})
assert expected<={s['word'] for s in seen},(expected,seen)
report={'result':'passed','recording':rec,'native_replay_response':result,'expected_words':sorted(expected),'observed_words':sorted({s['word'] for s in seen}),'samples':seen}
(out/'replay-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
