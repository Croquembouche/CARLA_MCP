"""Run inside the Unreal Python commandlet; repair the legacy ORM sampler."""
from pathlib import Path
import json,shutil
import unreal as u
out=Path('/mnt/simulations/control-center/data/town-asset-repair')
out.mkdir(parents=True,exist_ok=True)
asset='/Game/Carla/Static/GenericMaterials/00_LegacyMaterials/Building/BuildingDetailsMaster'
file=Path('/mnt/simulations/carla/Unreal/CarlaUnreal/Content')/(asset.removeprefix('/Game/')+'.uasset')
backup=out/'BuildingDetailsMaster.before.uasset'
if not backup.exists():shutil.copy2(file,backup)
m=u.load_asset(asset);assert m
changed=[]
for e in u.ObjectIterator(u.MaterialExpressionTextureSample):
 if not e.get_path_name().startswith(m.get_path_name()+':'):continue
 t=e.get_editor_property('texture')
 if t and t.get_name()=='T_Flat_orm':
  changed.append({'expression':e.get_path_name(),'before':str(e.get_editor_property('sampler_type'))})
  e.set_editor_property('sampler_type',u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
if changed:
 u.MaterialEditingLibrary.recompile_material(m)
 assert u.EditorAssetLibrary.save_loaded_asset(m,False)
report={'material_changes':changed}
(out/'material-repair.json').write_text(json.dumps(report,indent=2));print('TOWN_MATERIAL_REPAIR '+json.dumps(report))
