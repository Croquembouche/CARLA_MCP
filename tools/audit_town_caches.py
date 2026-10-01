"""Validate installed Traffic Manager caches against each town's OpenDRIVE.

Run with --repair to rebuild mismatches; originals are retained under data.
Uses the current CARLA CachedSimpleWaypoint binary layout (not a portable format).
"""
import argparse,json,struct,sys,hashlib,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import carla
from towns import MAPS,available_towns
ROOT=Path(__file__).resolve().parents[1]

def invalid_waypoints(data,wmap):
    pos=0
    def read(fmt):
        nonlocal pos
        value=struct.unpack_from('<'+fmt,data,pos);pos+=struct.calcsize('<'+fmt);return value
    total,=read('I');invalid=0
    for _ in range(total):
        wid,road,section,lane,s=read('QIIif')
        for _ in range(2):
            n,=read('H');read('Q'*n)
        read('QQi?B')
        wp=wmap.get_waypoint_xodr(road,lane,s)
        if wp is None:invalid+=1
    if pos!=len(data):raise ValueError('Unrecognized TM cache format')
    return total,invalid

def main():
    p=argparse.ArgumentParser();p.add_argument('--repair',action='store_true');args=p.parse_args();results=[]
    for town in available_towns():
        level=MAPS.parent.parent/(town['id'].removeprefix('/Game/')+'.umap')
        xodr=level.parent/'OpenDrive'/(town['name']+'.xodr');cache=level.parent/'TM'/(town['name']+'.bin')
        if not cache.exists():continue
        wmap=carla.Map(town['name'],xodr.read_text());data=cache.read_bytes()
        count,invalid=invalid_waypoints(data,wmap)
        row={'town':town['name'],'waypoints':count,'invalid':invalid,'repaired':False}
        if invalid and args.repair:
            backup=ROOT/'data/tm-cache-backups'/town['name'];backup.mkdir(parents=True,exist_ok=True)
            shutil.copy2(cache,backup/(hashlib.sha256(data).hexdigest()+'.bin'))
            tmp=cache.with_suffix('.bin.next');wmap.cook_in_memory_map(str(tmp))
            new_count,new_invalid=invalid_waypoints(tmp.read_bytes(),wmap)
            if new_invalid:raise RuntimeError('Rebuilt cache still contains invalid waypoints')
            tmp.replace(cache)
            # CARLA downloads caches once by version. Refresh this exact map's
            # already-downloaded caches too, retaining copies for diagnosis.
            relative=cache.relative_to(MAPS.parent.parent)
            for folder in (Path.home()/'carlaCache').glob('*'):
                downloaded=folder/relative
                if downloaded.is_file():
                    old=downloaded.read_bytes();(backup/(hashlib.sha256(old).hexdigest()+'.bin')).write_bytes(old)
                    shutil.copy2(cache,downloaded)
            row.update(repaired=True,rebuilt_waypoints=new_count)
        results.append(row);print(json.dumps(row),flush=True)
    (ROOT/'data/town-cache-audit.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
