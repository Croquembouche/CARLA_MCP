"""Run using Unreal's PythonScript commandlet on a compatible CARLA project.
Validates exact identities, positions and mesh assets before saving Town10.
The original map is backed up beside this script on first application.
"""
import unreal,json,hashlib,shutil,traceback,math
from pathlib import Path
root=Path(__file__).resolve().parent
manifest=json.loads((root/'cleanup-manifest.json').read_text())
report={'map':manifest['map'],'removed':[]}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(actors):
 return {a.get_name():str(a.get_actor_transform()) for a in actors}
try:
 assert unreal.EditorLevelLibrary.load_level(manifest['map']), 'Map failed to load'
 actors=unreal.EditorLevelLibrary.get_all_level_actors();by_name={a.get_name():a for a in actors}
 targets=[]
 for row in manifest['removed']:
  a=by_name.get(row['source'])
  if a is None:continue
  assert a.get_level().get_path_name()==manifest['map']+'.Town10HD_Opt:PersistentLevel', 'Unexpected owning level'
  p=a.get_actor_location();expected=row['pose']
  assert math.hypot(p.x/100-expected['x'],p.y/100-expected['y'])<.5, 'Actor moved: '+row['source']
  meshes=sorted(c.static_mesh.get_path_name() for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.static_mesh)
  assert meshes==row['meshes'], 'Mesh mismatch: '+row['source']
  targets.append(a)
 assert len(targets) in (0,len(manifest['removed'])), 'Partially modified map: inspect before applying'
 asset=Path(unreal.Paths.project_content_dir()).resolve()/(manifest['map'].removeprefix('/Game/')+'.umap')
 report['before_sha256']=digest(asset);report['actors_before']=len(actors)
 if targets:
  backup=root/'backup'/asset.relative_to(Path(unreal.Paths.project_content_dir()).resolve());backup.parent.mkdir(parents=True,exist_ok=True)
  if not backup.exists():shutil.copy2(asset,backup)
  report['backup']=str(backup)
  # Check all targets before changing anything; save only this persistent level.
  for a in targets:
   name=a.get_name();assert unreal.EditorLevelLibrary.destroy_actor(a),'Failed to remove '+name
   report['removed'].append(name)
  assert unreal.EditorLevelLibrary.save_current_level(), 'Map save failed'
 assert unreal.EditorLevelLibrary.load_level(manifest['map']), 'Saved map reload failed'
 remaining=unreal.EditorLevelLibrary.get_all_level_actors();names={a.get_name() for a in remaining}
 assert not names.intersection(row['source'] for row in manifest['removed']), 'Deleted actors returned after reload'
 assert names==set(by_name)-set(report['removed']), 'Unexpected actors changed'
 report.update(actors_after=len(remaining),after_sha256=digest(asset),verified=True)
except:
 report.update(verified=False,error=traceback.format_exc())
(root/'apply-report.json').write_text(json.dumps(report,indent=2))
if not report['verified']:raise RuntimeError(report['error'])
print('TOWN10_CLEANUP_VERIFIED '+json.dumps(report))
