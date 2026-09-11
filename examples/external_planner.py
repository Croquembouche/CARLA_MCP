"""Minimal pure-pursuit API example; replace plan() with your own planning stack."""
import argparse,math,time
import httpx

def plan(actor,managed):
    goal=managed.get('destination');route=managed.get('route',[]);p=actor['pose']
    if not goal or not route or math.hypot(goal['x']-p['x'],goal['y']-p['y'])<3:return {'brake':1.,'throttle':0.,'steer':0.}
    nearest=min(range(len(route)),key=lambda i:math.hypot(route[i]['x']-p['x'],route[i]['y']-p['y']))
    target=route[-1]
    for wp in route[nearest:]:
        if math.hypot(wp['x']-p['x'],wp['y']-p['y'])>=8:target=wp;break
    alpha=math.atan2(target['y']-p['y'],target['x']-p['x'])-math.radians(p['yaw'])
    steer=max(-1.,min(1.,math.atan2(2*2.8*math.sin(alpha),8)/math.radians(35)))
    v=actor['velocity'];speed=math.hypot(v['x'],v['y']);error=5-speed
    return {'steer':steer,'throttle':max(0.,min(.5,error*.15)),'brake':max(0.,min(1.,-error*.15))}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',default='http://128.175.213.232:8095');p.add_argument('--vehicle-id',required=True,type=int);a=p.parse_args()
    with httpx.Client(base_url=a.url,timeout=15,headers={'X-Control-Client':'carla-control-center'}) as client:
        try:
            while True:
                r=client.get('/api/status');r.raise_for_status();s=r.json();m=s['managed'].get(str(a.vehicle_id))
                if not m or m['role']!='ego' or m['planner']!='external':raise RuntimeError('Select an existing ego using the External planning algorithm policy')
                actor=next(v for v in s['actors'] if v['id']==a.vehicle_id)
                r=client.post('/api/command/control',json={'id':a.vehicle_id,**plan(actor,m)});r.raise_for_status();time.sleep(.05)
        except KeyboardInterrupt:pass
        finally:
            try:client.post('/api/command/control',json={'id':a.vehicle_id,'brake':1.})
            except httpx.HTTPError:pass
