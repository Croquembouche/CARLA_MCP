"""Simulation-clock movement programs. Native packets drive TM, cameras and replay."""
from network_timing import NetworkTiming
import copy
import math
import xml.etree.ElementTree as ET

MOVES = ('left', 'straight', 'right')
VALUES = {'Stop': 0, 'Caution': 1, 'Protected': 2, 'Permissive': 3, 'Off': 4}


def unpack(word):
    return {m: list(VALUES)[(word >> (i*3)) & 7] for i,m in enumerate(MOVES)} if word & 0x8000 else None


def pack(states, now):
    return 0x8000 | (0x4000 if 'Permissive' in states.values() and int(now*2) % 2 == 0 else 0) | sum(VALUES[states[m]] << (i*3) for i,m in enumerate(MOVES))


def topology(xml, lanes, metadata):
    root = ET.fromstring(xml)
    signs = {}
    for road in root.findall('road'):
        for node in road.findall('./signals/*'):
            relation = node.find('./userData/vectorSignal')
            movement = relation.get('turnRelation', '').lower() if relation is not None else ''
            if movement not in MOVES: continue
            for valid in node.findall('validity'):
                for lane in range(int(valid.get('fromLane')), int(valid.get('toLane'))+1):
                    if lane: signs.setdefault(node.get('id'), {}).setdefault(movement, set()).add((int(road.get('id')), lane))
    result = {}
    for aid, meta in metadata.items():
        movements = {}
        for move, refs in signs.get(str(meta['opendrive_id']), {}).items():
            paths = [l['points'] for l in lanes if (int(l['id'].split(':')[0]), int(l['id'].split(':')[-1])) in refs]
            movements[move] = {'lanes': [f'{r}:{l}' for r,l in sorted(refs)], 'paths': paths}
        result[aid] = movements
    return result


def segment_distance(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/max(.0001,dx*dx+dy*dy)))
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def paths_conflict(paths_a, paths_b):
    # Lane-centre envelopes catch crossings and shared exit lanes, including
    # sampled curves. Conservative spacing avoids granting ambiguous protection.
    for a in paths_a:
        for b in paths_b:
            for p in a:
                for q,r in zip(b,b[1:]):
                    if abs(p[2]-q[2])<3 and segment_distance(p,q,r)<2.8: return True
            for p in b:
                for q,r in zip(a,a[1:]):
                    if abs(p[2]-q[2])<3 and segment_distance(p,q,r)<2.8: return True
    return False


