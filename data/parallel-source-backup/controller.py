import authoring
import traffic_signals
from movement_signals import MovementPrograms, unpack
from lane_map import build_lanes, traffic_path
import bootstrap
import collections
import concurrent.futures
import io
import json
import math
import os
from pathlib import Path
import queue
import re
import signal
import socket
import subprocess
import threading
import time
import traceback
import carla
import numpy as np
from PIL import Image
from agents.navigation.global_route_planner import GlobalRoutePlanner
from recording import Recording, dump
from rosio import RosIO

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data';DATA.mkdir(exist_ok=True)
WEATHER=['cloudiness','precipitation','precipitation_deposits','wind_intensity','sun_azimuth_angle','sun_altitude_angle','fog_density','fog_distance','wetness','dust_storm','fog_falloff','scattering_intensity','mie_scattering_scale','rayleigh_scattering_scale']
SENSOR_TYPES=['sensor.camera.rgb','sensor.camera.depth','sensor.camera.semantic_segmentation','sensor.camera.instance_segmentation','sensor.camera.normals','sensor.camera.optical_flow','sensor.lidar.ray_cast','sensor.lidar.ray_cast_semantic','sensor.other.radar','sensor.other.imu','sensor.other.gnss']
DEFAULT_SENSORS=[{'name':'front_rgb','type':'sensor.camera.rgb','mount':{'x':1.5,'z':2.2},'attributes':{'image_size_x':'640','image_size_y':'360','fov':'90'}},
 {'name':'roof_lidar','type':'sensor.lidar.ray_cast','mount':{'z':2.5},'attributes':{'channels':'32','range':'80','points_per_second':'200000','rotation_frequency':'20'}},
 {'name':'front_radar','type':'sensor.other.radar','mount':{'x':2.0,'z':1.0},'attributes':{'range':'80','points_per_second':'10000'}},
 {'name':'imu','type':'sensor.other.imu','mount':{},'attributes':{}},{'name':'gnss','type':'sensor.other.gnss','mount':{},'attributes':{}}]


def xyz(v):return {'x':v.x,'y':v.y,'z':v.z}
def pose(t):return dict(xyz(t.location),yaw=t.rotation.yaw,pitch=t.rotation.pitch,roll=t.rotation.roll)
def transform(d):return carla.Transform(carla.Location(x=d.get('x',0),y=d.get('y',0),z=d.get('z',0)),carla.Rotation(pitch=d.get('pitch',0),yaw=d.get('yaw',0),roll=d.get('roll',0)))


def validate_loadout(configs):
    if not isinstance(configs,list) or len(configs)>16:raise ValueError('Use a list of at most 16 sensors per ego vehicle')
    names=set();result=[]
    for c in configs:
        name=c.get('name','')
        if not re.fullmatch('[a-z][a-z0-9_]{0,39}',name) or name in names:raise ValueError('Sensor names must be unique lowercase identifiers, maximum 40 characters')
        names.add(name)
        if c.get('type') not in SENSOR_TYPES:raise ValueError('Unsupported sensor type')
        mount={k:float(v) for k,v in c.get('mount',{}).items()}
        if any(k not in ('x','y','z','yaw','pitch','roll') or not math.isfinite(v) or abs(v)>360 for k,v in mount.items()):raise ValueError('Invalid sensor mount')
        attrs={str(k):str(v) for k,v in c.get('attributes',{}).items()}
        if 'sensor_tick' in attrs and float(attrs['sensor_tick']) not in (0.,.05):raise ValueError('This synchronized workspace captures every 0.05 s; sensor_tick must be 0 or 0.05')
        attrs['sensor_tick']='0.0'
        # Explicit resource limits keep accidental configurations reviewable.
        for k,lo,hi in [('image_size_x',16,1920),('image_size_y',16,1080),('points_per_second',1,2000000),('channels',1,128),('range',1,150),('fov',1,179)]:
            if k in attrs and not(lo<=float(attrs[k])<=hi):raise ValueError(f'{k} must be between {lo} and {hi}')
        result.append({'name':name,'type':c['type'],'mount':mount,'attributes':attrs})
    return result


