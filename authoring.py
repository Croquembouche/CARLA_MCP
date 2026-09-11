"""Deterministic simulation-clock traffic flows and scenario actions."""
import copy
import math
import re


def number(value, name, low=0, high=86400):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f'{name} must be {low}–{high}')
    return float(value)


def validate(config, catalog, points, pedestrians, groups, actor_ids):
    if not isinstance(config,dict):raise ValueError('Expected a scenario plan object')
    flows=config.get('flows',[]);events=config.get('events',[])
    if not isinstance(flows,list) or len(flows)>32 or not isinstance(events,list) or len(events)>256:raise ValueError('Use at most 32 flows and 256 timeline events')
    vehicles={v['id'] for v in catalog.get('vehicles',[])};walkers=set(catalog.get('walkers',[]));ids=set()
    result={'flows':[],'events':[]}
    def identity(item):
        uid=item.get('id','')
        if not isinstance(uid,str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,39}',uid) or uid in ids:raise ValueError('Give every flow and event a unique short identifier')
        ids.add(uid)
    def point(i,pool):
        if isinstance(i,bool) or not isinstance(i,int) or not 0<=i<len(pool):raise ValueError('Choose a valid spawn or destination point')
        return i
    def spawn(item,ped=False):
        model=item.get('model');pool=pedestrians if ped else points
        if model not in (walkers if ped else vehicles):raise ValueError('Choose a model from the loaded scene')
        return {'model':model,'spawn':point(item.get('spawn'),pool),'destination':point(item.get('destination'),pool)}
    for flow in flows:
        if not isinstance(flow,dict):raise ValueError('Invalid vehicle flow')
        identity(flow);count=number(flow.get('count'), 'Vehicle count',1,1000)
        if int(count)!=count:raise ValueError('Vehicle count must be an integer')
        result['flows'].append({'id':flow['id'],**spawn(flow),'start':number(flow.get('start',0),'Start time'),'interval':number(flow.get('interval',5),'Departure interval',1,3600),'count':int(count),'remove_arrived':bool(flow.get('remove_arrived',True))})
    spawn_refs={e.get('id') for e in events if isinstance(e,dict) and e.get('action') in ('spawn_vehicle','spawn_pedestrian')}
    for event in events:
        if not isinstance(event,dict):raise ValueError('Invalid timeline event')
        identity(event);action=event.get('action');row={'id':event['id'],'time':number(event.get('time',0),'Event time'),'action':action}
        if action in ('spawn_vehicle','spawn_pedestrian'):row.update(spawn(event,action=='spawn_pedestrian'))
        elif action=='destination':
            ref=event.get('actor')
            if str(ref) not in {str(i) for i in actor_ids} and ref not in spawn_refs:raise ValueError('Choose an existing actor or a named spawn event')
            row.update(actor=str(ref),destination=point(event.get('destination'),points))
        elif action=='weather':
            if event.get('preset') not in ('clear','rain','cloudy','sunset','night'):raise ValueError('Choose a weather preset')
            row['preset']=event['preset']
        elif action in ('signal_phase','signal_hold','signal_resume'):
            gid=event.get('group_id')
            if isinstance(gid,bool) or gid not in groups:raise ValueError('Choose a signal group')
            row['group_id']=gid
            if action=='signal_phase':
                index=event.get('index')
                if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(groups[gid]):raise ValueError('Choose a valid signal phase')
                row['index']=index
        else:raise ValueError('Unknown timeline action')
        result['events'].append(row)
    # Named actor destinations must run after their spawn event, including ties.
    ordering={e['id']:(e['time'],i) for i,e in enumerate(result['events'])}
    for i,e in enumerate(result['events']):
        if e['action']=='destination' and e['actor'] in spawn_refs and ordering[e['actor']]>(e['time'],i):raise ValueError('A destination event must follow its named spawn event')
    return result


class ScenarioSchedule:
    def __init__(self, execute, arrived, remove):
        self.execute=execute;self.arrived=arrived;self.remove=remove;self.config={'flows':[],'events':[]};self.running=False;self.epoch=0.;self.elapsed=0.;self.log=[];self.refs={};self.owned={};self.flows=[];self.events=[]
    def configure(self, config):
        if self.running:raise ValueError('Stop the schedule before editing it')
        self.config=copy.deepcopy(config)
    def start(self, now):
        if self.running:raise ValueError('The schedule is already armed')
        self.running=True;self.epoch=now;self.elapsed=0.;self.log=[];self.refs={};self.owned={}
        self.flows=[{'config':f,'departed':0,'spawned':0,'skipped':0,'retry_at':0.} for f in self.config['flows']]
        self.events=[{'config':e,'status':'pending'} for e in sorted(self.config['events'],key=lambda e:e['time'])]
    def stop(self):self.running=False
    def note(self, now, name, status, **extra):
        self.log.append({'time':round(now-self.epoch,3),'id':name,'status':status,**extra});self.log=self.log[-256:]
    def update(self, now):
        if not self.running:return
        self.elapsed=max(0,now-self.epoch)
        for aid,cleanup in list(self.owned.items()):
            if cleanup and self.arrived(aid):
                self.remove(aid);del self.owned[aid];self.note(now,str(aid),'removed after arrival')
        for event in self.events:
            e=event['config']
            if event['status']!='pending' or e['time']>self.elapsed+1e-7:continue
            try:
                actor=self.execute(e,self.refs);event['status']='executed'
                if actor is not None:self.refs[e['id']]=actor;self.owned[actor]=False
                self.note(now,e['id'],'executed',actor_id=actor)
            except Exception as error:event['status']='failed';self.note(now,e['id'],'failed',error=str(error))
        for flow in self.flows:
            f=flow['config'];due=f['start']+flow['departed']*f['interval']
            if flow['departed']>=f['count'] or due>self.elapsed+1e-7 or self.elapsed<flow['retry_at']:continue
            try:
                actor=self.execute({**f,'action':'spawn_vehicle'},self.refs);self.owned[actor]=f['remove_arrived'];flow['departed']+=1;flow['spawned']+=1
                self.note(now,f['id'],'departed',actor_id=actor)
            except Exception as error:
                if self.elapsed>=due+10:flow['departed']+=1;flow['skipped']+=1;self.note(now,f['id'],'skipped',error=str(error))
                else:flow['retry_at']=self.elapsed+1;self.note(now,f['id'],'waiting',error=str(error))
        if all(f['departed']>=f['config']['count'] for f in self.flows) and all(e['status']!='pending' for e in self.events) and not any(self.owned.values()):self.running=False
    def snapshot(self):return {'running':self.running,'elapsed':self.elapsed,'config':copy.deepcopy(self.config),'flows':[{k:v for k,v in f.items() if k!='config'}|{'id':f['config']['id']} for f in self.flows],'events':[{'id':e['config']['id'],'status':e['status']} for e in self.events],'log':copy.deepcopy(self.log[-40:]),'actors':dict(self.refs)}
