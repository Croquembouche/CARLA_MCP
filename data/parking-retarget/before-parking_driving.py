"""Low-speed physical parking maneuvers, with Traffic Manager road handoff.

Plans are bounded curvature paths, checked against vehicle footprints and scene
bounds. Execution uses VehicleControl; it never moves actors with set_transform.
"""
import heapq,itertools,math,time,copy
import bootstrap,carla,parking
from lane_map import vehicle_route,traffic_path

def angle(a):return (a+math.pi)%(2*math.pi)-math.pi
def point(t):return dict(x=t.location.x,y=t.location.y,z=t.location.z,yaw=t.rotation.yaw)
def trip_status(trip):return {k:trip[k] for k in ('stage','bay','blocked','alignment_attempts','entry_strategy','motion') if k in trip}
def distance(a,b):return math.hypot(a['x']-b['x'],a['y']-b['y'])

class Obstacles:
    def __init__(self,boxes,length,width,offset=0):
        self.length=length;self.width=width;self.offset=offset;self.grid={}
        for polygon in boxes:
            xs,ys=zip(*polygon)
            for x in range(math.floor(min(xs)/8),math.floor(max(xs)/8)+1):
                for y in range(math.floor(min(ys)/8),math.floor(max(ys)/8)+1):self.grid.setdefault((x,y),[]).append(polygon)
    def clear(self,x,y,yaw):
        x+=self.offset*math.cos(yaw);y+=self.offset*math.sin(yaw)
        footprint=parking.corners(x,y,self.length+.12,self.width+.12,math.degrees(yaw));r=self.length/2+self.width/2
        seen=set()
        for gx in range(math.floor((x-r)/8),math.floor((x+r)/8)+1):
            for gy in range(math.floor((y-r)/8),math.floor((y+r)/8)+1):
                for poly in self.grid.get((gx,gy),[]):
                    if id(poly) in seen:continue
                    seen.add(id(poly))
                    if parking.overlaps(footprint,poly):return False
        return True

def connector(start,goal,reverse,radius,obstacles):
    """Cubic tangent connection, densely checked for clearance and curvature."""
    x,y,yaw=start;gx,gy,gyaw=goal;d=math.hypot(gx-x,gy-y)
    if d<.05:return [] if abs(angle(yaw-gyaw))<.08 else None
    sign=-1 if reverse else 1
    for tangent in (d,d*1.5,d*.7):
        ax,ay=sign*tangent*math.cos(yaw),sign*tangent*math.sin(yaw)
        bx,by=sign*tangent*math.cos(gyaw),sign*tangent*math.sin(gyaw)
        path=[];valid=True;n=max(8,math.ceil(d*4));previous=(x,y,yaw)
        for i in range(1,n+1):
            t=i/n;t2=t*t;t3=t2*t
            px=(2*t3-3*t2+1)*x+(t3-2*t2+t)*ax+(-2*t3+3*t2)*gx+(t3-t2)*bx
            py=(2*t3-3*t2+1)*y+(t3-2*t2+t)*ay+(-2*t3+3*t2)*gy+(t3-t2)*by
            dx=(6*t2-6*t)*x+(3*t2-4*t+1)*ax+(-6*t2+6*t)*gx+(3*t2-2*t)*bx
            dy=(6*t2-6*t)*y+(3*t2-4*t+1)*ay+(-6*t2+6*t)*gy+(3*t2-2*t)*by
            ddx=(12*t-6)*x+(6*t-4)*ax+(-12*t+6)*gx+(6*t-2)*bx
            ddy=(12*t-6)*y+(6*t-4)*ay+(-12*t+6)*gy+(6*t-2)*by
            yawp=angle(math.atan2(dy,dx)+(math.pi if reverse else 0))
            if abs(angle(yawp-previous[2]))>math.hypot(px-previous[0],py-previous[1])/radius+.03 or dx*dx+dy*dy<.01 or abs(dx*ddy-dy*ddx)/(dx*dx+dy*dy)**1.5>1/radius or not obstacles.clear(px,py,yawp):valid=False;break
            path.append(dict(x=px,y=py,yaw=math.degrees(yawp),reverse=reverse));previous=(px,py,yawp)
        if valid:return path
    return None

