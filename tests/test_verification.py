import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from types import SimpleNamespace
from recording import Recording
from verification import verify_session,compare_sessions

def record(root):
 c=SimpleNamespace(start_recorder=lambda *a:'ok',stop_recorder=lambda:None);r=SimpleNamespace(stop_bag=lambda:{})
 config={'actors':[{'id':1,'role':'ego','model':'vehicle.test','sensors':[{'name':'imu'}]}],'fixed_delta_seconds':.05}
 rec=Recording(root,c,r,config,{'name':'test'},'map',False)
 for frame in (1,2):
  sample={'data':SimpleNamespace(raw_data=b'abc',frame=frame,timestamp=frame*.05),'type':'test','parent':1,'config':{'name':'imu','attributes':{}},'pose':{}}
  rec.write({'frame':frame,'time':frame*.05,'actors':[{'id':1,'type':'vehicle.test','pose':{'x':frame,'y':0,'z':0,'yaw':0}}]},[sample])
 rec.close();return rec.path

def test_complete_seal_and_sensor_corruption(tmp_path):
 p=record(tmp_path);assert verify_session(p)['status']=='verified'
 next((p/'sensors').rglob('*.bin')).write_bytes(b'bad')
 assert verify_session(p)['status']=='failed'

def test_frame_index_corruption_and_legacy_are_not_verified(tmp_path):
 p=record(tmp_path);(p/'frames.idx').write_bytes(b'123')
 assert verify_session(p)['status']=='failed'

def test_replay_comparison_reports_trajectory_deviation(tmp_path):
 a=record(tmp_path);b=record(tmp_path)
 assert compare_sessions(a,b)['trajectory_pass']
 rows=[json.loads(l) for l in (b/'states.jsonl').read_text().splitlines()];rows[1]['actors'][0]['pose']['x']+=1
 (b/'states.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 report=compare_sessions(a,b);assert not report['trajectory_pass'] and report['position_max_m']==1

def test_rosbag_contents_must_match_sealed_manifest_counts(tmp_path):
 import sqlite3
 from verification import seal
 p=record(tmp_path);bag=p/'rosbag2';bag.mkdir()
 with sqlite3.connect(bag/'test.db3') as db:
  db.executescript('CREATE TABLE topics(id INTEGER,name TEXT); CREATE TABLE messages(id INTEGER,topic_id INTEGER); INSERT INTO topics VALUES(1,"/clock"); INSERT INTO messages VALUES(1,1),(2,1);')
 manifest=json.loads((p/'manifest.json').read_text());manifest.update(rosbag=True,ros_topics={'/clock':2});(p/'manifest.json').write_text(json.dumps(manifest));seal(p)
 assert verify_session(p)['status']=='verified'
 manifest['ros_topics']['/clock']=1;(p/'manifest.json').write_text(json.dumps(manifest))
 assert verify_session(p)['status']=='failed'
