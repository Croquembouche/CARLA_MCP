import unreal,json,traceback
out={}
for kind,path in [('vehicles','/Game/Carla/Blueprints/Vehicles/BP_VehicleFactory'),('walkers','/Game/Carla/Blueprints/Walkers/BP_WalkerFactory')]:
 try:
  c=unreal.EditorAssetLibrary.load_blueprint_class(path);o=unreal.get_default_object(c);out[kind]={'class':str(c),'attrs':[n for n in dir(o) if not n.startswith('_')]}
  for name in ['vehicles','pedestrians','definitions','walkers']:
   try:out[kind][name]=str(o.get_editor_property(name))
   except:pass
 except:out[kind]=traceback.format_exc()
out['gltf']=hasattr(unreal,'GLTFExporter')
open('/mnt/simulations/control-center/data/actor-assets-inspection.json','w').write(json.dumps(out,indent=2))
