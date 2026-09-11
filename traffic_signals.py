"""Traffic-light controls, executed exclusively by the simulation owner."""
import math
import json
from pathlib import Path
_HEAD_FILE=Path(__file__).parent/"data/signal-head-topology.json"
_HEADS=json.loads(_HEAD_FILE.read_text()) if _HEAD_FILE.exists() else []
import carla

STATES=('Red','Yellow','Green','Off')

def metadata(actor):
    group=sorted({a.id for a in actor.get_group_traffic_lights() if a is not None}|{actor.id})
    boxes=actor.get_light_boxes()
    location=actor.get_location()
    exported=next((h for h in _HEADS if math.dist([location.x,location.y,location.z],[h['pose'][k] for k in ('x','y','z')])<.02),None)
    return {**({k:exported[k] for k in ('pedestrian_heads','push_buttons')} if exported else {}),'head_source':'Unreal vehicle lamp components' if exported else 'CARLA semantic boxes (unclassified)','group_ids':group,'group_id':min(group),'opendrive_id':actor.get_opendrive_id(),
            'heads':exported['heads'] if exported else [{'x':b.location.x,'y':b.location.y,'z':b.location.z,'yaw':b.rotation.yaw} for b in boxes]}

def apply(world,p):
    # Validate the entire payload before issuing any mutation.
    aid=p.get('id')
    if isinstance(aid,bool) or not isinstance(aid,int):raise ValueError('Choose a traffic-light ID')
    op=p.get('operation')
    if op not in ('state','timing','resume'):raise ValueError('Choose state, timing or resume')
    if op=='state':
        if p.get('state') not in STATES:raise ValueError('Signal state must be Red, Yellow, Green or Off')
        if not isinstance(p.get('hold',True),bool):raise ValueError('Hold must be true or false')
    if op=='timing':
        if p.get('scope','signal') not in ('signal','intersection'):raise ValueError('Invalid timing scope')
        times={}
        for k in ('green_time','yellow_time','red_time'):
            v=p.get(k)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not .1<=v<=600:raise ValueError('Each signal duration must be between 0.1 and 600 seconds')
            times[k]=float(v)
    actor=world.get_actor(aid)
    if not actor or not actor.type_id.startswith('traffic.traffic_light'):raise ValueError('Traffic light no longer exists; select a signal on the current map')
    group=[a for a in actor.get_group_traffic_lights() if a is not None]
    if not any(a.id==aid for a in group):group.append(actor)
    if not hasattr(actor,'freeze_group'):raise RuntimeError('The CARLA client with intersection-specific signal controls is required')
    if op=='state':
        if p.get('hold',True):
            actor.freeze_group(True)
            for other in group:other.set_state(carla.TrafficLightState.Red)
        actor.set_state(getattr(carla.TrafficLightState,p['state']))
    else:
        if op=='timing':
            for target in group if p.get('scope','signal')=='intersection' else [actor]:
                for k,v in times.items():getattr(target,'set_'+k)(v)
        # Restart a consistent intersection sequence before unfreezing it.
        actor.reset_group();actor.freeze_group(False)
    return {'id':aid,'operation':op,'group_ids':sorted(a.id for a in group),'hold':op=='state' and p.get('hold',True)}
