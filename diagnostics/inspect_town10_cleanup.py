import unreal,json,traceback
from pathlib import Path
root=Path('/mnt/simulations/control-center/data/town10-cleanup')
out={}
try:
 manifest=json.loads((root/'cleanup-manifest.json').read_text()); keys={x['source'] for x in manifest['removed']}
 assert unreal.EditorLevelLibrary.load_level(manifest['map'])
 actors=unreal.EditorLevelLibrary.get_all_level_actors()
 out['matches']=[{'name':a.get_name(),'label':a.get_actor_label(),'path':a.get_path_name(),'level':a.get_level().get_path_name(),'location':str(a.get_actor_location()),'components':[{'name':c.get_name(),'mesh':c.static_mesh.get_path_name() if c.static_mesh else None} for c in a.get_components_by_class(unreal.StaticMeshComponent)]} for a in actors if a.get_name() in keys]
 out['count']=len(actors)
except:out['error']=traceback.format_exc()
(root/'editor-inventory.json').write_text(json.dumps(out,indent=2))
