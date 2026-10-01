"""Prepare a read-only browser review without switching the live simulation."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bootstrap,carla
from towns import available_towns,MAPS
from lane_map import build_lanes
out=ROOT/'static/town-review';out.mkdir(exist_ok=True);index=[]
for town in available_towns():
    manifest=ROOT/'static/scenes'/town['name']/'manifest.json'
    if not manifest.exists():continue
    level=MAPS.parent.parent/(town['id'].removeprefix('/Game/')+'.umap');xml=(level.parent/'OpenDrive'/(town['name']+'.xodr')).read_text();wmap=carla.Map(town['name'],xml)
    # Review needs lane bounds and geometry, not traffic-routing authoring.
    groups={}
    for w in wmap.generate_waypoints(4):
        p=w.transform.location;groups.setdefault((w.road_id,w.section_id,w.lane_id),[]).append((w.s,[p.x,p.y,p.z,w.lane_width]))
    lanes=[{'points':[p for _,p in sorted(row)]} for row in groups.values()];points=[p for l in lanes for p in l['points']]
    data={'name':town['id'].removeprefix('/Game/'),'lanes':lanes,'bounds':[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]}
    path=ROOT/'data/parking'/(town['name']+'.json')
    if path.exists():
        parking=json.loads(path.read_text());data['parking_spaces']=parking.get('validated_spaces',[])
    (out/(town['name']+'.json')).write_text(json.dumps(data,separators=(',',':')));index.append(town['name'])
(out/'towns.json').write_text(json.dumps(index))
