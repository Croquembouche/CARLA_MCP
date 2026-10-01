"""Build isolated per-town browser packages; preserve existing Town10 surveys.

Run under the control-center environment. Each town gets its own editor process,
source buffers, texture/build reports, and atomic browser manifest.
"""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from towns import available_towns

def main():
    ap=argparse.ArgumentParser();ap.add_argument('towns',nargs='*');ap.add_argument('--resume',action='store_true');args=ap.parse_args()
    selected=[t for t in available_towns() if t['name'] in args.towns] if args.towns else [t for t in available_towns() if t['name']!='Town10HD_Opt']
    if args.towns and len(selected)!=len(set(args.towns)):raise ValueError('Unknown town')
    reports=[]
    for town in selected:
        src=ROOT/'data/scene-sources'/town['name'];src.mkdir(parents=True,exist_ok=True)
        env={**os.environ,'CARLA_SCENE_MAP':town['id'],'CARLA_SCENE_SOURCE':str(src)};env.pop('CARLA_SCENE_ALREADY_LOADED',None)
        start=time.time();row={'town':town['name'],'started':start};print(json.dumps(row),flush=True)
        try:
            if not(args.resume and (src/'textures.json').exists() and (src/'splines.json').exists() and (src/'landscape-report.json').exists()):
                with (src/'stdout.log').open('w') as log:
                    subprocess.run(['/mnt/simulations/bin/carla-editor','-run=pythonscript','-script='+str(ROOT/'diagnostics/export_town_scene.py'),'-nullrhi','-ini:Engine:[/Script/Engine.RendererSettings]:r.GenerateMeshDistanceFields=False','-unattended','-nosound','-notraceserver','-ddc=NoZenLocalFallback','-LocalDataCachePath='+str(Path.home()/'.cache/carla-ddc'),'-abslog='+str(src/'export.log')],stdout=log,stderr=subprocess.STDOUT,env=env,check=True)
            subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/build_scene_textures.py')],env=env,check=True)
            subprocess.run(['node',str(ROOT/'scripts/build_scene.mjs')],env=env,check=True)
            subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'tools/build_town_parking.py'),town['name']],env=env,check=True)
            subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'tools/validate_town_scenes.py'),town['name']],env=env,check=True)
            row.update(status='built',summary=json.loads((src/'build-report.json').read_text()))
        except Exception as e:row.update(status='failed',error=str(e))
        row['seconds']=round(time.time()-start,2);reports.append(row)
        (src/'pipeline-report.json').write_text(json.dumps(row,indent=2));print(json.dumps({k:v for k,v in row.items() if k!='summary'}),flush=True)
    (ROOT/'data/town-scene-builds.json').write_text(json.dumps(reports,indent=2))
    if any(r['status']=='failed' for r in reports):raise SystemExit(1)

if __name__=='__main__':main()
