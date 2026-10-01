"""Parking overlays and physical occupancy.

Surveyed curb strips constrain parking positions. Unpainted along-curb divisions
remain planning estimates; these annotations do not create driving lanes.
"""
import math,json,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
from parking_rules import screen_spaces

def corners(x,y,length,width,yaw):
    a=math.radians(yaw);c,s=math.cos(a),math.sin(a)
    return [[x+c*u-s*v,y+s*u+c*v] for u,v in [(-length/2,-width/2),(length/2,-width/2),(length/2,width/2),(-length/2,width/2)]]

def overlaps(a,b):
    for polygon in (a,b):
        for p,q in zip(polygon,polygon[1:]+polygon[:1]):
            axis=(-(q[1]-p[1]),q[0]-p[0])
            av=[v[0]*axis[0]+v[1]*axis[1] for v in a];bv=[v[0]*axis[0]+v[1]*axis[1] for v in b]
            if max(av)<=min(bv) or max(bv)<=min(av):return False
    return True

def build_parking(wmap,opendrive,source):
    result={'parking_spaces':[],'parking_areas':[],'parking_source':'No parking annotations available for this map'}
    if not source.exists():return result
    data=json.loads(source.read_text())
    if data['map'].split('/')[-1]!=wmap.name.split('/')[-1]:return result
    if 'validated_spaces' in data:
        if data.get('validation',{}).get('opendrive_sha256')!=hashlib.sha256(opendrive.encode()).hexdigest():
            result['parking_source']='Parking annotations require revalidation for this OpenDRIVE revision'
            return result
        spaces=data['validated_spaces'];rules=data.get('traffic_rules');excluded=[]
        validation=data.get('validation',{})
        if validation.get('geometry_sha256'):
            town=wmap.name.split('/')[-1]
            scene_root=source.parent.parent/'scene-sources'/town
            if town=='Town10HD_Opt' and not scene_root.exists():
                scene_root=source.parent.parent/'scene-source'
            geometry=scene_root/'geometry.bin'
            scene=scene_root/'scene.json'
            if (not geometry.exists() or not scene.exists()
                or hashlib.sha256(geometry.read_bytes()).hexdigest()!=validation['geometry_sha256']
                or hashlib.sha256(scene.read_bytes()).hexdigest()!=validation.get('scene_sha256')):
                result['parking_source']='Parking survey requires revalidation for this scene geometry revision'
                return result
        # Sandbox policy: every geometry-validated bay is open unless occupied.
        # Keep the historical rule audit on disk, but do not withhold its bays.
        spaces=[{k:v for k,v in bay.items() if k!='restriction_reasons'} for bay in spaces]
        result.update(parking_spaces=spaces,parking_areas=data.get('areas',[]),
                      parking_curb_strips=data.get('curb_strips',[]),
                      parking_source=data.get("parking_note") or f"{len(spaces)} mapped parking positions, open unless occupied. Footprints use this town's native pavement and authored parking locations; unpainted divisions remain planning estimates.",
                      parking_validation=data['validation'],parking_excluded=excluded,
                      parking_rules={'enforcement':'disabled','availability':'open_or_occupied'})
        return result
    samples=[]
    for road in ET.fromstring(opendrive).findall('road'):
        sections=road.findall('./lanes/laneSection')
        for index,section in enumerate(sections):
            start=float(section.get('s'));end=float(sections[index+1].get('s')) if index+1<len(sections) else float(road.get('length'))
            for lane in section.findall('./*/lane'):
                if lane.get('type') not in ('shoulder','parking'):continue
                for i in range(max(1,math.ceil((end-start)/1.5))):
                    w=wmap.get_waypoint_xodr(int(road.get('id')),int(lane.get('id')),min(end-.01,start+.01+i*1.5))
                    if w and w.lane_width>=1.8 and not w.is_junction:samples.append(w)
    for meter in sorted(data['meters'],key=lambda m:(round(m['y']),m['x'])):
        if not samples:continue
        w=min(samples,key=lambda w:math.hypot(w.transform.location.x-meter['x'],w.transform.location.y-meter['y']))
        p=w.transform.location
        if math.hypot(p.x-meter['x'],p.y-meter['y'])>6:continue
        yaw=w.transform.rotation.yaw;a=math.radians(yaw);c,s=math.cos(a),math.sin(a)
        # Slide to the meter's along-curb coordinate rather than a sampled offset.
        along=(meter['x']-p.x)*c+(meter['y']-p.y)*s;x,y=p.x+along*c,p.y+along*s
        neighbors=[math.hypot(m['x']-meter['x'],m['y']-meter['y']) for m in data['meters'] if m is not meter and abs(-(m['x']-meter['x'])*s+(m['y']-meter['y'])*c)<1.5 and math.hypot(m['x']-meter['x'],m['y']-meter['y'])>.1]
        length=min(7.5,min(neighbors)-.6) if neighbors else 6.
        if length<5:continue
        result['parking_spaces'].append({'id':f'P{len(result["parking_spaces"])+1:03d}','x':x,'y':y,'z':p.z,'yaw':yaw,'length':length,'width':w.lane_width,'polygon':corners(x,y,length,w.lane_width,yaw),'source':'metered_curb_estimate','estimated':True,'meter':meter['name'],'lane':[w.road_id,w.section_id,w.lane_id]})
    result['parking_areas']=data.get('areas',[])
    result['parking_source']='Estimated metered bays from authored Unreal parking meters and OpenDRIVE curb shoulders; individual bay boundaries are not authored in this map'
    return result

