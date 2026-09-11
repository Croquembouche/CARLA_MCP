import unreal,json,os,hashlib,traceback
ROOT='/mnt/simulations/control-center';source=json.load(open(ROOT+'/data/scene-source/scene.json'));dest=ROOT+'/data/road-source';os.makedirs(dest,exist_ok=True)
options=unreal.GLTFExportOptions();options.set_editor_property('bake_material_inputs',unreal.GLTFMaterialBakeMode.DISABLED);options.set_editor_property('export_source_model',True);options.set_editor_property('default_level_of_detail',0)
report={}
for key in source['meshes']:
 if 'SM_Town10HD_' not in key:continue
 try:
  mesh=unreal.load_asset(key);file=mesh.get_name()+'.glb';messages=unreal.GLTFExporter.export_to_gltf(mesh,dest+'/'+file,options,set());report[key]={'file':file,'warnings':[str(w) for w in messages.warnings],'errors':[str(w) for w in messages.errors]}
 except:report[key]={'error':traceback.format_exc()}
open(dest+'/manifest.json','w').write(json.dumps(report,indent=2))
