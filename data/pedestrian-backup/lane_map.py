"""Road markings derived from CARLA's driving waypoints and junction connectivity."""
import math
from collections import defaultdict, deque

def lane_key(w): return (w.road_id, w.section_id, w.lane_id)

def turn_options(end):
    # Only inspect the immediately connected junction, not a later intersection.
    pending=deque((w,False,0.) for w in end.next(2.0));seen=set();turns=set()
    heading=math.radians(end.transform.rotation.yaw)
    while pending and len(seen)<3000:
        w,entered,distance=pending.popleft()
        key=(w.id,entered)
        if key in seen or distance>150:continue
        seen.add(key)
        if not w.is_junction:
            if entered:
                delta=(w.transform.rotation.yaw-math.degrees(heading)+180)%360-180
                turns.add('straight' if abs(delta)<35 else 'uturn' if abs(delta)>150 else 'right' if delta>0 else 'left')
                continue
            if distance>5:continue
        for n in w.next(2.):pending.append((n,entered or w.is_junction,distance+2))
    return [t for t in ('left','straight','right','uturn') if t in turns]

def build_lanes(wmap):
    groups=defaultdict(list)
    for w in wmap.generate_waypoints(2):groups[lane_key(w)].append(w)
    lanes=[];allpoints=[];markings=[]
    for key,waypoints in groups.items():
        ordered=sorted(waypoints,key=lambda w:w.s)
        # Infer travel order from the actual forward vector, including positive lanes.
        if len(ordered)>1:
            a,b=ordered[:2];f=a.transform.get_forward_vector();d=b.transform.location-a.transform.location
            if f.x*d.x+f.y*d.y<0:ordered.reverse()
        points=[];travel=18.
        for i,w in enumerate(ordered):
            p=w.transform.location;yaw=w.transform.rotation.yaw
            points.append([round(p.x,3),round(p.y,3),round(p.z,3),round(w.lane_width,2),round(yaw,2)])
            allpoints.append((p.x,p.y))
            if i:travel+=p.distance(ordered[i-1].transform.location)
            if travel>=18 and not w.is_junction:
                markings.append({'x':p.x,'y':p.y,'z':p.z,'yaw':yaw,'kind':'direction','lane':':'.join(map(str,key))});travel=0
        turns=turn_options(ordered[-1]) if not ordered[-1].is_junction else []
        if turns:
            w=ordered[max(0,len(ordered)-6)];p=w.transform.location
            markings.append({'x':p.x,'y':p.y,'z':p.z,'yaw':w.transform.rotation.yaw,'kind':'turns','turns':turns,'lane':':'.join(map(str,key))})
        lanes.append({'id':':'.join(map(str,key)),'points':points,'maneuvers':turns,'junction':ordered[0].is_junction,'point_order':'driving direction'})
    bounds=[min(p[0] for p in allpoints),min(p[1] for p in allpoints),max(p[0] for p in allpoints),max(p[1] for p in allpoints)]
    return lanes,bounds,markings

def traffic_path(path,target):
    """TM selects a junction branch using the next imported point's exit road.

    Dense GRP samples inside junctions confuse that heuristic. Supply the ends
    of non-junction lane segments instead, retaining lane-change segments.
    """
    anchors=[];segment=[];key=None
    for w,_ in path:
        k=lane_key(w) if not w.is_junction else None
        if k!=key:
            if segment:anchors.append(segment[-1].transform.location)
            segment=[];key=k
        if k is not None:segment.append(w)
    if segment:anchors.append(segment[-1].transform.location)
    if not anchors or anchors[-1].distance(target)>.1:anchors.append(target)
    # Suppress duplicate points; never submit an empty path.
    return [p for i,p in enumerate(anchors) if not i or p.distance(anchors[i-1])>.1]
