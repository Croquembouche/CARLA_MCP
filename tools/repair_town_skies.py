"""Run with Unreal's Python commandlet; add UE5 CARLA skies where absent.

Backs up every changed map, leaves existing skies intact, and removes obsolete
standalone daylight components only when replacing a missing sky setup.
"""
import json,shutil,os
from pathlib import Path
import unreal as u
content=Path('/mnt/simulations/carla/Unreal/CarlaUnreal/Content')
out=Path('/mnt/simulations/control-center/data/town-asset-repair');out.mkdir(parents=True,exist_ok=True)
skyclass=u.EditorAssetLibrary.load_blueprint_class('/Game/Carla/Blueprints/LevelDesign/BP_Carla_Sky');assert skyclass
paths=[f'/Game/Carla/Maps/Town{i:02d}_Opt' for i in range(1,8)]
paths += [f'/Game/Carla/Maps/Town{i}/Town{i}' for i in [11,12,13,15]]
report=[]
def backup(obj):
 package=obj.get_outermost().get_path_name();src=content/(package.removeprefix('/Game/')+'.umap');dst=out/'maps'/src.relative_to(content)
 if not dst.exists():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 return str(src)
for path in paths:
 if path.split('/')[-1] in os.environ.get('TOWN_SKY_SKIP','').split(','):continue
 assert u.EditorLevelLibrary.load_level(path)
 world=u.EditorLevelLibrary.get_editor_world();actors=u.EditorLevelLibrary.get_all_level_actors()
 skies=[a for a in actors if isinstance(a,u.SkyBase)]
 row={'town':path,'existing_skies':[a.get_path_name() for a in skies],'changed':False}
 if not skies:
  row['backups']=[backup(world)];row['removed_legacy_lights']=[]
  sky=u.OpenDriveToMap.spawn_actor_with_check_no_collisions(skyclass,u.Transform());assert sky
  sky.set_actor_label('CARLA Weather Sky');world.modify()
  for a in actors:
   if isinstance(a,(u.DirectionalLight,u.SkyLight,u.ExponentialHeightFog,u.SkyAtmosphere)):
    row['backups'].append(backup(a));row['removed_legacy_lights'].append(a.get_path_name());u.EditorLevelLibrary.destroy_actor(a)
  assert u.EditorLevelLibrary.save_all_dirty_levels();row['changed']=True;row['sky']=sky.get_path_name()
 report.append(row);(out/'sky-repair.json').write_text(json.dumps(report,indent=2));print('TOWN_SKY '+json.dumps(row))