class Controller:
    def __init__(self):
        self.commands=queue.Queue(maxsize=128);self.stop_event=threading.Event()
        self.state={'phase':'offline','running':False,'error':None,'actors':[],'managed':{},'sensors':[],'frame':0,'time':0,'recording':None,'map':None,'ros_domain':42}
        self.schedule=authoring.ScenarioSchedule(self.execute_scheduled,lambda aid:aid not in self.managed or self.managed[aid].get('arrived',False),lambda aid:self.delete(aid) if aid in self.managed else None);self.scheduled_walkers=[]
        self.movements=None;self.signal_metadata={};self.map_data=None;self.catalog={};self.previews={};self.managed={};self.sensors={};self.proc=None;self.log_handle=None
        self.client=None;self.world=None;self.tm=None;self.recording=None;self.ros=None;self.running=False;self.mode='live'
        self.thread=threading.Thread(target=self.loop,name='simulation-owner',daemon=True);self.thread.start()
        restart=DATA/'restart-live-request.json'
        if restart.exists():
            request=json.loads(restart.read_text());restart.unlink()
            if time.time()-request.get('created',0)<300:self.submit('start',{'gpus':request['gpus']})

    def submit(self,action,payload):
        f=concurrent.futures.Future()
        try:self.commands.put_nowait((action,payload,f))
        except queue.Full:f.set_exception(RuntimeError('Controller command queue is full'))
        return f

    def loop(self):
        try:self.ros=RosIO()
        except Exception as e:self.state['ros_error']=str(e)
        while not self.stop_event.is_set():
            try:
                action,payload,f=self.commands.get(timeout=0.001 if self.running else 0.05)
                if not f.cancelled():
                    try:
                        result=self.command(action,payload);self.state['error']=None;f.set_result(result)
                    except Exception as e:
                        traceback.print_exc();self.state['error']=str(e);f.set_exception(e)
            except queue.Empty:pass
            try:
                if self.state['phase']=='starting':self.poll_start()
                elif self.running and self.world:
                    started=time.monotonic();self.tick()
                    time.sleep(max(0,0.05-(time.monotonic()-started)))
                if self.proc and self.proc.poll() is not None and self.state['phase'] not in ('offline','error'):
                    raise RuntimeError('CARLA group exited; inspect data/simulator.log')
            except Exception as e:
                traceback.print_exc();self.fail(e)
        try:self.disconnect(stop_process=True)
        finally:
            if self.ros:self.ros.close()

    def command(self,action,p):
        if action=='start':
            if self.proc or self.world:raise ValueError('A simulator is already connected or starting')
            if not self.ros:raise RuntimeError('ROS initialization failed: '+self.state.get('ros_error',''))
            gpus=p.get('gpus','3')
            self.last_gpus=gpus
            if gpus not in ('0,1,2,3','3'):raise ValueError('Choose four GPUs or single GPU')
            self.log_handle=(DATA/'simulator.log').open('ab')
            env=os.environ.copy();env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
            self.proc=subprocess.Popen(['/mnt/simulations/bin/carla-multigpu','--gpus',gpus,'--port','2000','--backend','gpu'],stdout=self.log_handle,stderr=subprocess.STDOUT,start_new_session=True,env=env)
            self.started=time.monotonic();self.state.update(phase='starting',error=None,worker_count=len(gpus.split(',')),gpu_selection=gpus)
            return {'started':True}
        if action=='connect':
            if self.world:raise ValueError('Already connected')
            self.connect();return {'connected':True}
        if action=='shutdown':self.disconnect(stop_process=True);return {'stopped':True}
        if not self.world:raise ValueError('Start or connect to CARLA first')
        if action=='configuration':return self.export_config()
        if action=='run':
            if self.mode=='native-replay' and self.replay_frames<=0:raise ValueError('Playback ended. Stop replay to restart a clean live scene.')
            self.running=True;self.state.update(running=True,error=None,phase='connected');return {'running':True}
        if action=='pause':self.running=False;self.state['running']=False;return {'running':False}
        if action=='step':self.tick();return {'frame':self.state['frame']}
        if action=='record-stop':return self.finish_record()
        if action=='control':
            m=self.managed.get(int(p['id']))
            if not m or m['planner']!='external':raise ValueError('Select an ego vehicle using the external planner')
            throttle,steer,brake=(float(p.get(k,0)) for k in ('throttle','steer','brake'))
            if not(0<=throttle<=1 and -1<=steer<=1 and 0<=brake<=1):raise ValueError('Invalid vehicle control ranges')
            control=carla.VehicleControl(throttle=throttle,steer=steer,brake=brake,reverse=bool(p.get('reverse',False)))
            for response in self.client.apply_batch_sync([carla.command.ApplyVehicleControl(m['actor'].id,control)],False):
                if response.error:raise RuntimeError('Control command failed: '+response.error)
            m['last_control']=time.monotonic();return {'applied':True,'frame':self.state['frame']}
        if action=='authoring-configure':
            self.require_edit()
            config=self.validate_schedule(p.get('config'))
            self.schedule.configure(config);dump(DATA/'authoring-plan.json',{'map':self.state['map'],'config':config});self.refresh();return self.state['authoring']
        if action=='authoring-start':
            self.require_edit();self.schedule.configure(self.validate_schedule(self.schedule.config));self.schedule.start(self.state['time']);self.refresh();return self.state['authoring']
        if action=='authoring-stop':
            self.schedule.stop();self.refresh();return self.state['authoring']
        if action=='network-timing':
            if self.recording or self.mode!='live':raise ValueError('Stop recording or replay before editing network timing')
            result=self.movements.network.configure(p,self.state['time']);self.tick();return result
        if action=='movement-program':
            if self.recording or self.mode!='live':raise ValueError('Stop recording or replay before editing phases')
            result=self.movements.apply(p,self.state['time'])
            self.tick();return self.movements.snapshot()
        if action=='traffic-light':
            if self.recording or self.mode!='live':raise ValueError('Stop recording or replay before editing signals')
            meta=self.signal_metadata.get(p.get('id'),{})
            if meta.get('group_id') in self.movements.programs:raise ValueError('Disable movement phases and let clearance finish before using native colour controls')
            result=traffic_signals.apply(self.world,p)
            self.tick();result['signal']=next(a for a in self.state['actors'] if a['id']==result['id'])
            return result
        if action=='weather':
            if self.recording or self.mode!='live':raise ValueError('Stop recording or replay before editing weather')
            w=self.world.get_weather()
            for k,v in p.items():
                hi=360 if k=='sun_azimuth_angle' else 10000 if k=='fog_distance' else 90 if k=='sun_altitude_angle' else 100
                lo=-90 if k=='sun_altitude_angle' else 0
                if k not in WEATHER or not(lo<=float(v)<=hi):raise ValueError('Invalid weather field or value')
                setattr(w,k,float(v))
            self.world.set_weather(w)
            # A synchronous world must tick to deliver the weather to GPU replicas.
            self.tick();return self.state['weather']
        if action=='record-start':
            if self.recording or self.mode!='live':raise ValueError('Stop existing recording or replay first')
            if not self.ros:raise ValueError('ROS unavailable')
            import shutil
            if shutil.disk_usage(DATA).free<5*1024**3:raise ValueError('Recording requires at least 5 GiB free')
            self.recording=Recording(DATA/'recordings',self.client,self.ros,self.export_config(),self.map_data,self.opendrive,bool(p.get('rosbag',True)))
            self.state['recording']=dict(self.recording.manifest);return self.state['recording']
        if action=='replay-stop':
            if self.mode!='native-replay':raise ValueError('No native replay active')
            # Native replay changes sensor stream routing in CARLA replicas. A
            # fresh owned group is required before collecting new sensor data.
            gpus=getattr(self,'last_gpus','3')
            # CARLA's process-global client/TM threads can retain the replay
            # episode after the simulator restarts. Replace this owner process
            # too, so no old native thread survives into the new episode.
            self.running=False;self.state.update(running=False,phase='restarting')
            dump(DATA/'restart-live-request.json',{'gpus':gpus,'created':time.time()})
            threading.Timer(.5,lambda:subprocess.Popen(['systemctl','--user','--no-block','restart','carla-control-center.service'])).start()
            return {'started':True,'restarting_live_scene':True,'restarting_owner':True}
        if action=='replay-native':
            self.require_edit()
            if not self.proc:raise ValueError('Native replay requires a simulator group started by this interface; recorded-state playback is available for external servers')
            session=self.session(p['id']);info=json.loads((session/'manifest.json').read_text())
            if info['status']!='complete':raise ValueError('Only completed sessions can be replayed')
            self.schedule.stop();self.movements.suspend()
            self.clear_managed();self.tick()
            self.replay_baseline_ids={a.id for a in self.world.get_actors()}
            self.tm.set_synchronous_mode(False)
            self.client.set_replayer_time_factor(1.0)
            result=self.client.replay_file(str(session/'carla.log'),float(p.get('start',0)),0,0,False)
            if 'error' in result.lower():raise ValueError(result)
            # Replay replaces actor lifetimes; discard client-side walker navigation caches.
            client=carla.Client('127.0.0.1',2000);client.set_timeout(120)
            self.client=client;self.world=client.get_world()
            self.replay_frames=max(1,info['frames']-round(float(p.get('start',0))/.05))
            self.mode='native-replay';self.running=True;self.state.update(running=True,mode=self.mode,phase='connected',error=None);return {'result':result}
        if action=='destination':
            if self.recording or self.mode!='live':raise ValueError('Stop recording or replay before changing destinations')
            return self.destination(int(p['id']),p['point'])
        self.require_edit()
        if action=='spawn':return self.spawn(p)
        if action=='delete':self.delete(int(p['id']));self.refresh();return {'deleted':True}
        if action=='sensors':
            aid=int(p['id']);self.configure_sensors(aid,p['sensors']);self.refresh();return {'configured':True}
        raise ValueError('Unknown command')

    def require_edit(self):
        if self.running:raise ValueError('Pause simulation before editing the scenario')
        if self.recording:raise ValueError('Stop recording before changing the scenario')
        if self.mode!='live':raise ValueError('Stop native replay before editing')

    def poll_start(self):
        if time.monotonic()-self.started>1800:raise RuntimeError('CARLA initialization exceeded 30 minutes')
        if self.proc.poll() is not None:raise RuntimeError('CARLA failed to start; inspect simulator log')
        manifests=sorted(Path('/media/william/mist1/Simulations/logs').glob('multigpu-*/processes.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        for path in manifests[:8]:
            m=json.loads(path.read_text())
            if m.get('manager_pid')==self.proc.pid and m.get('ready'):
                self.connect();return
        time.sleep(0.5)

    def connect(self):
        self.movements=None;self.signal_metadata={}
        self.state['phase']='connecting'
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(('127.0.0.1',8005))==0:raise RuntimeError('Dedicated Traffic Manager port 8005 is already in use')
        client=carla.Client('127.0.0.1',2000);client.set_timeout(120)
        world=client.get_world();wmap=world.get_map()
        self.original_settings=world.get_settings()
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        self.client,self.world,self.wmap=client,world,wmap
        self.tm=client.get_trafficmanager(8005);self.tm.set_synchronous_mode(True);self.tm.set_random_device_seed(42)
        self.planner=GlobalRoutePlanner(wmap,2.0)
        self.opendrive=wmap.to_opendrive()
        self.build_map()
        bps=world.get_blueprint_library()
        self.catalog={'vehicles':[{'id':b.id,'label':b.id.removeprefix('vehicle.').replace('.',' / ').replace('_',' ').title()} for b in sorted(bps.filter('vehicle.*'),key=lambda b:b.id)],
                      'walkers':[b.id for b in bps.filter('walker.pedestrian.*')],
                      'sensors':{kind:[{'id':a.id,'type':str(a.type),'value':str(a),'modifiable':a.is_modifiable,'recommended':list(a.recommended_values)} for a in bps.find(kind)] for kind in SENSOR_TYPES if bps.filter(kind)},
                      'defaults':DEFAULT_SENSORS}
        self.state.update(error=None,running=False,map=wmap.name,server_version=client.get_server_version())
        self.refresh()
        self.movements=MovementPrograms(world,self.opendrive,self.map_data['lanes'],self.signal_metadata)
        self.schedule.stop();saved=DATA/'authoring-plan.json'
        if saved.exists():
            stored=json.loads(saved.read_text())
            if stored.get('map')==self.state['map']:self.schedule.config=stored.get('config',{'flows':[],'events':[]})
        self.refresh()
        self.state['phase']='connected'

    def build_map(self):
        lanes,bounds,markings=build_lanes(self.wmap)
        boxes=[]
        for b in self.world.get_level_bbs(carla.CityObjectLabel.Buildings)[:6000]:boxes.append(dict(pose(carla.Transform(b.location,b.rotation)),extent=xyz(b.extent)))
        self.map_data={'name':self.wmap.name,'lanes':lanes,'markings':markings,'marking_source':'CARLA driving direction and immediate junction connectivity','bounds':bounds,'spawn_points':[dict(pose(t),index=i) for i,t in enumerate(self.wmap.get_spawn_points())],'buildings':boxes,'coordinates':'CARLA metres, x/y horizontal, z up; left-handed'}
        cache=DATA/'map-cache.json';previous=json.loads(cache.read_text()) if cache.exists() else {}
        self.map_data['pedestrian_points']=previous.get('pedestrian_points',[]) if previous.get('name')==self.wmap.name else []
        if not self.map_data['pedestrian_points']:self.map_data['pedestrian_points']=[dict(xyz(p),index=i) for i in range(30) if (p:=self.world.get_random_location_from_navigation()) is not None]
        dump(DATA/'map-cache.json',self.map_data);(DATA/'map-cache.xodr').write_text(self.opendrive)

    def waypoint(self,p):
        x,y=float(p['x']),float(p['y'])
        if not math.isfinite(x+y):raise ValueError('Invalid point')
        w=self.wmap.get_waypoint(carla.Location(x=x,y=y,z=float(p.get('z',0))),project_to_road=True,lane_type=carla.LaneType.Driving)
        if not w or math.hypot(w.transform.location.x-x,w.transform.location.y-y)>30:raise ValueError('Pick a point within 30 m of a drivable lane')
        return w

    def spawn(self,p,advance=True):
        role=p.get('role','ego');planner=p.get('planner','tm')
        if not advance and role=='ego':raise ValueError('Configure ego vehicles and sensors while paused')
        if role not in ('ego','background','pedestrian') or planner not in ('tm','external'):raise ValueError('Invalid role or planner')
        if len(self.managed)>=100:raise ValueError('Limit: 100 managed actors')
        if role=='pedestrian':
            bp=self.world.get_blueprint_library().find(p.get('model') or self.catalog['walkers'][0])
            if not bp.id.startswith('walker.pedestrian.'):raise ValueError('Select a pedestrian blueprint')
            loc=carla.Location(**{k:float(p['spawn'].get(k,0)) for k in ('x','y','z')});loc.z+=1
            t=carla.Transform(loc)
        else:
            bp=self.world.get_blueprint_library().find(p['model'])
            if not bp.id.startswith('vehicle.'):raise ValueError('Select a vehicle blueprint')
            t=self.waypoint(p['spawn']).transform;t.location.z+=.5
            bp.set_attribute('role_name','hero' if role=='ego' else 'background')
        configs=validate_loadout(p.get('sensors',[]))
        self.validate_blueprints(configs)
        a=self.world.try_spawn_actor(bp,t)
        if not a:raise ValueError('Spawn position is occupied; choose another lane point')
        self.managed[a.id]={'actor':a,'role':role,'planner':'tm' if role!='ego' else planner,'destination':None,'route':[],'last_control':0.,'controller':None}
        try:
            if advance:self.tick()
            if role=='pedestrian':
                ctrl=self.world.spawn_actor(self.world.get_blueprint_library().find('controller.ai.walker'),carla.Transform(),attach_to=a)
                self.managed[a.id]['controller']=ctrl
                if advance:self.tick();ctrl.start();ctrl.set_max_speed(1.4)
                else:self.scheduled_walkers.append({'id':a.id,'frame':self.world.get_snapshot().frame+1,'destination':p.get('destination')})
            else:
                a.set_autopilot(planner=='tm' or role=='background',8005)
                self.tm.ignore_lights_percentage(a,0.);self.tm.ignore_signs_percentage(a,0.)
                if role=='ego':self.configure_sensors(a.id,configs)
                if planner=='external' and role=='ego':a.apply_control(carla.VehicleControl(brake=1.))
            if p.get('destination') and (advance or role!='pedestrian'):self.destination(a.id,p['destination'])
        except Exception:
            self.client.set_timeout(3)
            try:self.delete(a.id)
            finally:self.client.set_timeout(120)
            raise
        self.refresh();return {'id':a.id,'actor':self.state['managed'][str(a.id)]}

    def validate_schedule(self,config):
        return authoring.validate(config,self.catalog,self.map_data['spawn_points'],self.map_data.get('pedestrian_points',[]),{g:self.movements.programs.get(g,{}).get('phases',self.movements.defaults(g)) for g in self.movements.groups},list(self.managed))

    def execute_scheduled(self,event,refs):
        action=event['action']
        if action in ('spawn_vehicle','spawn_pedestrian'):
            ped=action=='spawn_pedestrian';points=self.map_data['pedestrian_points' if ped else 'spawn_points']
            return self.spawn({'role':'pedestrian' if ped else 'background','planner':'tm','model':event['model'],'spawn':points[event['spawn']],'destination':points[event['destination']]},advance=False)['id']
        if action=='destination':
            aid=refs.get(event['actor'])
            if aid is None:
                try:aid=int(event['actor'])
                except ValueError:raise ValueError('The named spawn event has not produced an actor')
            self.destination(aid,self.map_data['spawn_points'][event['destination']])
        elif action=='weather':
            presets={'clear':{'cloudiness':5,'sun_altitude_angle':65},'cloudy':{'cloudiness':95,'sun_altitude_angle':45},'rain':{'cloudiness':95,'precipitation':70,'precipitation_deposits':60,'wetness':80,'sun_altitude_angle':35},'sunset':{'cloudiness':20,'sun_altitude_angle':8,'sun_azimuth_angle':270},'night':{'cloudiness':10,'sun_altitude_angle':-35}}
            w=self.world.get_weather()
            for key,value in dict(cloudiness=0,precipitation=0,precipitation_deposits=0,wetness=0,sun_altitude_angle=45,sun_azimuth_angle=0).items():setattr(w,key,value)
            for key,value in presets[event['preset']].items():setattr(w,key,value)
            self.world.set_weather(w)
        else:
            payload={'group_id':event['group_id'],'operation':{'signal_phase':'phase','signal_hold':'hold','signal_resume':'resume'}[action]}
            if action=='signal_phase':payload.update(index=event['index'],hold=True)
            self.movements.apply(payload,self.world.get_snapshot().timestamp.elapsed_seconds+.05)

    def destination(self,aid,p):
        m=self.managed.get(aid)
        if not m:raise ValueError('Select a managed actor')
        a=m['actor']
        if m['role']=='pedestrian':
            target=carla.Location(x=float(p['x']),y=float(p['y']),z=float(p.get('z',a.get_location().z)))
            m['controller'].go_to_location(target);route=[xyz(a.get_location()),xyz(target)]
        else:
            target_waypoint=self.waypoint(p);target=target_waypoint.transform.location
            target_lane=(target_waypoint.road_id,target_waypoint.section_id,target_waypoint.lane_id)
            path=self.planner.trace_route(a.get_location(),target)
            if not path:raise ValueError('No drivable route to this destination')
            route=[xyz(w.transform.location) for w,_ in path]
            if path[-1][0].transform.location.distance(target)>.1:route.append(xyz(target))
            if m['planner']=='tm':
                a.set_autopilot(True,8005)
                self.tm.auto_lane_change(a,False)
                self.tm.vehicle_percentage_speed_difference(a,0)
                m['target_lane']=target_lane;m['approach_slowdown']=False
                self.tm.set_path(a,traffic_path(path,target),True)
        m.update(destination=xyz(target),route=route,arrived=False);self.refresh()
        return {'route':route,'destination':xyz(target)}

    def validate_blueprints(self,configs):
        for cfg in configs:
            bp=self.world.get_blueprint_library().find(cfg['type'])
            for k,v in cfg['attributes'].items():
                if not bp.has_attribute(k) or not bp.get_attribute(k).is_modifiable:raise ValueError(f'{cfg["type"]}: unknown or read-only attribute {k}')
                bp.set_attribute(k,v)

    def configure_sensors(self,aid,configs):
        m=self.managed.get(aid)
        if not m or m['role']!='ego':raise ValueError('Sensor loadouts belong to ego vehicles')
        configs=validate_loadout(configs);self.validate_blueprints(configs)
        old=[sid for sid,s in self.sensors.items() if s['parent']==aid];new=[]
        try:
            for cfg in configs:
                bp=self.world.get_blueprint_library().find(cfg['type'])
                for k,v in cfg['attributes'].items():bp.set_attribute(k,v)
                mount=transform(cfg['mount']);a=self.world.spawn_actor(bp,mount,attach_to=m['actor'])
                new.append({'actor':a,'parent':aid,'config':cfg,'type':cfg['type'],'queue':queue.Queue(maxsize=8),'mount':mount,'overflow':False})
            self.tick() # Replicate new actors before subscribing; drain existing streams.
            for s in new:
                def callback(data,entry=s):
                    try:entry['queue'].put_nowait(data)
                    except queue.Full:entry['overflow']=True
                s['actor'].listen(callback)
            # Listen registers an asynchronous TCP subscription. Allow its local
            # connection to settle, then prove a complete frame before replacing
            # the old loadout or permitting recording. Zero tick interval avoids
            # floating-point cadence skips at the fixed .05-second world step.
            time.sleep(.2)
            for s in new:self.sensors[s['actor'].id]=s
            self.tick(publish=False)
            for sid in old:
                old_sensor=self.sensors[sid]
                old_sensor['actor'].stop();old_sensor['actor'].destroy()
                if self.ros:self.ros.remove_prefix(f"/carla/ego_{aid}/{old_sensor['config']['name']}/")
                del self.sensors[sid];self.previews.pop(sid,None)
            for s in new:self.sensors[s['actor'].id]=s
        except Exception:
            self.client.set_timeout(3)
            for s in new:
                self.sensors.pop(s['actor'].id,None)
                try:s['actor'].stop();s['actor'].destroy()
                except Exception:pass
            self.client.set_timeout(120)
            raise

    def fail(self,error):
        self.running=False
        self.state.update(running=False,phase='error',error=str(error))
        if self.recording:
            try:self.finish_record('failed',str(error))
            except Exception as final_error:self.state['error']+=f'; recording finalization failed: {final_error}'

    def tick(self,publish=True):
        try:
            return self._tick(publish)
        except Exception as error:
            self.fail(error)
            raise

    def prune_removed_actors(self):
        alive={a.id for a in self.world.get_actors()}
        for aid in list(self.managed):
            if aid in alive or str(aid) not in self.state.get('managed',{}):continue
            m=self.managed.pop(aid)
            for sid in [sid for sid,s in self.sensors.items() if s['parent']==aid]:
                s=self.sensors.pop(sid);self.previews.pop(sid,None)
                try:s['actor'].stop();s['actor'].destroy()
                except RuntimeError:pass
            if m.get('controller'):
                try:m['controller'].stop();m['controller'].destroy()
                except RuntimeError:pass
            if self.ros:self.ros.remove_prefix(f'/carla/ego_{aid}/')
            self.state['removed_actors']=(self.state.get('removed_actors',[])+[{'id':aid,'frame':self.state['frame'],'reason':'Actor removed by simulator'}])[-20:]

    def _tick(self,publish=True):
        if self.mode=='live':self.prune_removed_actors()
        if self.mode=='live':
            frame=self.world.get_snapshot().frame
            for entry in list(self.scheduled_walkers):
                if frame>=entry['frame']:
                    m=self.managed.get(entry['id'])
                    if m:
                        m['controller'].start();m['controller'].set_max_speed(1.4)
                        if entry['destination']:self.destination(entry['id'],entry['destination'])
                    self.scheduled_walkers.remove(entry)
            self.schedule.update(self.world.get_snapshot().timestamp.elapsed_seconds+.05)
        forced_controls=[]
        if self.mode=='live':
            for m in list(self.managed.values()):
                a=m['actor']
                actor_snapshot=self.world.get_snapshot().find(a.id)
                if actor_snapshot is None:
                    self.prune_removed_actors()
                    continue
                if m['role']=='ego' and m['planner']=='external' and time.monotonic()-m['last_control']>1:forced_controls.append(carla.command.ApplyVehicleControl(a.id,carla.VehicleControl(brake=1.)))
                if m.get('arrived') and m['planner']=='tm' and m['role']!='pedestrian':
                    # Actor.apply_control caches identical values across TM runs.
                    # A batch bypasses that sticky cache and really holds the brake.
                    forced_controls.append(carla.command.ApplyVehicleControl(a.id,carla.VehicleControl(brake=1.)))
                if m['destination'] and not m.get('arrived'):
                    d=m['destination'];loc=actor_snapshot.get_transform().location
                    distance=math.hypot(loc.x-d['x'],loc.y-d['y'])
                    if m['planner']=='tm' and m['role']!='pedestrian':
                        approach=False
                        if distance<25 and m.get('target_lane'):
                            w=self.wmap.get_waypoint(loc)
                            approach=w is not None and (w.road_id,w.section_id,w.lane_id)==tuple(m['target_lane'])
                        if approach:
                            speed=min(a.get_speed_limit(),3.6*math.sqrt(2*max(0,distance-3)))
                            self.tm.set_desired_speed(a,max(2.,speed));m['approach_slowdown']=True
                        elif m.get('approach_slowdown'):
                            self.tm.vehicle_percentage_speed_difference(a,0);m['approach_slowdown']=False
                    if distance<3:
                        m['arrived']=True
                        if m['role']=='pedestrian':m['controller'].stop()
                        elif m['planner']=='tm':
                            a.set_autopilot(False,8005)
                            forced_controls.append(carla.command.ApplyVehicleControl(a.id,carla.VehicleControl(brake=1.)))
        if forced_controls:
            for response in self.client.apply_batch_sync(forced_controls,False):
                if response.error:raise RuntimeError('Brake command failed: '+response.error)
        if self.mode=='live' and self.movements:self.movements.update(self.world.get_snapshot().timestamp.elapsed_seconds+.05)
        frame=self.world.tick(120);snap=self.world.get_snapshot();samples=[]
        if self.mode=='live':self.prune_removed_actors()
        for sid,s in self.sensors.items():
            if s['overflow']:raise RuntimeError(f'Sensor {sid} queue overflow: simulation paused; no complete recording claim')
            deadline=time.monotonic()+90
            while True:
                try:data=s['queue'].get(timeout=max(.01,deadline-time.monotonic()))
                except queue.Empty:raise RuntimeError(f'Sensor {sid} did not deliver frame {frame}')
                if data.frame<frame:continue
                if data.frame!=frame or abs(data.timestamp-snap.timestamp.elapsed_seconds)>1e-5:raise RuntimeError(f'Sensor {sid} frame or timestamp mismatch')
                samples.append(dict(s,data=data,pose=pose(data.transform)));break
        self.refresh(snap)
        if self.mode=='native-replay':
            self.replay_frames-=1
            if self.replay_frames<=0:self.running=False;self.state['running']=False
        if self.ros and publish:self.ros.frame(snap.timestamp.elapsed_seconds,[m['actor'] for m in self.managed.values() if m['role']=='ego'],samples)
        if self.ros and publish:self.ros.signals(snap.timestamp.elapsed_seconds,self.state)
        if self.recording:
            self.recording.write(self.state,samples);self.state['recording']=dict(self.recording.manifest)
        now=time.monotonic()
        for s in samples:
            if s['type']=='sensor.camera.rgb' and now-s.get('preview_at',0)>.2:
                d=s['data'];im=Image.frombytes('RGBA',(d.width,d.height),bytes(d.raw_data),'raw','BGRA').convert('RGB');im.thumbnail((480,270));b=io.BytesIO();im.save(b,format='JPEG',quality=75)
                self.previews[s['actor'].id]=(d.frame,b.getvalue());self.sensors[s['actor'].id]['preview_at']=now

    def refresh(self,snap=None):
        snap=snap or self.world.get_snapshot();actors=[]
        for a in self.world.get_actors():
            if a.type_id.startswith(('vehicle.','walker.pedestrian.','traffic.traffic_light')):
                item={'id':a.id,'type':a.type_id,'pose':pose(a.get_transform())}
                if a.type_id.startswith('traffic.traffic_light'):
                    if a.id not in self.signal_metadata:self.signal_metadata[a.id]=traffic_signals.metadata(a)
                    item.update(self.signal_metadata[a.id])
                    item.update(movement_word=a.get_movement_states(),movements=unpack(a.get_movement_states()),movement_lanes=self.movements.movements.get(a.id,{}) if self.movements else {})
                    item.update(state=str(a.get_state()).split('.')[-1],elapsed=a.get_elapsed_time(),green_time=a.get_green_time(),yellow_time=a.get_yellow_time(),red_time=a.get_red_time(),frozen=a.is_frozen())
                else:
                    item.update(velocity=xyz(a.get_velocity()),angular_velocity=xyz(a.get_angular_velocity()),acceleration=xyz(a.get_acceleration()),attributes=dict(a.attributes))
                    c=a.get_control()
                    item['control']={k:getattr(c,k) for k in ('throttle','steer','brake','hand_brake','reverse','manual_gear_shift','gear')} if a.type_id.startswith('vehicle.') else {'direction':xyz(c.direction),'speed':c.speed,'jump':c.jump}
                    item['extent']=xyz(a.bounding_box.extent)
                actors.append(item)
        weather=self.world.get_weather()
        managed={str(aid):{k:v for k,v in m.items() if k not in ('actor','controller','last_control')} for aid,m in self.managed.items()}
        self.state={**self.state,'frame':snap.frame,'time':snap.timestamp.elapsed_seconds,'delta':snap.timestamp.delta_seconds,'actors':actors,'weather':{k:getattr(weather,k) for k in WEATHER},
                    'authoring':self.schedule.snapshot(),'network_timing':self.movements.network.snapshot() if self.movements else {'mode':'independent'},'managed':managed,'mode':self.mode,'running':self.running,'movement_programs':self.movements.snapshot() if self.movements else {},
                    'sensors':[{'id':sid,'parent':s['parent'],**s['config']} for sid,s in self.sensors.items()]}

    def delete(self,aid):
        m=self.managed.get(aid)
        if not m:raise ValueError('Actor is not managed by this interface')
        for sid in [sid for sid,s in self.sensors.items() if s['parent']==aid]:
            s=self.sensors.pop(sid);s['actor'].stop();s['actor'].destroy();self.previews.pop(sid,None)
            if self.ros:self.ros.remove_prefix(f"/carla/ego_{aid}/{s['config']['name']}/")
        if m['controller']:m['controller'].stop();m['controller'].destroy()
        m['actor'].destroy();del self.managed[aid]
        if self.ros:self.ros.remove_prefix(f'/carla/ego_{aid}/')

    def clear_managed(self):
        for aid in list(self.managed):self.delete(aid)

    def finish_record(self,status='complete',error=None):
        if not self.recording:raise ValueError('No recording active')
        rec=self.recording;self.recording=None
        try:return rec.close(status,error)
        finally:self.state['recording']=None

    def export_config(self):
        poses={a['id']:a['pose'] for a in self.state['actors']}
        return {'version':3,'authoring':self.schedule.snapshot(),'network_timing':self.movements.network.snapshot() if self.movements else {},'map':self.state['map'],'weather':self.state.get('weather'),'movement_programs':self.movements.snapshot() if self.movements else {},
                'traffic_lights':[a for a in self.state['actors'] if a['type'].startswith('traffic.traffic_light')],
                'actors':[dict(id=aid,model=m['actor'].type_id,role=m['role'],planner=m['planner'],spawn=poses[aid],destination=m['destination'],
                               sensors=[s['config'] for s in self.sensors.values() if s['parent']==aid]) for aid,m in self.managed.items() if aid in poses],
                'fixed_delta_seconds':.05,'tm_seed':42}

    @staticmethod
    def session(sid):
        if not re.fullmatch(r'\d{8}-\d{6}-[0-9a-f]{6}',sid):raise ValueError('Invalid session ID')
        path=DATA/'recordings'/sid
        if not path.is_dir():raise ValueError('Session not found')
        return path

    def disconnect(self,stop_process=False):
        self.schedule.stop();self.scheduled_walkers=[]
        self.running=False
        if self.recording:self.finish_record()
        if self.world and (not self.proc or self.proc.poll() is None):
            try:
                self.client.set_timeout(5)
                if self.mode!='live':self.client.stop_replayer(False)
                if self.movements:self.movements.suspend()
                self.clear_managed();self.tm.set_synchronous_mode(False);self.world.apply_settings(self.original_settings)
            except Exception:traceback.print_exc()
        # Python wrapper deletion does not stop CARLA's process-global TM threads.
        # Shut down our dedicated TM while its CARLA server is still alive.
        if self.tm:
            try:self.tm.shut_down()
            except Exception:traceback.print_exc()
        self.movements=None;self.world=None;self.client=None;self.tm=None;self.mode='live';self.sensors={};self.managed={};self.previews={}
        if stop_process and self.proc:
            if self.proc.poll() is None:os.killpg(self.proc.pid,signal.SIGTERM)
            try:self.proc.wait(timeout=40)
            except subprocess.TimeoutExpired:os.killpg(self.proc.pid,signal.SIGKILL);self.proc.wait()
            self.proc=None
            if self.log_handle:self.log_handle.close();self.log_handle=None
        self.state.update(phase='offline',mode='live',running=False,actors=[],managed={},sensors=[],recording=None,error=None)

    def close(self):self.stop_event.set();self.thread.join(timeout=150)
