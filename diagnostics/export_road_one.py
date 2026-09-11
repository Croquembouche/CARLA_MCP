import unreal,json,os,struct,traceback
ROOT='/mnt/simulations/control-center';source=unreal.load_asset('/Game/Carla/Static/Road/RoadsTown10HD/SM_Town10HD_Road_1.SM_Town10HD_Road_1');dest=ROOT+'/data/road-source/SM_Town10HD_Road_1.glb'
options=unreal.GLTFExportOptions();options.set_editor_property('bake_material_inputs',unreal.GLTFMaterialBakeMode.DISABLED);options.set_editor_property('export_source_model',True);options.set_editor_property('default_level_of_detail',0)
report={'slots':len(source.get_editor_property('static_materials')),'attempts':[]}
original_slots=list(source.get_editor_property('static_materials'))
try:
 for count in range(1,5):
  mesh=source;slots=original_slots;mesh.set_editor_property('static_materials',(slots+[slots[0]]*count)[:count]);messages=unreal.GLTFExporter.export_to_gltf(mesh,dest,options,set());b=open(dest,'rb').read();n=struct.unpack_from('<I',b,12)[0];g=json.loads(b[20:20+n]);report['attempts'].append({'count':count,'meshes':len(g.get('meshes',[]))})
  if g.get('meshes'):break
except:report['error']=traceback.format_exc()
finally:source.set_editor_property('static_materials',original_slots)
open(ROOT+'/data/road-one-export.json','w').write(json.dumps(report,indent=2))
