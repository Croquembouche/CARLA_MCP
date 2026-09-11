import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
from controller import Controller
from types import SimpleNamespace
from unittest.mock import Mock

def test_removed_background_does_not_keep_stale_handle():
 c=object.__new__(Controller);actor=Mock();sensor=Mock();c.world=SimpleNamespace(get_actors=lambda:[SimpleNamespace(id=25),SimpleNamespace(id=31)],get_snapshot=lambda:SimpleNamespace(has_actor=lambda aid:aid==25))
 c.managed={25:{'controller':None},31:{'controller':None},99:{'controller':None}}
 c.state={'frame':200,'managed':{'25':{},'31':{}}};c.sensors={40:{'parent':31,'actor':sensor}};c.previews={40:b'old'};c.ros=Mock()
 c.prune_removed_actors()
 assert set(c.managed)=={25,99} # A just-spawned actor is not published until its first tick.
 assert not c.sensors and not c.previews
 assert c.state['removed_actors']==[{'id':31,'frame':200,'reason':'Actor removed by simulator'}]
 sensor.stop.assert_called_once();sensor.destroy.assert_called_once()
 c.prune_removed_actors();assert len(c.state['removed_actors'])==1

def test_export_uses_published_poses_without_reading_removed_handles():
 c=object.__new__(Controller);a=Mock(type_id='vehicle.test');a.get_transform.side_effect=RuntimeError('removed')
 c.state={'map':'test','actors':[{'id':25,'type':'vehicle.test','pose':{'x':1,'y':2,'z':0}}]};c.schedule=Mock();c.schedule.snapshot.return_value={};c.movements=None;c.sensors={}
 c.managed={i:{'actor':a,'role':'background','planner':'tm','destination':None} for i in [25,31]}
 config=c.export_config();assert [a['id'] for a in config['actors']]==[25];assert config['actors'][0]['spawn']=={'x':1,'y':2,'z':0};a.get_transform.assert_not_called()
