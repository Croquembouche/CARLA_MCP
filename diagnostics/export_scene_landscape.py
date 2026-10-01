"""Export native landscape heights and visibility holes in an isolated editor.

Must run LAST: clears static component references only in this disposable world,
so Unreal's OBJ exporter emits landscapes without baking static materials.
Never saves the level, components, or source assets.
"""
import os,json
from pathlib import Path
import unreal
if not os.environ.get('CARLA_SCENE_ALREADY_LOADED'):unreal.EditorLevelLibrary.load_level(os.environ['CARLA_SCENE_MAP'])
root=Path(os.environ['CARLA_SCENE_SOURCE']);actors=unreal.EditorLevelLibrary.get_all_level_actors()
landscapes=[a for a in actors if isinstance(a,unreal.Landscape)]
if landscapes:
    for actor in actors:
        for c in actor.get_components_by_class(unreal.StaticMeshComponent):c.set_static_mesh(None)
    task=unreal.AssetExportTask();task.object=unreal.EditorLevelLibrary.get_editor_world();task.filename=str(root/'landscape.obj');task.exporter=unreal.LevelExporterOBJ();task.selected=False;task.automated=True;task.prompt=False;task.replace_identical=True
    # This exporter returns false even after successfully writing geometry.
    returned=unreal.Exporter.run_asset_export_task(task)
    path=root/'landscape.obj'
    if not path.exists() or path.stat().st_size<1000:raise RuntimeError('Landscape export is empty')
    (root/'landscape-report.json').write_text(json.dumps({'actors':len(landscapes),'bytes':path.stat().st_size,'exporter_returned':returned,'errors':list(task.errors)}))
else:(root/'landscape-report.json').write_text(json.dumps({'actors':0,'bytes':0}))
