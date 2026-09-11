"""Replace vehicle scenery with managed actors without editing the authored map."""
import math,re,time,subprocess,sys,tempfile,json
from pathlib import Path
import bootstrap
import carla

LABELS=('Car','Truck','Bus','Motorcycle','Bicycle')
MOTORCYCLE_PRESETS={'vehicle.harley.low_rider','vehicle.vespa.zx125','vehicle.yamaha.yzf','vehicle.kawasaki.ninja'}
ALIASES=[('chargercop','vehicle.dodgecop.charger'),('dodgecop','vehicle.dodgecop.charger'),('charger','vehicle.dodge.charger'),('fordcrown02','vehicle.taxi.ford'),('fordcrown01','vehicle.ue4.ford.crown'),('mustang','vehicle.ue4.ford.mustang'),('lincoln','vehicle.lincoln.mkz'),('mini','vehicle.mini.cooper'),('nissan','vehicle.nissan.patrol'),('sprinter','vehicle.sprinter.mercedes'),('fuso','vehicle.fuso.mitsubishi'),('carlacola','vehicle.carlacola.actors'),('tesla','vehicle.tesla.model3'),('volkswagen','vehicle.volkswagen.t2'),('europeanhgv','vehicle.european.hgv')]
ALIASES.extend([('harley','vehicle.harley.low_rider'),('vespa','vehicle.vespa.zx125'),('yamaha','vehicle.yamaha.yzf'),('kawasaki','vehicle.kawasaki.ninja'),('crossbike','vehicle.bh.crossbike'),('roadbike','vehicle.diamondback.century'),('leisurebike','vehicle.gazelle.omafiets')])

def contains_center(part,b):
    a=math.radians(part['yaw']);dx=b.location.x-part['x'];dy=b.location.y-part['y']
    return abs(dx*math.cos(a)+dy*math.sin(a))<=part['length']/2+.2 and abs(-dx*math.sin(a)+dy*math.cos(a))<=part['width']/2+.2 and abs(b.location.z-part['z'])<=part['height']/2+.2

def discover(world):
    groups={}
    dynamic_centres=[]
    for actor in world.get_actors().filter('vehicle.*'):
        dynamic_centres.append(actor.get_transform().transform(actor.bounding_box.location))
    for label in LABELS:
        for obj in world.get_environment_objects(getattr(carla.CityObjectLabel,label)):
            # A body and its glass share an actor; ISM instances remain separate.
            key=re.sub(r'_(?:SM|SKM)_\d+$','',obj.name)
            if any(obj.bounding_box.location.distance(p)<.25 for p in dynamic_centres):continue
            group=groups.setdefault(key,{'key':key,'names':[],'ids':[],'components':[]})
            group['names'].append(obj.name);group['ids'].append(obj.id)
            group['components'].append((obj,label))
    result=[]
    for g in groups.values():
        parts=[]
        components=sorted(g.pop('components'),key=lambda pair:pair[0].bounding_box.extent.x*pair[0].bounding_box.extent.y*pair[0].bounding_box.extent.z,reverse=True)
        for obj,label in components:
            b=obj.bounding_box
            if b.extent.x<.4 or b.extent.y<.2 or any(contains_center(part,b) for part in parts):continue
            parts.append(dict(key=g['key'],label=label,x=b.location.x,y=b.location.y,z=b.location.z,yaw=b.rotation.yaw,length=2*b.extent.x,width=2*b.extent.y,height=2*b.extent.z))
        if not parts:continue
        g.update(parts[0]);g['parts']=parts
        result.append(g)
    return sorted(result,key=lambda x:x['key'])

def model_for(source,available):
    name=re.sub('[^a-z0-9]','',source['key'].lower())
    preferred=next((model for token,model in ALIASES if token in name),None)
    if preferred in available:return preferred,False
    # The UE5 catalogue does not include every legacy parked mesh.
    fallbacks={'Car':['vehicle.lincoln.mkz','vehicle.dodge.charger'],'Truck':['vehicle.carlacola.actors','vehicle.sprinter.mercedes'],'Bus':['vehicle.fuso.mitsubishi'],'Motorcycle':['vehicle.kawasaki.ninja'],'Bicycle':['vehicle.bh.crossbike']}
    replacement=next((v for v in fallbacks[source['label']] if v in available),None)
    return replacement,True

def two_wheeler_source(part):
    return part['label'] in ('Motorcycle','Bicycle') or any(token in part['key'].lower() for token in ('harley','vespa','yamaha','kawasaki','crossbike','roadbike','leisurebike'))

