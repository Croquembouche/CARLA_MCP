"""Map-specific parking footprints constrained by native pavement triangles.

Uses authored parking lanes (or wide curb shoulders adjoining sidewalks), plus
existing authored parked-car poses. Does not invent curb bays on narrow shoulders
or infer permission from arbitrary roadside points. Unpainted divisions are
explicit planning estimates. Never replaces the hand-surveyed Town10 inventory.
"""
import argparse,hashlib,json,math,sys,xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
import numpy as np
from shapely import polygons,area,union_all
from shapely.geometry import Polygon
from shapely.strtree import STRtree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bootstrap,carla
from towns import available_towns,MAPS
from parking import corners

def rotation(q):
    x,y,z,w=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

def surface_kind(mesh,material):
    m=(material or '').lower();p=mesh.lower()
    if any(t in m for t in ('lanemark','marking','curb','gutter','grass','soil','gravel')):return None
    if any(t in m for t in ('asphalt','wetroad','road_asphalt')) or m.rsplit('/',1)[-1].startswith(('m_road','mi_road')):return 'pavement'
    if '/road/' in p and not any(t in p for t in ('manhole','sidewalk','curb')) and not any(t in m for t in ('sidewalk','concrete','terrain')):return 'pavement'
    return None

class Pavement:
    def __init__(self,scene,blob,include_markings=False,include_ground=False,min_base_fraction=0.):
        pieces=[];heights=[];vertex_heights=[];base_pavement=[];anchors=[]
        for g in scene['groups'].values():
            mesh=scene['meshes'][g['mesh']]
            if '/Parked/' in g['mesh']:
                for t in g['transforms']:
                    forward=rotation(t[3:7])@np.array([1.,0.,0.])
                    anchors.append(dict(x=t[0],y=t[2],z=t[1],yaw=math.degrees(math.atan2(forward[2],forward[0])),mesh=g['mesh']))
            if g['category']!='roads':continue
            for section in mesh['sections']:
                slot=section['slot'];material=g['materials'][slot] if 0<=slot<len(g['materials']) else None
                if surface_kind(g['mesh'],material) is None and not (include_markings and ('/RoadLine/' in g['mesh'] or any(k in (material or '').lower() for k in ('marking','lanemark')))) and not (include_ground and '/Terrain/' in g['mesh']):continue
                v=np.frombuffer(blob,dtype='<f4',count=section['position'][1],offset=section['position'][0]).reshape(-1,3)
                ix=np.frombuffer(blob,dtype='<u4',count=section['index'][1],offset=section['index'][0]).reshape(-1,3)
                for t in g['transforms']:
                    tri=((v*np.array(t[7:]))@rotation(t[3:7]).T+np.array(t[:3]))[ix]
                    ps=polygons(tri[:,:,[0,2]]);valid=area(ps)>1e-7
                    pieces.extend(ps[valid]);base_pavement.extend([surface_kind(g['mesh'],material) is not None]*int(np.sum(valid)));heights.extend(np.mean(tri[valid,:,1],axis=1));vertex_heights.extend(tri[valid,:,1])
        self.base_pavement=np.array(base_pavement,dtype=bool);self.min_base_fraction=min_base_fraction;self.polygons=np.array(pieces,dtype=object);self.heights=np.array(heights);self.vertex_heights=np.array(vertex_heights).reshape(-1,3);self.tree=STRtree(self.polygons);self.anchors=anchors
    def fits(self,bay):
        footprint=Polygon(bay['polygon']);indices=self.tree.query(footprint)
        indices=indices[(self.vertex_heights[indices].min(axis=1)<=bay['z']+.65)&(self.vertex_heights[indices].max(axis=1)>=bay['z']-.65)]
        if not len(indices):return False
        # Small tolerance only closes numerical seams; it cannot bridge a curb.
        surface=union_all(self.polygons[indices]).buffer(.025)
        if not surface.covers(footprint):return False
        if self.min_base_fraction:
            base=union_all(self.polygons[indices[self.base_pavement[indices]]])
            if base.intersection(footprint).area<footprint.area*self.min_base_fraction:return False
        elevations=[]
        for x,y in bay['polygon']:
            matches=[]
            for i in indices:
                tri=np.asarray(self.polygons[i].exterior.coords)[:3]
                matrix=np.vstack([tri.T,np.ones(3)])
                weights=np.linalg.solve(matrix,np.array([x,y,1.]))
                if weights.min()>=-.002 and weights.max()<=1.002:
                    matches.append(float(weights@self.vertex_heights[i]))
            if not matches:return False
            elevations.append(min(matches,key=lambda z:abs(z-bay['z'])))
        if max(elevations)-min(elevations)>.5:return False
        bay['corner_z']=elevations;bay['z']=sum(elevations)/len(elevations)+.02
        return True

