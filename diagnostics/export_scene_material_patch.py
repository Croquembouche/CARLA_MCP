import unreal,json,os,hashlib,traceback
ROOT='/mnt/simulations/control-center';src=json.load(open(ROOT+'/data/scene-source/scene.json'));dest=ROOT+'/data/scene-material-patch';os.makedirs(dest,exist_ok=True);out={'materials':{},'textures':{},'errors':{}}
for key,old in src['materials'].items():
 if '/Engine/Transient' in key:continue
 try:
  mat=unreal.load_asset(key)
  if not mat:continue
  m=dict(old);m['scalars']={}
  for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(mat):
   if isinstance(mat,unreal.MaterialInstanceConstant):m['scalars'][str(n)]=unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(mat,n)
  if not m.get('web_texture'):
   names=['BaseColor','Base Color','Diffuse','Albedo','Color','BaseColorTexture','Sticker Diffuse','FakeInterior']
   name=next((n for n in names if n in m['textures']),None)
   path=m['textures'].get(name)
   if not path and isinstance(mat,unreal.Material):
    textures=unreal.MaterialEditingLibrary.get_used_textures(mat)
    t=next((t for t in textures if any(x in t.get_name().lower() for x in ['_d','diffuse','albedo','basecolor'])),None)
    if t:path=t.get_path_name()
   if path:
    m['browser_texture']=path
    if path not in out['textures']:
     file=hashlib.sha256(path.encode()).hexdigest()[:20]+'.png';task=unreal.AssetExportTask();task.object=unreal.load_asset(path);task.filename=dest+'/'+file;task.automated=True;task.prompt=False;task.replace_identical=True;ok=unreal.Exporter.run_asset_export_task(task)
     if not ok:file=file.replace('.png','.exr');task.filename=dest+'/'+file;ok=unreal.Exporter.run_asset_export_task(task)
     out['textures'][path]={'file':file,'success':ok}
  out['materials'][key]=m
 except:out['errors'][key]=traceback.format_exc()
 open(dest+'/manifest.json','w').write(json.dumps(out))
# Retry the source mesh separately and reject empty exports.
key='/Game/Carla/Static/Road/RoadsTown10HD/SM_Town10HD_Road_1.SM_Town10HD_Road_1'
mesh=unreal.load_asset(key);print('ROAD1_ASSET',mesh,type(mesh),flush=True)
options=unreal.GLTFExportOptions();options.set_editor_property('bake_material_inputs',unreal.GLTFMaterialBakeMode.DISABLED);options.set_editor_property('export_source_model',True);options.set_editor_property('default_level_of_detail',0)
print('ROAD1_EXPORT',unreal.GLTFExporter.export_to_gltf(mesh,ROOT+'/data/road-source/SM_Town10HD_Road_1.glb',options,set()),flush=True)
