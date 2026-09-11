"""Shared cycle starts and demand-based green termination for native programs."""
import copy
import math
from authoring import number


class NetworkTiming:
    def __init__(self, manager):self.manager=manager;self.config={'mode':'independent'};self.epoch=0.;self.release={};self.last_demand={};self.detector_time=-1.;self.detectors={}
    def configure(self, config, now):
        mode=config.get('mode')
        if mode not in ('independent','coordinated','adaptive'):raise ValueError('Choose independent, coordinated or adaptive timing')
        m=self.manager;result={'mode':mode}
        if mode!='independent' and (set(m.programs)!=set(m.groups) or any(p.get('pending') or p.get('disable') for p in m.programs.values())):raise ValueError('Enable and finish applying a movement plan at every intersection first')
        if mode=='coordinated':
            cycle=number(config.get('cycle_time',120),'Common cycle',1,3600);offsets=config.get('offsets',{})
            if not isinstance(offsets,dict) or set(offsets)-{str(g) for g in m.groups}:raise ValueError('Offsets reference an unknown intersection')
            for p in m.programs.values():
                if sum(x['duration']+p['yellow_time']+p['all_red_time'] for x in p['phases'])>cycle:raise ValueError('The common cycle must fit every intersection plan, including clearances')
            result.update(cycle_time=cycle,offsets={str(g):number(offsets.get(str(g),0),'Offset',0,cycle-.05) for g in m.groups})
        elif mode=='adaptive':
            low=number(config.get('min_green',5),'Minimum green',.5,120);high=number(config.get('max_green',30),'Maximum green',low,600)
            result.update(min_green=low,max_green=high,gap=number(config.get('gap',2),'Vehicle gap',.5,15),distance=number(config.get('distance',40),'Detector distance',5,100))
        self.config=result;self.release={};self.last_demand={};self.detectors={};self.detector_time=-1
        if mode=='coordinated':
            self.epoch=now+max(p['yellow_time']+p['all_red_time'] for p in m.programs.values())+.05
            for gid,p in m.programs.items():p['hold']=False;p['next']=0;m.clearance(p,now);self.release[gid]=self.epoch+result['offsets'][str(gid)]
        return self.snapshot()
    def green_finished(self,gid,p,now):
        if self.config['mode']!='adaptive':return now-p['since']+1e-7>=p['phases'][p['index']]['duration']
        if now-self.detector_time>=.5:
            self.detector_time=now;self.detectors=self.detect()
        if any(self.detectors.get(a,0) for a,moves in p['current'].items() if any(v in ('Protected','Permissive') for v in moves.values())):self.last_demand[gid]=now
        elapsed=now-p['since'];last=max(p['since'],self.last_demand.get(gid,p['since']))
        return elapsed+1e-7>=self.config['max_green'] or elapsed+1e-7>=self.config['min_green'] and now-last+1e-7>=self.config['gap']
    def can_release(self,gid,p,now):
        if self.config['mode']!='coordinated' or p['next']!=0:return True
        return now+1e-7>=self.release.get(gid,now)
    def released(self,gid,p,now):
        self.last_demand[gid]=now
        if self.config['mode']=='coordinated' and p['index']==0:
            base=self.epoch+self.config['offsets'][str(gid)];cycle=self.config['cycle_time'];self.release[gid]=base+(math.floor((now-base+1e-7)/cycle)+1)*cycle
    def detect(self):
        world=self.manager.world
        if not hasattr(world,'get_actors'):return {}
        wmap=world.get_map();vehicles=[]
        for vehicle in world.get_actors().filter('vehicle.*'):
            loc=vehicle.get_location();wp=wmap.get_waypoint(loc)
            if wp:vehicles.append((loc,vehicle.get_transform().get_forward_vector(),wp.road_id,wp.lane_id))
        result={};distance=self.config.get('distance',40)
        for aid in self.manager.metadata:
            light=world.get_actor(aid);stops=light.get_stop_waypoints();count=0
            for loc,forward,road,lane in vehicles:
                if any(stop.road_id==road and stop.lane_id==lane and (stop.transform.location.x-loc.x)*forward.x+(stop.transform.location.y-loc.y)*forward.y>=-2 and loc.distance(stop.transform.location)<=distance and abs(loc.z-stop.transform.location.z)<3 for stop in stops):count+=1
            result[str(aid)]=count
        return result
    def snapshot(self):return {**copy.deepcopy(self.config),'epoch':self.epoch,'detectors':dict(self.detectors),'next_cycle_starts':dict(self.release)}