def traffic_surface(wmap,position,parking_spaces):
    """Require an actual driving/bicycle lane or a mapped parking bay, never nearest-road projection."""
    location=carla.Location(x=position['x'],y=position['y'],z=position.get('z',0))
    waypoint=wmap.get_waypoint(location,project_to_road=False,lane_type=carla.LaneType.Any)
    if waypoint and waypoint.lane_type in (carla.LaneType.Driving,carla.LaneType.Biking,carla.LaneType.Parking):return True
    if waypoint and waypoint.lane_type==carla.LaneType.Sidewalk:return False
    for bay in parking_spaces:
        angle=math.radians(bay['yaw']);dx=position['x']-bay['x'];dy=position['y']-bay['y']
        if abs(dx*math.cos(angle)+dy*math.sin(angle))<=bay['length']/2 and abs(-dx*math.sin(angle)+dy*math.cos(angle))<=bay['width']/2:return True
    return False

class SceneVehicles:
    def __init__(self,owner):
        self.owner=owner;self.tm_port=getattr(owner,'tm_port',8005);self.sources=discover(owner.world);self.hidden=set();self.failures=[];self.synced={};self.original_parking_static=list(owner.parking_static)
        self.removed=[]
        name=owner.world.get_map().name
        if isinstance(name,str):
            path=Path(__file__).parent/'map-revisions'/(name.split('/')[-1]+'.json')
            if path.exists():
                revision=json.loads(path.read_text())
                if revision['map'].removeprefix('/Game/')==name.removeprefix('/Game/'):
                    # Only migrate deletions actually absent from the loaded native map.
                    present={s['key'] for s in self.sources}
                    self.removed=[r for r in revision['removed'] if r['source'] not in present]

        # Sidewalk display bikes must not become collidable background traffic.
        wmap=owner.world.get_map();bays=(owner.map_data or {}).get('parking_spaces',[])
        self.excluded={source['key'] for source in self.sources if any(two_wheeler_source(part) and not traffic_surface(wmap,part,bays) for part in source['parts'])}
        if self.excluded:self.visibility(self.excluded,False,sync=False)

    def was_removed(self,source):
        return bool(source) and source.split(':')[0] in ({r['source'] for r in self.removed}|self.excluded)

    def snapshot(self):
        return {'total':sum(len(s['parts']) for s in self.sources),'hidden':[dict(part,key=s['key'] if len(s['parts'])==1 else f'{s["key"]}:{i}',ids=[str(v) for v in s['ids']]) for s in self.sources if s['key'] in self.hidden for i,part in enumerate(s['parts'])],
                'removed':[dict(r['pose'],key=r['source']) for r in self.removed],
                'remaining':sum(len(s['parts']) for s in self.sources if s['key'] not in self.hidden),'substitutions':sum(bool(m.get('model_substituted')) for m in self.owner.managed.values()),'failures':self.failures}

    def visibility(self,keys,enabled,sync=True):
        sources=[s for s in self.sources if s['key'] in keys]
        self.owner.world.enable_environment_objects({i for s in sources for i in s['ids']},enabled)
        if enabled:self.hidden.difference_update(keys)
        else:self.hidden.update(keys)
        hidden_names={n for s in self.sources if s['key'] in self.hidden for n in s['names']}
        self.owner.parking_static=[b for b in self.original_parking_static if b['name'] not in hidden_names]
        if sync:self.sync_workers()

    def sync_workers(self):
        owner=self.owner
        if not getattr(owner,'worker_manifest',None):return
        from gpu_resources import read_manifest
        names={n for s in self.sources if s['key'] in self.hidden for n in s['names']}
        for worker in read_manifest(owner.worker_manifest).get('children',[]):
            if worker['role']=='primary' or not worker.get('initialized'):continue
            key=(worker['pid'],tuple(sorted(names)))
            if self.synced.get(worker['pid'])==key:continue
            port=int(next(a.split('=')[1] for a in worker['command'] if a.startswith('-carla-rpc-port=')))
            self.sync_worker(port,{n for s in self.sources for n in s['names']},names)
            self.synced[worker['pid']]=key

    def sync_worker(self,port,all_names,hidden_names):
        # get_world holds the Python GIL while waiting for a secondary snapshot.
        # A separate client process lets the owner supply frames and serve UI
        # progress, without allowing a second process to advance the world clock.
        import json
        with tempfile.TemporaryFile(mode='w+b') as log:
            child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('scene_vehicle_worker.py'))],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
            try:
                child.stdin.write(json.dumps({'port':port,'all_names':sorted(all_names),'hidden_names':sorted(hidden_names)}).encode());child.stdin.close()
                deadline=time.monotonic()+120
                while child.poll() is None:
                    if time.monotonic()>deadline:raise RuntimeError('GPU scenery visibility synchronization timed out')
                    self.owner.tick(publish=False);time.sleep(.02)
                if child.returncode:
                    log.seek(0);raise RuntimeError('GPU scenery visibility failed: '+log.read().decode(errors='replace')[-3000:])
            finally:
                if child.poll() is None:child.kill();child.wait()

    def convert(self):
        owner=self.owner;owner.require_edit();self.failures=[]
        available={b.id for b in owner.world.get_blueprint_library().filter('vehicle.*')}
        created=[]
        for actor in owner.world.get_actors().filter('vehicle.*'):
            if actor.id in owner.managed:continue
            actor.set_autopilot(False,self.tm_port);actor.apply_control(carla.VehicleControl(brake=1,hand_brake=True));actor.set_simulate_physics(False)
            owner.managed[actor.id]={'actor':actor,'role':'background','planner':'parked','parked':True,'scene_source':f'native:{actor.id}','destination':None,'route':[],'arrived':True,'last_control':0.,'controller':None,'physics_sleeping':True}
            created.append(actor.id)
        for s in self.sources:
            if s['key'] in self.hidden:continue
            actors=[]
            try:
                choices=[model_for(part,available) for part in s['parts']]
                if any(not model for model,_ in choices):raise ValueError('No compatible drivable model in this catalogue')
                self.visibility({s['key']},False,sync=False)
                for i,(part,(model,substituted)) in enumerate(zip(s['parts'],choices)):
                    actors.append(self.spawn(model,part,source=s['key'] if len(s['parts'])==1 else f'{s["key"]}:{i}',substituted=substituted))
                created.extend(actor.id for actor in actors)
            except Exception as error:
                for actor in actors:owner.managed.pop(actor.id,None);actor.destroy()
                self.visibility({s['key']},True,sync=False)
                self.failures.append({'source':s['key'],'error':str(error)})
        self.sync_workers()
        owner.tick();owner.refresh()
        return {'created':created,**self.snapshot()}

    def spawn(self,model,position,source=None,substituted=False,saved_pose=False):
        owner=self.owner;bp=owner.world.get_blueprint_library().find(model);bp.set_attribute('role_name','background')
        z=position['z'] if saved_pose else position['z']-position['height']/2+.2
        t=carla.Transform(carla.Location(x=position['x'],y=position['y'],z=z),carla.Rotation(yaw=position['yaw'],pitch=position.get('pitch',0),roll=position.get('roll',0)))
        actor=owner.world.try_spawn_actor(bp,t)
        if not saved_pose and not actor:
            for lift in (.5,1.):
                t.location.z=position['z']-position['height']/2+lift
                actor=owner.world.try_spawn_actor(bp,t)
                if actor:break
        if not actor:
            # Some authored display cars intersect coarse building collision.
            # Construct on a free road, freeze physics, then place at the exact
            # scenery pose. They can only be released at a checked road position.
            for staging in owner.world.get_map().get_spawn_points():
                actor=owner.world.try_spawn_actor(bp,staging)
                if actor:break
        if not actor:raise ValueError('Replacement model cannot spawn at this scenery position')
        try:
            actor.set_autopilot(False,self.tm_port)
            actor.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
            # Parked actors sleep without physics cost until explicitly released.
            actor.set_simulate_physics(False)
            if not saved_pose:
                b=actor.bounding_box;a=math.radians(t.rotation.yaw)
                t.location.x-=math.cos(a)*b.location.x-math.sin(a)*b.location.y
                t.location.y-=math.sin(a)*b.location.x+math.cos(a)*b.location.y
                t.location.z=position['z']-position['height']/2+b.extent.z-b.location.z+.03
            actor.set_transform(t)
            owner.managed[actor.id]={'actor':actor,'role':'background','planner':'parked','parked':True,'scene_source':source,'model_substituted':substituted,'destination':None,'route':[],'arrived':True,'last_control':0.,'controller':None,'physics_sleeping':True,'physics_preset':'approximate_motorcycle' if model in MOTORCYCLE_PRESETS else None}
        except Exception:actor.destroy();raise
        return actor

    def restore(self,config):
        wanted={key for key in config.get('hidden',[]) if not self.was_removed(key)}|self.excluded
        unknown=wanted-{s['key'] for s in self.sources}
        if unknown:raise ValueError('Saved scenery vehicles are absent from this map revision: '+', '.join(sorted(unknown)))
        self.visibility(self.hidden-wanted,True,sync=False)
        self.visibility(wanted,False)

    def release_to_road(self,aid,point):
        owner=self.owner;owner.require_edit();m=owner.managed.get(aid)
        if not m or not m.get('parked'):raise ValueError('Select a parked background vehicle')
        w=owner.waypoint(point);t=w.transform;t.location.z+=.3
        # Probe a drivable vehicle at the destination before moving the original.
        probe=owner.world.try_spawn_actor(owner.world.get_blueprint_library().find(m['actor'].type_id),t)
        if not probe:raise ValueError('The selected road position is occupied')
        probe.destroy();a=m['actor'];a.set_transform(t);a.set_simulate_physics(True)
        a.apply_control(carla.VehicleControl());a.set_autopilot(True,self.tm_port)
        owner.tm.ignore_lights_percentage(a,0.);owner.tm.ignore_signs_percentage(a,0.)
        m.update(parked=False,physics_sleeping=False,planner='tm',arrived=False,parking_space=None)
        owner.tick();owner.refresh();return {'id':aid,'moved_to_road':True}