def generate(town,source):
    scene=json.loads((source/'scene.json').read_text());blob=(source/'geometry.bin').read_bytes()
    if scene['map'].split('/')[-1]!=town['name'] or scene['errors']:raise ValueError('Wrong or incomplete scene')
    level=MAPS.parent.parent/(town['id'].removeprefix('/Game/')+'.umap');xodr=(level.parent/'OpenDrive'/(town['name']+'.xodr')).read_text();wmap=carla.Map(town['name'],xodr)
    surface=Pavement(scene,blob,include_markings=True,min_base_fraction=.8);spaces=[];rejected=Counter();grid={}
    def add(q):
        q['polygon']=corners(q['x'],q['y'],q['length'],q['width'],q['yaw'])
        if not surface.fits(q):rejected['outside_pavement']+=1;return
        poly=Polygon(q['polygon']);cell=(math.floor(q['x']/10),math.floor(q['y']/10))
        for x in range(cell[0]-1,cell[0]+2):
            for y in range(cell[1]-1,cell[1]+2):
                if any(abs(z-q['z'])<2 and poly.intersects(p.buffer(.25)) for p,z in grid.get((x,y),[])):rejected['overlap']+=1;return
        q['id']=f'P{len(spaces)+1:04d}';q['estimated']=True;spaces.append(q);grid.setdefault(cell,[]).append((poly,q['z']))
    for road in ET.fromstring(xodr).findall('road'):
        if road.get('junction')!='-1':continue
        sections=road.findall('./lanes/laneSection')
        for i,section in enumerate(sections):
            start=float(section.get('s'));end=float(sections[i+1].get('s')) if i+1<len(sections) else float(road.get('length'))
            for side in ('left','right'):
                lanes=section.findall('./'+side+'/lane');byid={int(l.get('id')):l for l in lanes}
                for lane in lanes:
                    kind=lane.get('type');lid=int(lane.get('id'));outer=byid.get(lid+(1 if lid>0 else -1))
                    if kind!='parking' and not(kind=='shoulder' and outer is not None and outer.get('type')=='sidewalk'):continue
                    distance=start+3.5
                    while distance<end-3.5:
                        w=wmap.get_waypoint_xodr(int(road.get('id')),lid,distance);distance+=.5
                        if w is None or w.is_junction or w.lane_width<2.:continue
                        perpendicular=kind=='parking' and w.lane_width>=5.
                        length,width=(min(5.5,w.lane_width-.3),2.5) if perpendicular else (6.,min(2.8,w.lane_width-.25))
                        p=w.transform.location;yaw=w.transform.rotation.yaw+(90 if perpendicular else 0)
                        q=dict(x=p.x,y=p.y,z=p.z,yaw=yaw,length=length,width=width,lane=[w.road_id,w.section_id,lid],source='native_parking_lane' if kind=='parking' else 'native_curb_shoulder',boundary_note='Full footprint checked against native pavement; divisions are planning positions within an authored parking lane.' if kind=='parking' else 'Full footprint checked against native pavement on a wide curb shoulder adjoining a sidewalk; divisions are planning estimates.')
                        # CARLA's point lookup can choose a narrow neighbouring
                        # shoulder and return None even inside a wide parking lane.
                        # Build the actual lane ribbon from OpenDRIVE widths instead.
                        left=[];right=[]
                        for sample_s in np.linspace(max(start+.01,w.s-7),min(end-.01,w.s+7),29):
                            sample=wmap.get_waypoint_xodr(w.road_id,lid,float(sample_s))
                            if sample is None or sample.section_id!=w.section_id:continue
                            a=math.radians(sample.transform.rotation.yaw);p0=sample.transform.location
                            nx=-math.sin(a)*sample.lane_width/2;ny=math.cos(a)*sample.lane_width/2
                            left.append([p0.x+nx,p0.y+ny]);right.append([p0.x-nx,p0.y-ny])
                        ribbon=Polygon(left+right[::-1]).buffer(0) if len(left)>1 else Polygon()
                        valid=ribbon.buffer(.015).covers(Polygon(corners(p.x,p.y,length,width,yaw)))
                        if valid:
                            before=len(spaces);add(q)
                            if len(spaces)>before:distance+=2.3 if perpendicular else 6.1
                        else:rejected['outside_lane']+=1
    # An existing parked vehicle is a map-authored position, not evidence of an
    # entire parking row. Keep exactly its pose and never extrapolate neighbours.
    for a in surface.anchors:
        length,width=5.5,2.4
        # Never mark a driving lane as parking, including any of the four corners.
        if any(wmap.get_waypoint(carla.Location(x=x,y=y,z=a['z']),project_to_road=False,lane_type=carla.LaneType.Driving) for x,y in corners(a['x'],a['y'],length,width,a['yaw'])):rejected['driving_lane_anchor']+=1;continue
        add({k:a[k] for k in ('x','y','z','yaw')}|dict(length=length,width=width,source='authored_parked_vehicle_position',native_mesh=a['mesh'],boundary_note='Existing map-authored parked-vehicle pose; footprint checked against native pavement. Estimated vehicle position, not a surveyed painted stall; driving access is checked when assigning a destination.'))
    validation=dict(minimum_base_pavement_fraction=.8,method='Native pavement and marking triangles constrain every footprint, with at least 80 percent base pavement;  OpenDRIVE lane identity, corners and junction checks constrain lane positions; authored parked poses are not extended into invented rows.',opendrive_sha256=hashlib.sha256(xodr.encode()).hexdigest(),scene_sha256=hashlib.sha256((source/'scene.json').read_bytes()).hexdigest(),geometry_sha256=hashlib.sha256(blob).hexdigest(),map=scene['map'],rejected=dict(rejected),pavement_triangles=len(surface.polygons))
    data=dict(map=scene['map'],validated_spaces=spaces,areas=[],validation=validation)
    if not spaces:data['parking_note']='No parking footprint could be verified against this town’s native pavement and authored parking locations. Narrow shoulders are not shown as parking bays.'
    dest=ROOT/'data/parking'/(town['name']+'.json');tmp=dest.with_suffix('.json.next');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(dest)
    (source/'parking-report.json').write_text(json.dumps(dict(town=town['name'],spaces=len(spaces),sources=dict(Counter(s['source'] for s in spaces)),validation=validation),indent=2))
    print(town['name'],len(spaces),dict(rejected),flush=True)
    return data

def main():
    ap=argparse.ArgumentParser();ap.add_argument('towns',nargs='+');args=ap.parse_args()
    for town in available_towns():
        if town['name'] not in args.towns:continue
        if town['name']=='Town10HD_Opt':raise ValueError('Preserve the existing Town10 hand survey')
        generate(town,ROOT/'data/scene-sources'/town['name'])
if __name__=='__main__':main()