def maneuver(start,goal,obstacles,radius=5,budget=2.,final_reverse=None):
    a=(start['x'],start['y'],math.radians(start['yaw']));b=(goal['x'],goal['y'],math.radians(goal['yaw']))
    if not obstacles.clear(*a):raise ValueError('Vehicle is obstructed at its current position; clear nearby objects before driving')
    if not obstacles.clear(*b):raise ValueError('Parking approach or destination is obstructed')
    for reverse in ((False,True) if final_reverse is None else (final_reverse,)):
        path=connector(a,b,reverse,radius,obstacles)
        if path is not None:return [dict(start,reverse=reverse)]+[dict(p,z=goal.get('z',start.get('z',0))) for p in path]
    # Hybrid A*: forward/reverse bicycle arcs, with dense swept-footprint checks.
    serial=itertools.count();deadline=time.monotonic()+budget;queue=[(0,next(serial),0,a,False,None,[])];visited={};nodes=[]
    while queue and time.monotonic()<deadline and len(nodes)<18000:
        _,_,cost,pose,rev,parent,segment=heapq.heappop(queue);x,y,yaw=pose
        key=(round(x/.6),round(y/.6),round(yaw/math.radians(12)),rev)
        if visited.get(key,float('inf'))<=cost:continue
        visited[key]=cost;idx=len(nodes);nodes.append((parent,segment))
        if math.hypot(x-b[0],y-b[1])<18:
            for reverse in ((rev,not rev) if final_reverse is None else (final_reverse,)):
                tail=connector(pose,b,reverse,radius,obstacles)
                if tail is not None:
                    parts=[tail];at=idx
                    while at is not None:at,part=nodes[at];parts.append(part)
                    result=[dict(start,reverse=parts[-2][0]['reverse'] if len(parts)>1 and parts[-2] else False)]
                    result.extend(dict(p,z=start.get('z',0)+(goal.get('z',0)-start.get('z',0))*min(1,math.hypot(p['x']-a[0],p['y']-a[1])/max(.1,math.hypot(b[0]-a[0],b[1]-a[1])))) for part in reversed(parts) for p in part)
                    return result
        for reverse in (False,True):
            sign=-1 if reverse else 1
            for curvature in (-1/radius,0,1/radius):
                px,py,pa=x,y,yaw;path=[]
                for _ in range(4):
                    da=sign*.3*curvature;px+=sign*.3*math.cos(pa+da/2);py+=sign*.3*math.sin(pa+da/2);pa=angle(pa+da)
                    if math.hypot(px-a[0],py-a[1])>max(30,math.hypot(b[0]-a[0],b[1]-a[1])+15) or not obstacles.clear(px,py,pa):break
                    path.append(dict(x=px,y=py,yaw=math.degrees(pa),reverse=reverse))
                if len(path)!=4:continue
                newcost=cost+1.2*(1.4 if reverse else 1)+(2 if reverse!=rev else 0)+abs(curvature)*.3
                heuristic=math.hypot(px-b[0],py-b[1])+radius*.4*abs(angle(pa-b[2]))
                heapq.heappush(queue,(newcost+heuristic*1.3,next(serial),newcost,(px,py,pa),reverse,idx,path))
    raise ValueError('No clear parking maneuver found within the planning limit. Clear the exit or choose another bay')

def parking_entry(start,target,obstacles,radius,wheelbase,rear_axle=None):
    """Back into the bay, including a forward setup move when necessary.

    Only the short final alignment lies on the bay axis. A long inline staging
    segment would occupy the neighboring parking space. Hybrid search is free
    to drive forward to a setup pose, but its terminal connection must reverse.
    """
    # Bicycle arcs are defined at the rear axle. CARLA reports actor origins
    # near the body centre, so convert both poses and swept-box offsets.
    axle=wheelbase*.5 if rear_axle is None else rear_axle
    def rear(p):
        yaw=math.radians(p['yaw'])
        return dict(p,x=p['x']-axle*math.cos(yaw),y=p['y']-axle*math.sin(yaw))
    begin=rear(start);finish=rear(target);yaw=math.radians(target['yaw']);errors=[]
    swept=copy.copy(obstacles);swept.offset+=axle
    room=max(0.,(target['length']-obstacles.length)/2-.15)
    for lead in (min(1.,room),0.):
        staging=dict(finish,x=finish['x']+lead*math.cos(yaw),y=finish['y']+lead*math.sin(yaw))
        try:
            first=maneuver(begin,staging,swept,radius,final_reverse=True)
            last=connector((staging['x'],staging['y'],yaw),(finish['x'],finish['y'],yaw),True,radius,swept)
            if last is not None:
                return [dict(v,x=v['x']+axle*math.cos(math.radians(v['yaw'])),y=v['y']+axle*math.sin(math.radians(v['yaw'])),z=target.get('z',0)) for v in first+last]
        except ValueError as e:errors.append(str(e))
    raise ValueError(errors[-1] if errors else 'No clear reverse entry into this parking bay')

