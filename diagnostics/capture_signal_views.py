import sys,queue,json,math
sys.path.insert(0,'/mnt/simulations/control-center')
import bootstrap,carla,httpx
import numpy as np
from PIL import Image
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
client=carla.Client('127.0.0.1',2000);client.set_timeout(120);world=client.get_world();s=c.get('/api/status').json();head=next(a for a in s['actors'] if a['id']==8)['heads'][0]
print('HEAD',head,flush=True);cams=[]
try:
 for i,(dx,dy,yaw) in enumerate([(8,0,180),(-8,0,0),(0,8,-90),(0,-8,90)]):
  bp=world.get_blueprint_library().find('sensor.camera.rgb')
  for k,v in {'image_size_x':'640','image_size_y':'360','fov':'60'}.items():bp.set_attribute(k,v)
  camera=world.spawn_actor(bp,carla.Transform(carla.Location(x=head['x']+dx,y=head['y']+dy,z=head['z']),carla.Rotation(yaw=yaw)))
  q=queue.Queue();camera.listen(q.put);cams.append((camera,q))
 for j in range(12):
  fr=cmd('step')['frame']
  for i,(cam,q) in enumerate(cams):
   while True:
    d=q.get(timeout=90)
    if d.frame>=fr:break
   if j in (5,11):
    im=Image.fromarray(np.frombuffer(d.raw_data,dtype=np.uint8).reshape(d.height,d.width,4)[:,:,[2,1,0]])
    im.save(f'/mnt/simulations/control-center/data/movement-verification/compass-{i}-{j}.png')
    print(i,j,'actor',cam.get_transform(),'image',d.transform,flush=True)
finally:
 for a,q in cams:a.stop();a.destroy()
