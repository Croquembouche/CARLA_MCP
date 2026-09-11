"""Observe movement entry boundaries and program consistency without controlling traffic."""
import math

def front(actor):
    p=actor['pose'];r=math.radians(p['yaw']);n=actor.get('extent',{}).get('x',0)
    return (p['x']+n*math.cos(r),p['y']+n*math.sin(r),p['z'])

def crosses_entry(previous,current,path):
    if len(path)<2:return False
    a,b=path[:2];dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
    if length<.01:return False
    dx/=length;dy/=length
    p,q=front(previous),front(current)
    before=(p[0]-a[0])*dx+(p[1]-a[1])*dy;after=(q[0]-a[0])*dx+(q[1]-a[1])*dy
    lateral=abs((q[0]-a[0])*dy-(q[1]-a[1])*dx)
    yaw=math.radians(current['pose']['yaw'])
    return before<0<=after and lateral<(a[3]/2 if len(a)>3 else 1.8) and abs(q[2]-a[2])<3 and math.cos(yaw)*dx+math.sin(yaw)*dy>.5

class SignalAudit:
    def __init__(self):self.previous=None;self.events=[];self.entries=0;self.active_entries={};self.violation_count=0;self.recent_violations=[]
    def observe(self,state):
        violations=[];programs=state.get('movement_programs',{})
        for gid,p in programs.items():
            if not p.get('active'):continue
            for (a,am),(b,bm) in p.get('conflicts',[]):
                if p.get('current',{}).get(str(a),{}).get(am)==p.get('current',{}).get(str(b),{}).get(bm)=='Protected':violations.append({'kind':'conflicting_protection','group':gid})
        if self.previous:
            old={a['id']:a for a in self.previous['actors']};signals=[a for a in self.previous['actors'] if a['type']=='traffic.traffic_light']
            for vehicle in state['actors']:
                if not vehicle['type'].startswith('vehicle.') or vehicle['id'] not in old:continue
                route=state.get('managed',{}).get(str(vehicle['id']),{}).get('route',[])
                candidates=[]
                for light in signals:
                    gid=light.get('group_id',light['id'])
                    active=self.active_entries.get(vehicle['id'])
                    if active and active[0]==gid:
                        x,y=vehicle['pose']['x'],vehicle['pose']['y'];bounds=active[1]
                        if bounds[0]-10<x<bounds[2]+10 and bounds[1]-10<y<bounds[3]+10:continue
                        self.active_entries.pop(vehicle['id'],None)
                    options=[]
                    for move,data in light.get('movement_lanes',{}).items():
                        for path in data.get('paths',[]):
                            score=sum(min(((p[0]-r['x'])**2+(p[1]-r['y'])**2 for r in route),default=1e9) for p in path[::max(1,len(path)//5)])
                            options.append((score,move,path))
                    if not options:continue
                    # Resolve the intended movement before testing its entry line.
                    # Different connector starts can be offset along the same approach.
                    best_move=min(options,key=lambda x:x[0])[1] if route else None
                    for score,move,path in options:
                        if best_move is not None and move!=best_move:continue
                        if crosses_entry(old[vehicle['id']],vehicle,path):candidates.append((score,light,move))
                if candidates:
                    _,light,move=min(candidates,key=lambda x:x[0]);self.entries+=1
                    gid=light.get('group_id',light['id'])
                    points=[p for other in signals if other.get('group_id',other['id'])==gid for data in other.get('movement_lanes',{}).values() for path in data.get('paths',[]) for p in path]
                    self.active_entries[vehicle['id']]=(gid,[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)])
                    # Native controllers publish movements=None until a turn
                    # program is enabled. Their shared colour still applies.
                    indication=(light.get('movements') or {}).get(move,light.get('state'))
                    event={'frame':state['frame'],'actor':vehicle['id'],'signal':light['id'],'movement':move,'indication':indication}
                    if indication in ('Stop','Off','Red'):violations.append({'kind':'entry_on_stop',**event})
                    self.events.append(event)
        self.previous=state
        self.events=self.events[-100:]
        self.violation_count+=len(violations);self.recent_violations=(self.recent_violations+violations)[-10:]
        return {'entries_observed':self.entries,'violation_count':self.violation_count,'recent_violations':self.recent_violations,'violations':violations,'recent_entries':self.events[-10:],
                'scope':'Movement-entry boundary observations and protected-conflict checks; yielding requires dedicated interaction tests'}
