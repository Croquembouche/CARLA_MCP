"""Real arrows on four render workers; synchronized native, JSON and ROS capture."""
import sys,json,time,queue,math,struct,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,carla,httpx
import numpy as np
from PIL import Image
from rclpy.serialization import deserialize_message
from std_msgs.msg import String
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/movement-verification';OUT.mkdir(exist_ok=True)
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
def state():return c.get('/api/status').json()
def step():cmd('step');return state()
def light(s,aid=8):return next(a for a in s['actors'] if a['id']==aid)
client=carla.Client('127.0.0.1',2000);client.set_timeout(120);world=client.get_world()
report={};cameras=[];qs=[]
try:
 cmd('pause');initial=state();a=light(initial);assert len(a['heads'])==3;assert len(a['pedestrian_heads'])==1
 report['topology']={'vehicle_heads':sum(len(a.get('heads',[])) for a in initial['actors']),'pedestrian_heads':sum(len(a.get('pedestrian_heads',[])) for a in initial['actors'])}
 payload={'group_id':8,'operation':'enable','yellow_time':.5,'all_red_time':.5,'phases':[{'name':'Permissive left / protected through','duration':60,'states':{'8':{'left':'Permissive','straight':'Protected'}}}]}
 cmd('movement-program',payload)
 for _ in range(30):
  s=step()
  if s['movement_programs']['8']['stage']=='green':break
 assert light(s)['movements']['left']=='Permissive';cmd('movement-program',{'group_id':8,'operation':'hold'})
 head=a['heads'][0]
 for i in range(4):
  bp=world.get_blueprint_library().find('sensor.camera.rgb')
  for k,v in {'image_size_x':'640','image_size_y':'360','fov':'45','sensor_tick':'0.0'}.items():bp.set_attribute(k,v)
  camera=world.spawn_actor(bp,carla.Transform(carla.Location(x=head['x']+12,y=head['y'],z=head['z']),carla.Rotation(yaw=180)))
  q=queue.Queue();camera.listen(q.put);cameras.append(camera);qs.append(q)
 def capture(s):
  images=[]
  for q in qs:
   while True:
    d=q.get(timeout=90)
    if d.frame>=s['frame']:break
   assert d.frame==s['frame'];images.append(d)
  return images
 for _ in range(10):s=step();images=capture(s)
 rec=cmd('record-start',{'rosbag':True});records=[];seen={}
 for _ in range(24):
  s=step();images=capture(s);word=light(s)['movement_word'];records.append({'frame':s['frame'],'word':word})
  phase='on' if word&0x4000 else 'off'
  if True:
   seen[phase]=[]
   for i,d in enumerate(images):
    im=Image.fromarray(np.frombuffer(d.raw_data,dtype=np.uint8).reshape(d.height,d.width,4)[:,:,[2,1,0]])
    path=OUT/f'worker-{i}-arrows-{phase}.png';im.save(path);seen[phase].append(str(path))
 stopped=cmd('record-stop');assert stopped['frames']==24
 for camera in cameras:camera.stop();camera.destroy()
 cameras=[]
 assert set(seen)=={'on','off'}
 report['camera_images']=seen
 checks=[]
 for i in range(4):
  on=np.asarray(Image.open(seen['on'][i])).astype(float);off=np.asarray(Image.open(seen['off'][i])).astype(float)
  def yellow(im):
   p=im[158:202,278:313];return int(((p[:,:,0]>100)&(p[:,:,1]>60)&(p[:,:,2]<p[:,:,0]*.7)).sum())
  p=on[158:202,309:332];green=int(((p[:,:,1]>90)&(p[:,:,0]<p[:,:,1]*.85)&(p[:,:,2]<p[:,:,1]*.9)).sum())
  check={'stream':i,'yellow_on':yellow(on),'yellow_off':yellow(off),'protected_green':green};checks.append(check)
  assert check['yellow_on']>check['yellow_off']+5 and green>5,check
 report['camera_pixel_checks']=checks
 session=ROOT/'data/recordings'/rec['id'];raw=[json.loads(x) for x in (session/'states.jsonl').read_text().splitlines()]
 assert [light(x)['movement_word'] for x in raw]==[x['word'] for x in records]
 con=sqlite3.connect(session/'rosbag2/rosbag2_0.db3')
 rows=con.execute("select timestamp,data from messages where topic_id=(select id from topics where name='/carla/traffic_signals') order by timestamp").fetchall()
 decoded=[json.loads(deserialize_message(data,String).data) for ts,data in rows]
 assert [next(a['movement_word'] for a in x['signals'] if a['id']==8) for x in decoded]==[x['word'] for x in records]
 assert [ts for ts,data in rows]==[round(x['time']*1e9) for x in raw]
 f=(session/'carla.log').open('rb')
 def read(fmt):return struct.unpack(fmt,f.read(struct.calcsize(fmt)))[0]
 def string():return f.read(read('<H'))
 version=read('<H');magic=string();date=read('<q');mapname=string();packets=[]
 while head:=f.read(5):
  pid,size=struct.unpack('<BI',head);data=f.read(size)
  if pid==25:
   n=struct.unpack_from('<H',data)[0];packets.append(dict(struct.unpack_from('<IH',data,2+i*6) for i in range(n)))
 assert len(packets)==24 and [p[8] for p in packets]==[x['word'] for x in records]
 report['recording']={'id':rec['id'],'frames':24,'native_movement_packets':len(packets),'ros_messages':len(rows),'exact_words_and_timestamps':True,'original_ego_sensors':len(raw[0]['sensor_files'])}
 report['result']='passed';(OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
finally:
 if state().get('recording'):cmd('record-stop')
 for camera in cameras:
  try:camera.stop();camera.destroy()
  except:pass
 cmd('pause')
