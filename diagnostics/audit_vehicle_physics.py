import unreal as u,json
from pathlib import Path
root=Path('/mnt/simulations/control-center');items=json.loads(Path('/mnt/simulations/carla/Unreal/CarlaUnreal/Content/Carla/Config/VehicleParameters.json').read_text())['Vehicles'];report={}
items += [{'Make':'audit','Model':name,'Class':'/Game/Carla/Blueprints/Vehicles/'+path+'.'+path.rsplit('/',1)[-1]+'_C'} for name,path in [('harley','2Wheeled/Harley/BP_Harley'),('vespa','2Wheeled/Vespa/BP_Vespa'),('tesla','Tesla/BP_Tesla')]]
for name in ['Harley','Vespa','Yamaha','KawasakiNinja']:
    path='/Game/Carla/Blueprints/Vehicles/SceneControllable/BP_'+name+'Background'
    if u.EditorAssetLibrary.does_asset_exist(path):items.append({'Make':'verified','Model':name,'Class':path+'.'+path.rsplit('/',1)[-1]+'_C'})
for item in items:
    model='vehicle.'+item['Make'].lower()+'.'+item['Model'].lower()
    actor=None
    try:
        cls=u.load_class(None,item['Class']);actor=u.EditorLevelLibrary.spawn_actor_from_class(cls,u.Vector(),u.Rotator(),transient=True)
        movement=actor.get_component_by_class(u.ChaosWheeledVehicleMovementComponent)
        wheels=movement.get_editor_property('wheel_setups')
        report[model]={'wheels':[{'bone':str(w.get_editor_property('bone_name')),'class':str(w.get_editor_property('wheel_class'))} for w in wheels],'max_torque':movement.get_editor_property('engine_setup').get_editor_property('max_torque')}
        report[model]['components']=[{'name':m.get_name(),'wheels':str(m.get_editor_property('wheel_setups'))} for m in actor.get_components_by_class(u.ChaosWheeledVehicleMovementComponent)]
        mesh=actor.get_component_by_class(u.SkeletalMeshComponent);report[model]['bones']=[str(mesh.get_bone_name(i)) for i in range(mesh.get_num_bones())]
    except Exception as e:report[model]={'error':str(e)}
    finally:
        if actor:u.EditorLevelLibrary.destroy_actor(actor)
(root/'data/scene-vehicles/physics-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