def occupancy(spaces,static_boxes,actors):
    boxes=[(box['polygon'],box['z'],box['height'],{'kind':'scenery','name':box['name']}) for box in static_boxes]
    for a in actors:
        if not a['type'].startswith('vehicle.'):continue
        p=a['pose'];e=a.get('extent',{'x':2.5,'y':1.2,'z':1})
        boxes.append((corners(p['x'],p['y'],2*e['x'],2*e['y'],p['yaw']),p['z']+e['z'],2*e['z'],{'kind':'actor','id':a['id']}))
    # Axis-aligned bounds reject distant pairs before the exact polygon test.
    # Keep box order and the existing height/SAT checks for identical occupancy.
    def bounds(polygon):
        return (min(p[0] for p in polygon),min(p[1] for p in polygon),
                max(p[0] for p in polygon),max(p[1] for p in polygon))
    boxes=[(polygon,z,height,who,bounds(polygon)) for polygon,z,height,who in boxes]
    if not boxes:return {space['id']:None for space in spaces}
    # Large towns have thousands of bays; only nearby vehicle boxes need SAT.
    from math import floor
    cell_size=10;grid={};large=[]
    for i,(_,_,_,_,b) in enumerate(boxes):
        x0,y0,x1,y1=(floor(v/cell_size) for v in b)
        if (x1-x0+1)*(y1-y0+1)>256:large.append(i);continue
        for x in range(x0,x1+1):
            for y in range(y0,y1+1):grid.setdefault((x,y),[]).append(i)
    result={}
    for space in spaces:
        a=bounds(space['polygon']);x0,y0,x1,y1=(floor(v/cell_size) for v in a)
        candidates=set(large)
        for x in range(x0,x1+1):
            for y in range(y0,y1+1):candidates.update(grid.get((x,y),()))
        result[space['id']]=next((boxes[i][3] for i in sorted(candidates)
            if abs(boxes[i][1]-space['z'])<boxes[i][2]/2+1
            and a[0]<boxes[i][4][2] and boxes[i][4][0]<a[2] and a[1]<boxes[i][4][3] and boxes[i][4][1]<a[3]
            and overlaps(space['polygon'],boxes[i][0])),None)
    return result

def static_vehicles(world,carla):
    boxes=[]
    for label in (carla.CityObjectLabel.Car,carla.CityObjectLabel.Truck,carla.CityObjectLabel.Bus):
        for item in world.get_environment_objects(label):
            b=item.bounding_box
            if b.extent.x<.5 or b.extent.y<.4:continue
            boxes.append({'name':item.name,'z':b.location.z,'height':2*b.extent.z,'polygon':corners(b.location.x,b.location.y,2*b.extent.x,2*b.extent.y,b.rotation.yaw)})
    return boxes
