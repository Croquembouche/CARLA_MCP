import unreal,json,traceback,collections
out={}
try:
 unreal.EditorLevelLibrary.load_level('/Game/Carla/Maps/Town10HD_Opt')
 actors=unreal.EditorLevelLibrary.get_all_level_actors()
 out['actors']=len(actors);out['classes']=dict(collections.Counter(a.get_class().get_name() for a in actors))
 out['libraries']=[x for x in dir(unreal) if any(s in x for s in ['ProceduralMesh','GLTF','LevelUtils'])]
 out['levels']=[x for x in dir(unreal.EditorLevelUtils) if 'level' in x]
 meshes={};samples=[]
 for a in actors:
  for c in a.get_components_by_class(unreal.StaticMeshComponent):
   m=c.get_editor_property('static_mesh')
   if not m:continue
   path=m.get_path_name()
   if path not in meshes:meshes[path]={'lods':[m.get_num_triangles(i) for i in range(m.get_num_lods())], 'instances':0}
   meshes[path]['instances']+= c.get_instance_count() if isinstance(c,unreal.InstancedStaticMeshComponent) else 1
   if len(samples)<4:
    samples.append({'actor':a.get_name(),'component':c.get_name(),'mesh':path,'transform':str(c.get_world_transform()),'methods':[x for x in dir(c) if any(s in x for s in ['transform','visible','hidden'])]})
 out['meshes']=meshes;out['samples']=samples
 m=unreal.load_asset(next(iter(meshes)))
 out['section']=str(unreal.ProceduralMeshLibrary.get_section_from_static_mesh(m,0,0))[:2000]
except:out['error']=traceback.format_exc()
open('/mnt/simulations/control-center/data/scene-inspection.json','w').write(json.dumps(out,indent=2))
