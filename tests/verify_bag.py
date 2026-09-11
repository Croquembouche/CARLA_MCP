import sys,json,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
import numpy as np
root=Path(__file__).resolve().parents[1]; report=json.loads((root/'data/live-workflow-report.json').read_text());session=root/'data/recordings'/report['session']
reader=rosbag2_py.SequentialReader();reader.open(rosbag2_py.StorageOptions(uri=str(session/'rosbag2'),storage_id='sqlite3'),rosbag2_py.ConverterOptions(input_serialization_format='cdr',output_serialization_format='cdr'))
types={t.name:t.type for t in reader.get_all_topics_and_types()};counts=collections.Counter();first={}
while reader.has_next():
 topic,raw,stamp=reader.read_next();msg=deserialize_message(raw,get_message(types[topic]));counts[topic]+=1
 if topic not in first:first[topic]=(msg,stamp)
assert dict(counts)==report['ros_topics']
frame=json.loads((session/'states.jsonl').read_text().splitlines()[0])
for s in frame['sensor_files']:
 prefix=f'/carla/ego_{s["parent"]}/{s["name"]}'
 if s['type']=='sensor.camera.rgb':assert bytes(first[prefix+'/image'][0].data)==(session/s['path']).read_bytes()
 if s['type']=='sensor.lidar.ray_cast':
  raw=np.frombuffer((session/s['path']).read_bytes(),dtype='<f4').reshape(-1,4).copy();raw[:,1]*=-1
  assert np.array_equal(np.frombuffer(bytes(first[prefix+'/points'][0].data),dtype='<f4').reshape(-1,4),raw)
 assert first[prefix+('/image' if 'camera' in s['type'] else '/points' if ('lidar' in s['type'] or 'radar' in s['type']) else '/data')][1]==round(s['timestamp']*1e9)
result={'passed':True,'total_messages':sum(counts.values()),'topics':dict(counts),'camera_original_bytes':'identical','lidar_coordinate_conversion':'exact','timestamps':'matched sensor simulation timestamps'}
(root/'data/rosbag-readback-report.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
