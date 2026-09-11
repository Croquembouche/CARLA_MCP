import unreal,json,traceback
out=[]
try:
 unreal.EditorLevelLibrary.load_level('/Game/Carla/Maps/Town10HD_Opt')
 for a in unreal.EditorLevelLibrary.get_all_level_actors():
  if 'TrafficLightNew' not in a.get_class().get_name():continue
  parts=[]
  for c in a.get_components_by_class(unreal.StaticMeshComponent):
   m=c.get_editor_property('static_mesh')
   if m:parts.append({'name':c.get_name(),'mesh':m.get_path_name(),'transform':str(c.get_world_transform()),'bounds':str(c.get_local_bounds()),'stencil':c.get_editor_property('custom_depth_stencil_value')})
  out.append({'actor':a.get_name(),'pose':str(a.get_actor_transform()),'parts':parts})
except:out.append({'error':traceback.format_exc()})
open('/mnt/simulations/control-center/data/signal-head-inspection.json','w').write(json.dumps(out,indent=2))
