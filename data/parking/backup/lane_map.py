"""Road markings derived from CARLA's driving waypoints and junction connectivity."""
import math
import xml.etree.ElementTree as ET
from collections import defaultdict, deque

def lane_key(w): return (w.road_id, w.section_id, w.lane_id)

def build_pedestrian_lanes(wmap, opendrive):
    """Sample explicit sidewalk sections; never join unrelated sidewalk endpoints."""
    lanes=[]
    for road in ET.fromstring(opendrive).findall('road'):
        sections=road.findall('./lanes/laneSection')
        for index,section in enumerate(sections):
            start=float(section.get('s'));end=float(sections[index+1].get('s')) if index+1<len(sections) else float(road.get('length'))
            for lane in section.findall('./*/lane'):
                if lane.get('type')!='sidewalk' or end-start<.02:continue
                count=max(1,math.ceil((end-start)/2));points=[]
                for i in range(count+1):
                    s=start+.01+(end-start-.02)*i/count
                    w=wmap.get_waypoint_xodr(int(road.get('id')),int(lane.get('id')),s)
                    if not w or w.section_id!=index or w.lane_width<.1:continue
                    p=w.transform.location
                    points.append([round(p.x,3),round(p.y,3),round(p.z,3),round(w.lane_width,3)])
                if len(points)>1:lanes.append({'id':f'{road.get("id")}:{index}:{lane.get("id")}','type':'sidewalk','points':points,'bidirectional':True})
    crossings=[];polygon=[]
    for p in wmap.get_crosswalks():
        point=[round(p.x,3),round(p.y,3),round(p.z,3)]
        if len(polygon)>=3 and math.dist(point,polygon[0])<.02:
            crossings.append({'points':polygon});polygon=[]
        else:polygon.append(point)
    return {'pedestrian_lanes':lanes,'crosswalks':crossings,'pedestrian_source':'OpenDRIVE sidewalks and crosswalk outlines; CARLA walker navigation determines traversability'}

def pedestrian_point(data,point):
    """Project onto nearby sidewalks or an existing sampled navigation location."""
    x,y,z=(float(point.get(k,0)) for k in ('x','y','z'))
    if not all(math.isfinite(v) for v in (x,y,z)):raise ValueError('Invalid pedestrian point')
    best=None;distance=float('inf')
    for lane in data.get('pedestrian_lanes',[]):
        for a,b in zip(lane['points'],lane['points'][1:]):
            dx,dy=b[0]-a[0],b[1]-a[1];length=dx*dx+dy*dy
            t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/length)) if length else 0
            p=[a[i]+t*(b[i]-a[i]) for i in range(3)];d=math.hypot(p[0]-x,p[1]-y)
            if d<distance and d<=max(5,(a[3]+t*(b[3]-a[3]))/2+2):best=dict(zip(('x','y','z'),p));distance=d
    for p in data.get('pedestrian_points',[]):
        d=math.hypot(p['x']-x,p['y']-y)
        if d<=2 and d<distance:best={k:p[k] for k in ('x','y','z')};distance=d
    if best is None:raise ValueError('Pick a blue sidewalk or a pedestrian navigation point')
    return best

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

def vehicle_route(planner,location,target,committed=None):
    """Plan from TM's actual lane, keeping a junction connector already entered.

    Junction connectors overlap. GRP's nearest-road localization may choose a
    different turn at the same position, which TM cannot reach after branching.
    Its retained front waypoint is authoritative for the current connector.
    """
    prefix=[]
    if committed is not None and committed.transform.location.distance(location)<10:
        waypoint=committed
        for _ in range(256):
            if not waypoint.is_junction:break
            prefix.append((waypoint,None))
            following=waypoint.next(2.)
            if len(following)!=1:raise ValueError('Cannot resolve the current junction exit; try again after leaving the junction')
            waypoint=following[0]
        else:raise ValueError('Current junction exceeds the routing limit')
        location=waypoint.transform.location
    remainder=planner.trace_route(location,target)
    if not remainder:raise ValueError('No drivable route to this destination')
    return prefix+remainder,bool(prefix)