class MovementPrograms:
    def __init__(self, world, xml, lanes, metadata):
        self.world=world;self.metadata=metadata;self.movements=topology(xml,lanes,metadata)
        self.programs={};self.sent={};self.now=0.;self.network=NetworkTiming(self)
        self.groups={m['group_id']:m['group_ids'] for m in metadata.values()}
        self.conflicts={}
        for gid,ids in self.groups.items():
            pairs=[]
            for ai,a in enumerate(ids):
                for b in ids[ai+1:]:
                    for am,av in self.movements[a].items():
                        for bm,bv in self.movements[b].items():
                            if paths_conflict(av['paths'],bv['paths']):pairs.append([[a,am],[b,bm]])
            self.conflicts[gid]=pairs

    def defaults(self,gid):
        phases=[]
        for aid in self.groups[gid]:
            if self.movements[aid]:
                phases.append({'name':f'Approach {aid}', 'duration':15., 'states':{str(aid):{m:'Protected' for m in self.movements[aid]}}})
        return phases

    def validate(self,gid,p):
        phases=p.get('phases',self.defaults(gid))
        if not isinstance(phases,list) or not 1<=len(phases)<=16:raise ValueError('Use 1–16 phases')
        result=[]
        for phase in phases:
            if not isinstance(phase,dict) or not isinstance(phase.get('states',{}),dict):raise ValueError('Each phase needs a states object keyed by approach ID')
            duration=phase.get('duration',15)
            if isinstance(duration,bool) or not isinstance(duration,(float,int)) or not math.isfinite(duration) or not .5<=duration<=600:raise ValueError('Phase duration must be 0.5–600 seconds')
            states={str(a):{m:'Stop' if m in self.movements[a] else 'Off' for m in MOVES} for a in self.groups[gid]}
            for aid, moves in phase.get('states',{}).items():
                if aid not in states:raise ValueError('Phase references an approach outside this group')
                if not isinstance(moves,dict):raise ValueError('Movement states must be an object')
                for m,v in moves.items():
                    if m not in MOVES or v not in ('Stop','Protected','Permissive','Off'):raise ValueError('Choose Stop, Protected, Permissive or Off')
                    if v=='Permissive' and m=='straight':raise ValueError('Permissive indications are for left and right turns')
                    if m not in self.movements[int(aid)] and v!='Off':raise ValueError(f'Approach {aid} has no mapped {m} movement')
                    states[aid][m]=v
            for (a,am),(b,bm) in self.conflicts[gid]:
                if states[str(a)][am]==states[str(b)][bm]=='Protected':raise ValueError(f'Conflicting protected movements: {a} {am} and {b} {bm}. Set a turn to Permissive or use separate phases.')
            result.append({'name':str(phase.get('name','Phase'))[:60], 'duration':float(duration), 'states':states})
        yellow=p.get('yellow_time',3.);red=p.get('all_red_time',2.)
        for v in (yellow,red):
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not .5<=v<=30:raise ValueError('Clearance intervals must be 0.5–30 seconds')
        return {'phases':result,'yellow_time':float(yellow),'all_red_time':float(red)}

    def apply(self,p,now):
        gid=p.get('group_id');op=p.get('operation')
        if isinstance(gid,bool) or not isinstance(gid,int) or gid not in self.groups:raise ValueError('Choose a signal group')
        if op not in ('enable','update','disable','hold','resume','phase'):raise ValueError('Invalid movement program operation')
        program=self.programs.get(gid)
        if op in ('hold','phase','disable') and self.network.config['mode']!='independent':self.network.configure({'mode':'independent'},now)
        if op in ('enable','update'):
            if self.network.config['mode']!='independent':raise ValueError('Choose Independent timing in Network before editing intersection plans')
            config=self.validate(gid,p)
            if program:
                program['pending']=config;program['disable']=False;program['next']=0;program['hold']=False
                self.clearance(program,now)
            else:
                if not all(self.movements[a] for a in self.groups[gid]):raise ValueError('This group has unmapped approaches; movement protection cannot be established')
                current={}
                for aid in self.groups[gid]:
                    actor=self.world.get_actor(aid)
                    if not hasattr(actor,'set_movement_states'):raise RuntimeError('Native movement-signal build is required')
                    green=str(actor.get_state()).split('.')[-1] in ('Green','Yellow')
                    current[str(aid)]={m:('Caution' if green else 'Stop') if m in self.movements[aid] else 'Off' for m in MOVES}
                self.world.get_actor(gid).freeze_group(True)
                program={**config,'index':0,'next':0,'stage':'yellow','since':now,'hold':False,'pending':None,'disable':False,'current':current}
                self.programs[gid]=program
        else:
            if not program:raise ValueError('Enable movement phases for this group first')
            if op=='hold':program['hold']=True
            elif op=='resume':program['hold']=False
            elif op=='phase':
                index=p.get('index')
                if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(program['phases']):raise ValueError('Choose a valid phase')
                program['next']=index;program['hold']=bool(p.get('hold',True));self.clearance(program,now)
            else:
                program['disable']=True;program['pending']=None;self.clearance(program,now)
        self.update(now)
        return self.snapshot()

    def clearance(self,p,now):
        if p['stage']=='green':
            p['stage']='yellow';p['since']=now
            p['current']={a:{m:'Caution' if v in ('Protected','Permissive') else v for m,v in moves.items()} for a,moves in p['current'].items()}

    def update(self,now):
        self.now=now
        for gid,p in list(self.programs.items()):
            elapsed=now-p['since']
            if p['stage']=='green' and not p['hold'] and self.network.green_finished(gid,p,now):
                p['next']=(p['index']+1)%len(p['phases']);self.clearance(p,now)
            elif p['stage']=='yellow' and elapsed+1e-7>=p['yellow_time']:
                p['stage']='all-red';p['since']=now
                p['current']={a:{m:'Off' if v=='Off' else 'Stop' for m,v in moves.items()} for a,moves in p['current'].items()}
            elif p['stage']=='all-red' and elapsed+1e-7>=p['all_red_time']:
                p['waiting_for_clearance']=self.occupied(gid)
                if p['waiting_for_clearance']:continue
                if p['disable']:
                    for aid in self.groups[gid]:self.world.get_actor(aid).set_movement_states(0);self.sent.pop(aid,None)
                    actor=self.world.get_actor(gid);actor.reset_group();actor.freeze_group(False)
                    del self.programs[gid];continue
                p['waiting_for_offset']=not self.network.can_release(gid,p,now)
                if p['waiting_for_offset']:continue
                if p['pending']:p.update(p.pop('pending'));p['pending']=None
                p['index']=p['next'];p['stage']='green';p['since']=now
                p['current']=copy.deepcopy(p['phases'][p['index']]['states'])
                self.network.released(gid,p,now)
            for aid,moves in p['current'].items():
                actor=self.world.get_actor(int(aid));word=pack(moves,now)
                # Native round-colour fallback is red: only movement-aware TM
                # grants entry. Original meshes are hidden by the native display.
                if self.sent.get(int(aid))!=word:
                    import carla
                    actor.set_state(carla.TrafficLightState.Red)
                    actor.set_movement_states(word);self.sent[int(aid)]=word

    def occupied(self,gid):
        if not hasattr(self.world,'get_actors'):return False
        paths=[path for a in self.groups[gid] for move in self.movements[a].values() for path in move['paths']]
        for actor in self.world.get_actors():
            if not actor.type_id.startswith(('vehicle.','walker.pedestrian.')):continue
            loc=actor.get_location();point=(loc.x,loc.y,loc.z)
            for path in paths:
                for a,b in zip(path,path[1:]):
                    if abs(loc.z-a[2])<3 and segment_distance(point,a,b)<2.5:return True
        return False

    def suspend(self):
        for gid in self.programs:
            for aid in self.groups[gid]:self.world.get_actor(aid).set_movement_states(0)
            actor=self.world.get_actor(gid);actor.reset_group();actor.freeze_group(False)
        self.programs={};self.sent={}

    def snapshot(self):
        return {str(g):{'active':g in self.programs, 'members':ids, 'conflicts':self.conflicts[g],
                       'defaults':self.defaults(g), **({k:copy.deepcopy(v) for k,v in self.programs[g].items() if k!='pending'} if g in self.programs else {}),
                       'elapsed':max(0,self.now-self.programs[g]['since']) if g in self.programs else 0} for g,ids in self.groups.items()}
