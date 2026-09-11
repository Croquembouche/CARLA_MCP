import unreal,json
root='/mnt/simulations/control-center/data/parking/'
materials=['/Game/Carla/Static/FX/Decals/Road/AccessRoad/DI_access','/Game/Carla/Static/Building/SpecialBuildings/Parking/IndividualComponents/MI_Parking']
out={}
for path in materials:
 m=unreal.load_asset(path);params={}
 for n in unreal.MaterialEditingLibrary.get_texture_parameter_names(m):
  t=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(m,n)
  if t:
   filename=t.get_name()+'.tga';params[str(n)]=filename
   task=unreal.AssetExportTask();task.object=t;task.filename=root+filename;task.automated=True;task.prompt=False;task.replace_identical=True;unreal.Exporter.run_asset_export_task(task)
 out[path]=params
open(root+'textures.json','w').write(json.dumps(out,indent=2))
