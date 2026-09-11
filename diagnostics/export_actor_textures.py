import unreal,json,os,hashlib,traceback
ROOT='/mnt/simulations/control-center';manifest=json.load(open(ROOT+'/static/actors/manifest.json'))
dest=ROOT+'/data/actor-textures';os.makedirs(dest,exist_ok=True)
out=json.load(open(dest+'/manifest.json')) if os.path.exists(dest+'/manifest.json') else {'materials':{},'textures':{},'errors':{}}
selected=set(json.loads(os.environ.get('ACTOR_MODEL_IDS','[]')))
if selected:manifest['models']={k:v for k,v in manifest['models'].items() if k in selected}
for key in sorted({p['mesh'] for m in manifest['models'].values() for p in m['parts']}):
 try:
  mesh=unreal.load_asset(key)
  slots=mesh.get_editor_property('materials') if isinstance(mesh,unreal.SkeletalMesh) else mesh.get_editor_property('static_materials')
  for slot in slots:
   mat=slot.get_editor_property('material_interface')
   if not mat or mat.get_name() in out['materials']:continue
   info={'textures':{},'vectors':{},'blend':str(mat.get_blend_mode())}
   if isinstance(mat,unreal.MaterialInstanceConstant):
    for n in unreal.MaterialEditingLibrary.get_texture_parameter_names(mat):
     t=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mat,n)
     if t:info['textures'][str(n)]=t.get_path_name()
    for n in unreal.MaterialEditingLibrary.get_vector_parameter_names(mat):
     c=unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(mat,n)
     info['vectors'][str(n)]=[c.r,c.g,c.b,c.a]
   out['materials'][mat.get_name()]=info
   names=['BaseColor','Base Color','Diffuse','Albedo','Color','BaseColorTexture','DiffuseTexture','Base_Color']
   name=next((n for n in names if n in info['textures']),None)
   if not name:name=next((n for n in info['textures'] if any(s in n.lower() for s in ['basecolor','base color','diffuse','albedo'])),None)
   if not name:continue
   info['color_texture']=info['textures'][name]
   alpha=next((v for k,v in info['textures'].items() if 'opacity' in k.lower()),None)
   if alpha and 'MASKED' in info['blend']:info['alpha_texture']=alpha
   for path in [info['color_texture']]+([alpha] if info.get('alpha_texture') else []):
    if path in out['textures']:continue
    name=hashlib.sha256(path.encode()).hexdigest()[:20]+'.png'
    task=unreal.AssetExportTask();task.object=unreal.load_asset(path);task.filename=dest+'/'+name;task.automated=True;task.prompt=False;task.replace_identical=True
    ok=unreal.Exporter.run_asset_export_task(task)
    if not ok:
     name=name.replace('.png','.exr');task.filename=dest+'/'+name;ok=unreal.Exporter.run_asset_export_task(task)
    out['textures'][path]={'file':name,'success':ok}
 except:out['errors'][key]=traceback.format_exc()
 open(dest+'/manifest.json','w').write(json.dumps(out))
 print('ACTOR_TEXTURES',len(out['materials']),len(out['textures']),flush=True)
