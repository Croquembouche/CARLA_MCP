"""Isolated native acceptance check. Requires a disposable server on port 2100."""
import sys,json,time,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,carla,parking
from controller import Controller,pose,xyz
from scene_vehicles import SceneVehicles

ROOT=Path(__file__).resolve().parents[1]
class Owner:
    def __init__(self):
        self.client=carla.Client('127.0.0.1',2100);self.client.set_timeout(30)
        self.world=self.client.get_world();self.wmap=self.world.get_map()
        self.original=self.world.get_settings();settings=self.world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;self.world.apply_settings(settings)
        self.tm_port=8105;self.tm=self.client.get_trafficmanager(self.tm_port);self.tm.set_synchronous_mode(True);self.tm.set_random_device_seed(42)
        self.managed={};self.sensors={};self.previews={};self.ros=None;self.running=False;self.recording=None;self.mode='live';self.worker_manifest=None
        self.tick();self.parking_static=parking.static_vehicles(self.world,carla);self.scene_vehicles=SceneVehicles(self)
    def tick(self):self.world.tick();self.refresh()
    def refresh(self):
        self.state={'frame':self.world.get_snapshot().frame,'actors':[{'id':a.id,'pose':pose(a.get_transform()),'type':a.type_id,'extent':xyz(a.bounding_box.extent)} for a in self.world.get_actors().filter('vehicle.*')],'managed':{str(aid):{k:v for k,v in m.items() if k not in ('actor','controller')} for aid,m in self.managed.items()}}
    require_edit=Controller.require_edit
    waypoint=Controller.waypoint
    delete=Controller.delete

def main():
    c=Owner();report={'map':c.wmap.name,'primary_port':2100,'gpu_rendering':False,'started':time.time()};out=ROOT/'data/scene-vehicles/native-verification.json'
    try:
        (ROOT/'data/scene-vehicles/native-inventory.json').write_text(json.dumps(c.scene_vehicles.sources,indent=2))
        report['conversion']=c.scene_vehicles.convert();out.write_text(json.dumps(report,indent=2));print('CONVERTED',len(report['conversion']['created']),'FAILURES',report['conversion']['failures'],flush=True)
        allowed='--allow-unavailable-models' in sys.argv
        assert not report['conversion']['failures'] or (allowed and all(f['error']=='No compatible drivable model in this catalogue' for f in report['conversion']['failures'])),report['conversion']['failures']
        report['all_scenery_converted']=report['conversion']['remaining']==0
        assert report['conversion']['created']
        physics={aid:m['actor'].get_physics_control() for aid,m in c.managed.items()}
        assert all(len(p.wheels)>0 for p in physics.values())
        rec=ROOT/'data/scene-vehicles/parked-native-recording.rec'
        c.client.start_recorder(str(rec),True)
        for _ in range(3):c.tick()
        c.client.stop_recorder()
        assert rec.stat().st_size>0
        report['parked_physics_and_recording']={'vehicles':len(physics),'recorded_frames':3,'bytes':rec.stat().st_size}
        before={aid:pose(m['actor'].get_transform()) for aid,m in c.managed.items()}
        for _ in range(60):c.tick()
        report['parked_max_drift_m']=max(math.hypot(m['actor'].get_location().x-before[aid]['x'],m['actor'].get_location().y-before[aid]['y']) for aid,m in c.managed.items())
        assert report['parked_max_drift_m']<.01
        aid=next(iter(c.managed));m=c.managed[aid]
        for point in c.wmap.get_spawn_points():
            try:c.scene_vehicles.release_to_road(aid,pose(point));break
            except ValueError:continue
        else:raise AssertionError('No free road spawn')
        start=m['actor'].get_location();maximum_speed=0
        for _ in range(100):c.tick();maximum_speed=max(maximum_speed,m['actor'].get_velocity().length())
        report['released_to_road']={'id':aid,'distance_m':m['actor'].get_location().distance(start),'max_speed_m_s':maximum_speed}
        assert maximum_speed>.1
        # get_actor(id) caches descriptions even after native destruction; use the live snapshot.
        hidden=set(c.scene_vehicles.hidden);c.delete(aid);c.tick();c.tick()
        assert aid not in c.managed and not c.world.get_snapshot().find(aid) and aid not in {a.id for a in c.world.get_actors()}
        assert c.scene_vehicles.hidden==hidden and not c.scene_vehicles.convert()['created']
        report['background_removal_preserves_hidden_scenery']=True
        report['motorcycle_driving']={}
        for model in ['vehicle.harley.low_rider','vehicle.vespa.zx125','vehicle.yamaha.yzf','vehicle.kawasaki.ninja']:
            matches=[(id,m) for id,m in c.managed.items() if m['actor'].type_id==model]
            if not matches:continue
            mid,mm=matches[0]
            for point in c.wmap.get_spawn_points():
                try:c.scene_vehicles.release_to_road(mid,pose(point));break
                except ValueError:continue
            else:raise AssertionError('No free motorcycle road spawn')
            speed=0
            for _ in range(80):c.tick();speed=max(speed,mm['actor'].get_velocity().length())
            rotation=mm['actor'].get_transform().rotation
            report['motorcycle_driving'][model]={'max_speed_m_s':speed,'roll_degrees':rotation.roll,'pitch_degrees':rotation.pitch}
            assert speed>.1 and abs(rotation.roll)<45,report['motorcycle_driving'][model]
            c.delete(mid);c.tick();c.tick()
        for point in c.wmap.get_spawn_points():
            ego=c.world.try_spawn_actor(c.world.get_blueprint_library().find('vehicle.lincoln.mkz'),point)
            if ego:break
        assert ego
        c.managed[ego.id]={'actor':ego,'controller':None,'role':'ego'}
        sensor=c.world.spawn_actor(c.world.get_blueprint_library().find('sensor.other.imu'),carla.Transform(),attach_to=ego);sensor.listen(lambda data:None)
        c.sensors[sensor.id]={'actor':sensor,'parent':ego.id,'config':{'name':'imu'}};c.tick();sid=sensor.id;eid=ego.id;c.delete(eid);c.tick();c.tick()
        assert not c.world.get_snapshot().find(eid) and not c.world.get_snapshot().find(sid)
        report['ego_sensor_removal']=True
        walker=None
        for _ in range(30):
            p=c.world.get_random_location_from_navigation()
            if p:walker=c.world.try_spawn_actor(c.world.get_blueprint_library().filter('walker.pedestrian.*')[0],carla.Transform(p))
            if walker:break
        assert walker
        ctrl=c.world.spawn_actor(c.world.get_blueprint_library().find('controller.ai.walker'),carla.Transform(),attach_to=walker);c.tick();ctrl.start()
        c.managed[walker.id]={'actor':walker,'controller':ctrl,'role':'pedestrian'};wid=walker.id;cid=ctrl.id;c.delete(wid);c.tick();c.tick()
        assert not c.world.get_snapshot().find(wid) and not c.world.get_snapshot().find(cid)
        report['pedestrian_controller_removal']=True;report['passed']=True
    finally:
        out.write_text(json.dumps(report,indent=2))
        for aid in list(c.managed):
            try:c.delete(aid)
            except RuntimeError:pass
        c.scene_vehicles.restore({});c.tm.set_synchronous_mode(False);c.tm.shut_down();c.world.apply_settings(c.original)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