def rear_reference(path,index,end,pose,offset):
    """Continuous projection onto the current gear segment, at the rear axle."""
    def rear(v):
        h=math.radians(v['yaw']);return v['x']-offset*math.cos(h),v['y']-offset*math.sin(h)
    rx,ry=rear(pose);first=index
    while first>max(0,index-4) and path[first-1]['reverse']==path[index]['reverse']:first-=1
    best=None
    for j in range(first,min(end,index+40)):
        ax,ay=rear(path[j]);bx,by=rear(path[j+1]);dx,dy=bx-ax,by-ay;length=math.hypot(dx,dy)
        if length<1e-5:continue
        u=max(0.,min(1.,((rx-ax)*dx+(ry-ay)*dy)/(length*length)))
        px,py=ax+u*dx,ay+u*dy;error=math.hypot(rx-px,ry-py)
        dh=angle(math.radians(path[j+1]['yaw']-path[j]['yaw']))
        candidate=(error,j,px,py,math.radians(path[j]['yaw'])+u*dh,dh/length)
        if best is None or error<best[0]:best=candidate
    if best is None:
        px,py=rear(path[index]);best=(math.hypot(rx-px,ry-py),index,px,py,math.radians(path[index]['yaw']),0.)
    return best

class ParkingDriving:
    def __init__(self,owner):self.owner=owner;self.tm_port=getattr(owner,'tm_port',8005);self.fixtures=None;self.fixture_map=None;self.merge_points=None;self.rear_axles={}
    def obstacles(self,a,dynamic=True):
        o=self.owner;location=a.get_location();z=location.z;boxes=[]
        if self.fixtures is None or self.fixture_map!=o.map_data.get('name'):
            self.fixtures=[];self.fixture_map=o.map_data.get('name');self.merge_points=[w for w in o.wmap.generate_waypoints(5) if not w.is_junction]
            for label in ('Walls','Fences','Poles','GuardRail'):
                for b in o.world.get_level_bbs(getattr(carla.CityObjectLabel,label)):
                    self.fixtures.append(dict(x=b.location.x,y=b.location.y,z=b.location.z,yaw=b.rotation.yaw,extent=dict(x=b.extent.x,y=b.extent.y,z=b.extent.z)))
        for b in itertools.chain(o.map_data.get('buildings',[]),self.fixtures):
            e=b['extent']
            if math.hypot(b['x']-location.x,b['y']-location.y)>100+max(e['x'],e['y']):continue
            if b['z']+e['z']<z+.3 or b['z']-e['z']>z+2.:continue
            boxes.append(parking.corners(b['x'],b['y'],2*e['x'],2*e['y'],b['yaw']))
        boxes.extend(b['polygon'] for b in getattr(o,'parking_static',[]) if abs(b['z']-z)<b['height']/2+2)
        if dynamic:
            for other in o.world.get_actors():
                if other.id==a.id or not other.type_id.startswith(('vehicle.','walker.pedestrian.')):continue
                t=other.get_transform();b=other.bounding_box;c=t.transform(b.location)
                if abs(c.z-z)>b.extent.z+2:continue
                boxes.append(parking.corners(c.x,c.y,2*b.extent.x+.25,2*b.extent.y+.25,t.rotation.yaw+b.rotation.yaw))
        e=a.bounding_box.extent
        return Obstacles(boxes,2*e.x,2*e.y,a.bounding_box.location.x)
    def geometry(self,a):
        pc=a.get_physics_control();w=list(pc.wheels);e=a.bounding_box.extent
        xs=[v.location.x/100 for v in w]
        wheelbase=max(xs)-min(xs) if xs else 0
        if wheelbase<.5:
            # UE5 RPC wheel offsets may be zero: skeletal wheel bones give the
            # actual axle centres, including an asymmetric actor origin.
            try:
                xs=[t.location.x for name,t in zip(a.get_bone_names(),a.get_bone_relative_transforms()) if 'wheel' in name.lower() and 'steering' not in name.lower()]
                wheelbase=max(xs)-min(xs) if len(xs)>=2 else 0
            except (AttributeError,RuntimeError,TypeError):wheelbase=0
        if wheelbase<.5:wheelbase=max(1.2,e.x*1.2);rear=wheelbase/2
        else:rear=-min(xs)
        self.rear_axles[a.id]=rear
        steer=max((v.max_steer_angle for v in w),default=35)
        return wheelbase,max(20,min(85,steer)),max(3.,wheelbase/math.tan(math.radians(max(15,steer*.65))))
    def bay(self,aid,bid):
        o=self.owner;m=o.managed[aid];a=m['actor'];space=next((s for s in o.map_data.get('parking_spaces',[]) if s['id']==bid),None)
        if not space:raise ValueError('Choose a parking bay in this map')
        if m['role']!='background':raise ValueError('Parking destinations are for background vehicles')
        e=a.bounding_box.extent
        if e.x*2+.1>space['length'] or e.y*2+.1>space['width']:raise ValueError(f'Vehicle needs {2*e.x+.1:.1f} × {2*e.y+.1:.1f} m; bay {bid} is {space["length"]:.1f} × {space["width"]:.1f} m')
        for otherid,other in o.managed.items():
            if otherid!=aid and other.get('parking_trip',{}).get('bay')==bid:raise ValueError(f'Bay {bid} is reserved by vehicle {otherid}')
        actors=[v for v in o.state.get('actors',[]) if v['id']!=aid]
        if parking.occupancy([space],getattr(o,'parking_static',[]),actors)[bid]:raise ValueError(f'Bay {bid} is occupied')
        # Bay centres describe the bounding box centre, whereas controls use actor origin.
        yaw=math.radians(space['yaw']);offset=a.bounding_box.location.x
        return dict(space,x=space['x']-offset*math.cos(yaw),y=space['y']-offset*math.sin(yaw))
    def check_junctions(self,path):
        for p in path[::4]:
            w=self.owner.wmap.get_waypoint(carla.Location(x=p['x'],y=p['y'],z=p.get('z',0)),project_to_road=False,lane_type=carla.LaneType.Driving)
            if w and w.is_junction:raise ValueError('Parking maneuver crosses a junction; a clear connection to a non-junction road is required')
    def assign(self,aid,p):
        o=self.owner;m=o.managed[aid];a=m['actor'];start=point(a.get_transform());wb,steer,radius=self.geometry(a);obstacles=self.obstacles(a)
        bid=p.get('parking_space');space=self.bay(aid,bid) if bid else None
        entry=[]
        if space:
            target=space;near=o.wmap.get_waypoint(carla.Location(x=space['x'],y=space['y'],z=space['z']),lane_type=carla.LaneType.Driving)
            if not near or near.is_junction:raise ValueError('This bay has no non-junction driving-lane approach')
            # Match bay orientation to the adjacent legal lane, including opposite-facing scenery.
            target=dict(target,yaw=near.transform.rotation.yaw)
            errors=[]
            # TM pulls past the bay in the adjacent driving lane. The local
            # planner then backs in, instead of starting far behind the bay.
            for approach in (max(14.,radius*3),12.,10.,7.):
                choices=near.next(approach)
                if not choices or choices[0].is_junction:continue
                try:road_goal=choices[0];entry=parking_entry(point(road_goal.transform),target,obstacles,radius,wb,self.rear_axles[a.id]);break
                except ValueError as e:errors.append(str(e))
            else:raise ValueError(errors[-1] if errors else 'Not enough clear approach lane before this bay')
        else:road_goal=o.waypoint(p);target=point(road_goal.transform)
        closest=o.wmap.get_waypoint(a.get_location(),lane_type=carla.LaneType.Driving)
        if not closest:raise ValueError('No road connection for this vehicle')
        road_start=closest;exit_path=[];direct=False
        on_road=distance(start,point(closest.transform))<1.1 and abs(angle(math.radians(start['yaw']-closest.transform.rotation.yaw)))<.25 and not m.get('parked')
        if space and (m.get('parked') or on_road) and distance(start,target)<25 and (closest.road_id,closest.lane_id)==(near.road_id,near.lane_id):
            try:entry=parking_entry(start,target,obstacles,radius,wb,self.rear_axles[a.id]);direct=True
            except ValueError:pass
        if not on_road and not direct:
            errors=[]
            if not obstacles.clear(start['x'],start['y'],math.radians(start['yaw'])):raise ValueError('Vehicle is obstructed at its current position; clear nearby objects before driving')
            candidates=[]
            for forward in (max(10.,radius*2),max(16.,radius*3),4.):candidates.extend(w for w in closest.next(forward) if not w.is_junction)
            # Scenery in yards may be closest to a junction; search nearby legal merges too.
            candidates.extend(sorted((w for w in self.merge_points if w.transform.location.distance(a.get_location())<100),key=lambda w:w.transform.location.distance(a.get_location()))[:10])
            deadline=time.monotonic()+6
            for candidate in candidates:
                if time.monotonic()>deadline:break
                if abs(candidate.transform.location.z-start['z'])>2:continue
                try:
                    exit_path=maneuver(start,point(candidate.transform),obstacles,radius,budget=min(1.,max(.05,deadline-time.monotonic())))
                    self.check_junctions(exit_path);road_start=candidate;break
                except ValueError as e:errors.append(str(e))
            else:raise ValueError(errors[-1] if errors else 'No clear road merge near this parked vehicle')
        self.check_junctions(exit_path);self.check_junctions(entry)
        committed=None
        if on_road and m.get('planner')=='tm' and not m.get('arrived'):
            actions=o.tm.get_all_actions(a)
            if actions:committed=actions[0][1]
        route,kept=([],False) if direct else vehicle_route(o.planner,road_start.transform.location,road_goal.transform.location,committed)
        road=[dict(x=w.transform.location.x,y=w.transform.location.y,z=w.transform.location.z) for w,_ in route]
        if not direct:road.append(dict(x=road_goal.transform.location.x,y=road_goal.transform.location.y,z=road_goal.transform.location.z))
        tm_path=[dict(x=v.x,y=v.y,z=v.z) for v in traffic_path(route,road_goal.transform.location)]
        trip=dict(road_goal_lane=[road_goal.road_id,road_goal.section_id,road_goal.lane_id],tm_path=tm_path,stage='entering' if direct else 'leaving' if exit_path else 'driving',bay=bid,exit=exit_path,entry=entry,road=road,index=0,wheelbase=wb,rear_axle=self.rear_axles[a.id],max_steer=steer,road_goal=point(road_goal.transform),target=target,blocked=None,entry_strategy='reverse_in' if bid else None,motion=None)
        # All planning and reservation checks finish before the old goal/control changes.
        a.set_autopilot(False,self.tm_port)
        if m.get('physics_sleeping'):a.set_simulate_physics(True)
        m.update(parked=False,physics_sleeping=False,planner='tm',parking_space=None,parking_trip=trip,arrived=False,approach_slowdown=False)
        m['destination']={k:target[k] for k in ('x','y','z')}
        if bid:m['destination']['parking_space']=bid
        m['route']=exit_path+road+entry
        m['route_update']=dict(revision=m.get('route_update',{}).get('revision',0)+1,frame=o.state.get('frame',0),preserved_junction=kept,execution='parking_and_traffic_manager')
        if not exit_path and not direct:self.road(m)
        else:a.apply_control(carla.VehicleControl(brake=1.))
        o.refresh();return {**{k:m[k] for k in ('route','destination','route_update','arrived','parked','parking_space','planner')},'parking_trip':trip_status(trip)}
    def road(self,m):
        o=self.owner;a=m['actor'];t=m['parking_trip'];t.update(stage='driving',index=0,blocked=None,motion='forward')
        a.set_autopilot(True,self.tm_port);o.tm.ignore_lights_percentage(a,0.);o.tm.ignore_signs_percentage(a,0.)
        o.tm.auto_lane_change(a,False);o.tm.vehicle_percentage_speed_difference(a,0)
        o.tm.set_path(a,[carla.Location(**p) for p in t['tm_path']],True)
    @staticmethod
    def hold(a,hand_brake=False):
        control=a.get_control()
        return carla.VehicleControl(brake=1,hand_brake=hand_brake,reverse=control.reverse,
                                    manual_gear_shift=True,gear=control.gear)
    def tick(self,m,snapshot):
        t=m['parking_trip'];a=m['actor'];p=point(snapshot.get_transform());speed=snapshot.get_velocity().length();o=self.owner
        if t['stage']=='parked':return self.hold(a,True)
        if t['stage']=='driving':
            d=distance(p,t['road_goal'])
            lane=o.wmap.get_waypoint(snapshot.get_transform().location,lane_type=carla.LaneType.Driving)
            on_target_lane=lane is not None and [lane.road_id,lane.section_id,lane.lane_id]==t['road_goal_lane']
            if d<25 and on_target_lane:o.tm.set_desired_speed(a,max(3.,min(18.,3.6*math.sqrt(max(.1,2*(d-1.))))))
            if d>2.5 or not on_target_lane:return None
            a.set_autopilot(False,self.tm_port)
            if not t['entry']:
                t['stage']='arrived';m['arrived']=speed<.12;return self.hold(a)
            t.update(stage='stopping',index=0,blocked=None,motion='stopping')
        if t['stage']=='stopping':
            if speed>.12:return self.hold(a)
            t.update(stage='entering',index=0,blocked=None)
            # The actual TM stopping pose differs from the planned approach.
            try:
                entry=parking_entry(p,t['target'],self.obstacles(a),self.geometry(a)[2],t['wheelbase'],t.get('rear_axle'));self.check_junctions(entry)
                t['entry']=entry;m['route']=entry
            except ValueError as e:t.update(stage='blocked',blocked=str(e));return self.hold(a)
        if t['stage']=='arrived':m['arrived']=speed<.12;return self.hold(a)
        if t['stage']=='blocked':return self.hold(a)
        path=t['exit'] if t['stage']=='leaving' else t['entry'];i=t['index']
        # Track progress by nearest point, allowing small lateral tracking error.
        # A gear-change cusp remains a mandatory stop.
        reverse=path[i]['reverse'];t['motion']='reversing' if reverse else 'forward';end=i
        while end<len(path)-1 and path[end+1]['reverse']==reverse:end+=1
        i=rear_reference(path,i,end,p,t.get('rear_axle',t['wheelbase']*.5))[1]
        if end<len(path)-1 and distance(p,path[end])<.18 and speed<.12:
            i=end+1;reverse=path[i]['reverse'];t['motion']='changing_gear';end=i
            while end<len(path)-1 and path[end+1]['reverse']==reverse:end+=1
        t['index']=i
        if distance(p,path[i])>3:
            t.update(stage='blocked',blocked='Vehicle deviated from its parking path; apply the destination again to replan')
            return self.hold(a)
        remaining=distance(p,path[end])
        final_yaw=math.radians(path[end]['yaw']);along_to_end=abs((p['x']-path[end]['x'])*math.cos(final_yaw)+(p['y']-path[end]['y'])*math.sin(final_yaw))
        reached=remaining<.4 if t['stage']=='leaving' else along_to_end<.18 and remaining<.6
        if end==len(path)-1 and reached:
            if speed>.12:return self.hold(a)
            if t['stage']=='leaving':self.road(m);return None
            yaw_error=abs(angle(math.radians(p['yaw']-t['target']['yaw'])))
            target=t['target'];heading=math.radians(target['yaw']);dx=p['x']-target['x'];dy=p['y']-target['y'];e=a.bounding_box.extent
            across=abs(-dx*math.sin(heading)+dy*math.cos(heading))+e.y*abs(math.cos(yaw_error))+e.x*abs(math.sin(yaw_error))
            along=abs(dx*math.cos(heading)+dy*math.sin(heading))+e.x*abs(math.cos(yaw_error))+e.y*abs(math.sin(yaw_error))
            if yaw_error>math.radians(6) or across>target['width']/2 or along>target['length']/2:
                if t.get('alignment_attempts',0)<2:
                    try:
                        correction=parking_entry(p,target,self.obstacles(a),self.geometry(a)[2],t['wheelbase'],t.get('rear_axle'))
                        self.check_junctions(correction)
                        t.update(entry=correction,index=0,alignment_attempts=t.get('alignment_attempts',0)+1,progress_time=o.world.get_snapshot().timestamp.elapsed_seconds,progress_pose=p)
                        m['route']=correction
                        return self.hold(a)
                    except ValueError as e:t['blocked']=str(e)
                t.update(stage='blocked',blocked=t.get('blocked') or 'Parking alignment incomplete; clear maneuvering space and apply the bay destination again')
                return self.hold(a)
            t.update(stage='parked',blocked=None,motion='stopped');m.update(parked=True,parking_space=t['bay'],arrived=True)
            a.apply_control(self.hold(a,True));a.set_simulate_physics(False);m['physics_sleeping']=True
            return self.hold(a,True)
        # Collision look-ahead includes actors moving into a previously clear maneuver.
        obstacles=self.obstacles(a);look=i
        while look<end and distance(path[i],path[look])<max(3.,speed*2):look+=1
        hazard=any(not obstacles.clear(v['x'],v['y'],math.radians(v['yaw'])) for v in path[i:look+1:2])
        if hazard:
            t.update(blocked='Waiting for vehicle or pedestrian to clear the maneuver',progress_time=o.world.get_snapshot().timestamp.elapsed_seconds,progress_pose=p)
            return self.hold(a)
        t['blocked']=None
        # Rear-axle path tracking with curvature feed-forward and heading /
        # cross-track feedback. Heading control remains defined at an endpoint,
        # unlike chasing a point behind the vehicle after a small overshoot.
        body_yaw=math.radians(p['yaw']);yaw=body_yaw+(math.pi if reverse else 0)
        axle=t.get('rear_axle',t['wheelbase']*.5)
        rx=p['x']-axle*math.cos(body_yaw);ry=p['y']-axle*math.sin(body_yaw)
        _,_,tx,ty,desired,curvature=rear_reference(path,i,end,p,axle)
        cross=-(tx-rx)*math.sin(yaw)+(ty-ry)*math.cos(yaw)
        sign=-1 if reverse else 1
        turn=sign*(math.atan(t['wheelbase']*curvature)+1.3*angle(desired-body_yaw)+math.atan2(1.5*cross,.7+speed))
        # ChaosVehicleMovementComponent defaults to SquaredFunction steering.
        # Invert that shaping here; road TM keeps its existing input behavior.
        normalized=max(-1,min(1,turn/math.radians(t['max_steer'])))
        steering=math.copysign(math.sqrt(abs(normalized)),normalized)
        target_speed=min(1.2 if not reverse else .8,max(.25,remaining*.7))
        if end<len(path)-1 and remaining<.16:target_speed=0
        current_reverse=a.get_control().reverse
        if current_reverse!=reverse and speed>.12:
            t['motion']='changing_gear';return self.hold(a)
        throttle=min(.45,max(0,.22+(target_speed-speed)*.35)) if speed<target_speed else 0
        brake=min(1,max(0,(speed-target_speed)*.7))
        # Expose a stalled physical vehicle instead of reporting successful motion.
        now=o.world.get_snapshot().timestamp.elapsed_seconds
        if distance(p,t.get('progress_pose',p))>.25 or 'progress_time' not in t:t.update(progress_pose=p,progress_time=now)
        elif now-t['progress_time']>12:t.update(stage='blocked',blocked='Vehicle could not move through the physical scene. Clear its exit and apply the destination again');return self.hold(a)
        return carla.VehicleControl(throttle=throttle,brake=brake,steer=steering,reverse=reverse,manual_gear_shift=True,gear=-1 if reverse else 1)
