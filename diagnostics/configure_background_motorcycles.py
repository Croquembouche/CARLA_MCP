"""Create separate Chaos-configured background motorcycle blueprints."""
import unreal as u,json
from pathlib import Path
root=Path('/mnt/simulations/control-center');folder='/Game/Carla/Blueprints/Vehicles/SceneControllable'
u.EditorAssetLibrary.make_directory(folder)
donor=u.get_default_object(u.load_class(None,'/Game/Carla/Blueprints/Vehicles/LincolnMKZ/BP_LincolnMKZ.BP_LincolnMKZ_C')).get_component_by_class(u.ChaosWheeledVehicleMovementComponent)
report={}
for name,mass,torque in [('Harley',250,100),('Vespa',150,15),('Yamaha',200,80),('KawasakiNinja',200,80)]:
    original='/Game/Carla/Blueprints/Vehicles/2Wheeled/'+name+'/BP_'+name
    path=folder+'/BP_'+name+'Background'
    bp=u.load_asset(path) if u.EditorAssetLibrary.does_asset_exist(path) else u.EditorAssetLibrary.duplicate_asset(original,path)
    cdo=u.get_default_object(bp.generated_class());movement=cdo.get_component_by_class(u.ChaosWheeledVehicleMovementComponent)
    wheels=[]
    for suffix,bones,steering in [('FW',['Wheel_F_L','Wheel_F_R'],True),('RW',['Wheel_R_L','Wheel_R_R'],False)]:
        wheel_path=folder+'/BP_'+name+'_'+suffix
        wheel=u.load_asset(wheel_path) if u.EditorAssetLibrary.does_asset_exist(wheel_path) else u.EditorAssetLibrary.duplicate_asset(original+'_'+suffix,wheel_path)
        wc=u.get_default_object(wheel.generated_class())
        wc.set_editor_property('affected_by_steering',steering);wc.set_editor_property('affected_by_engine',not steering)
        wc.set_editor_property('max_steer_angle',45 if steering else 0)
        u.EditorAssetLibrary.save_loaded_asset(wheel)
        for bone in bones:
            setup=u.ChaosWheelSetup();setup.set_editor_property('wheel_class',wheel.generated_class());setup.set_editor_property('bone_name',bone);wheels.append(setup)
    movement.set_editor_property('wheel_setups',wheels)
    for key in ('engine_setup','transmission_setup','differential_setup','steering_setup'):
        value=donor.get_editor_property(key)
        if key=='engine_setup':value.set_editor_property('max_torque',torque)
        movement.set_editor_property(key,value)
    movement.set_editor_property('mass',mass)
    cdo.set_editor_property('MaxEngineRotationSpeed',movement.get_editor_property('engine_setup').get_editor_property('max_rpm'))
    u.EditorAssetLibrary.save_loaded_asset(bp)
    report[name]={'blueprint':path+'.'+path.rsplit('/',1)[-1]+'_C','support_wheels':len(wheels),'mass_kg':mass,'max_torque_nm':torque,'note':'Approximate background driving preset, four virtual support wheels; not calibrated motorcycle dynamics'}
(root/'data/scene-vehicles/motorcycle-presets.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
