"""Set the legacy animation normalization denominator on our copied presets."""
import unreal as u,json
from pathlib import Path
report={}
for name in ['Harley','Vespa','Yamaha','KawasakiNinja']:
    path='/Game/Carla/Blueprints/Vehicles/SceneControllable/BP_'+name+'Background'
    bp=u.load_asset(path);cdo=u.get_default_object(bp.generated_class())
    before=cdo.get_editor_property('MaxEngineRotationSpeed')
    movement=cdo.get_component_by_class(u.ChaosWheeledVehicleMovementComponent)
    rpm=movement.get_editor_property('engine_setup').get_editor_property('max_rpm')
    if before<=0:
        cdo.set_editor_property('MaxEngineRotationSpeed',rpm)
        assert u.EditorAssetLibrary.save_loaded_asset(bp)
    report[name]={'animation_max_rpm_before':before,'animation_max_rpm_after':cdo.get_editor_property('MaxEngineRotationSpeed'),'engine_max_rpm':rpm}
Path('/mnt/simulations/control-center/data/scene-vehicles/animation-rpm.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
