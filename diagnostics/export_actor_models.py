"""Export read-only CARLA blueprint previews in an isolated editor, never save assets."""
import unreal,json,os,traceback,time,hashlib
ROOT='/mnt/simulations/control-center'
CONFIG='/mnt/simulations/carla/Unreal/CarlaUnreal/Content/Carla/Config/'
out=ROOT+'/static/actors';os.makedirs(out,exist_ok=True)
items=[]
for p in json.load(open(CONFIG+'VehicleParameters.json'))['Vehicles']:
 items.append(('vehicle.'+p['Make'].lower()+'.'+p['Model'].lower(),p['Class']))
for p in json.load(open(CONFIG+'WalkerParameters.json'))['Walkers']:
 items.append(('walker.pedestrian.'+p['Id'],p['Class']))
active={a['type'] for a in json.load(open(ROOT+'/data/actor-model-before.json'))['actors']}
items.sort(key=lambda i:i[0] not in active)
options=unreal.GLTFExportOptions()
for k,v in dict(bake_material_inputs=unreal.GLTFMaterialBakeMode.DISABLED,default_level_of_detail=2,export_source_model=False,export_vertex_skin_weights=True,export_animation_sequences=False,export_lights=False,export_cameras=False,export_uniform_scale=.01).items():options.set_editor_property(k,v)
manifest_path=out+'/manifest.json'
report=json.load(open(manifest_path)) if os.path.exists(manifest_path) else {'models':{},'errors':{}}
items=[item for item in items if item[0] not in report['models']]
exported={p['mesh']:p['file'] for m in report['models'].values() for p in m['parts']}
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for model,path in items:
 actor=None
 try:
  cls=unreal.load_class(None,path)
  actor=unreal.EditorLevelLibrary.spawn_actor_from_class(cls,unreal.Vector(0,0,0),unreal.Rotator(0,0,0),transient=True)
  if not actor:raise RuntimeError('Cannot instantiate '+path)
  parts=[]
  for comp in actor.get_components_by_class(unreal.MeshComponent):
   if not comp.is_visible() or comp.get_editor_property('hidden_in_game'):continue
   if isinstance(comp,unreal.SkeletalMeshComponent):mesh=comp.get_skeletal_mesh_asset()
   elif isinstance(comp,unreal.StaticMeshComponent):mesh=comp.get_editor_property('static_mesh')
   else:continue
   if not mesh:continue
   key=mesh.get_path_name();filename=hashlib.sha256(key.encode()).hexdigest()[:20]+'.glb'
   if key not in exported:
    messages=unreal.GLTFExporter.export_to_gltf(mesh,out+'/'+filename,options,set())
    if messages is None:raise RuntimeError('GLTF mesh export failed '+key)
    exported[key]=filename
   t=comp.get_world_transform();p=t.translation;q=t.rotation;scale=t.scale3d
   parts.append({'file':filename,'mesh':key,'position':[p.x/100,p.z/100,p.y/100],'quaternion':[-q.x,-q.z,-q.y,q.w],'scale':[scale.x,scale.z,scale.y]})
  if not parts:raise RuntimeError('No visible actor meshes')
  report['models'][model]={'blueprint':path,'parts':parts};report['errors'].pop(model,None)

 except:report['errors'][model]=traceback.format_exc()
 finally:
  if actor:unreal.EditorLevelLibrary.destroy_actor(actor)
 with open(out+'/manifest.json.tmp','w') as f:json.dump(report,f)
 os.replace(out+'/manifest.json.tmp',out+'/manifest.json')
 print('ACTOR_EXPORT',model,len(report['models']),len(report['errors']),flush=True)
 unreal.SystemLibrary.collect_garbage()
open(ROOT+'/data/actor-export-report.json','w').write(json.dumps(report,indent=2))
