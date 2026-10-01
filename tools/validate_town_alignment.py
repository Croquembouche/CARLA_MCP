"""Compare exported pavement with independent OpenDRIVE driving waypoints."""
import argparse,json,sys,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bootstrap,carla
from towns import available_towns,MAPS
from tools.build_town_parking import Pavement
from parking import corners

def check(town):
    source=ROOT/'data/scene-sources'/town['name'];scene=json.loads((source/'scene.json').read_text());surface=Pavement(scene,(source/'geometry.bin').read_bytes(),include_markings=True)
    level=MAPS.parent.parent/(town['id'].removeprefix('/Game/')+'.umap');xml=(level.parent/'OpenDrive'/(town['name']+'.xodr')).read_text();wmap=carla.Map(town['name'],xml)
    all_points=wmap.generate_waypoints(20);points=all_points[::max(1,len(all_points)//200)];passed=0;missed=[]
    for w in points:
        p=w.transform.location;bay={'z':p.z,'polygon':corners(p.x,p.y,.2,.2,w.transform.rotation.yaw)}
        if surface.fits(bay):passed+=1
        else:missed.append({'x':p.x,'y':p.y,'z':p.z,'road':w.road_id,'lane':w.lane_id})
    ground_supported=[]
    if missed:
        ground=Pavement(scene,(source/'geometry.bin').read_bytes(),include_markings=True,include_ground=True)
        for point in missed:
            bay={'z':point['z'],'polygon':corners(point['x'],point['y'],.2,.2,0)}
            if ground.fits(bay):ground_supported.append(point)
    result={'ground_supported':ground_supported,'town':town['name'],'sampled':len(points),'on_exported_pavement':passed,'coverage':round(passed/max(1,len(points)),4),'missed':missed}
    (source/'alignment-report.json').write_text(json.dumps(result,indent=2));print(town['name'],passed,'/',len(points),'pavement;',len(ground_supported),'additional native ground',flush=True)
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('towns',nargs='+');a=ap.parse_args()
    for t in available_towns():
        if t['name'] in a.towns:check(t)
