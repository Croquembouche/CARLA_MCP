import unreal
path='/Game/Carla/Static/TrafficSign/TrafficSignPanel/00_GenericComponents/T_TrafficSignAtlas04_d'
task=unreal.AssetExportTask();task.object=unreal.load_asset(path);task.filename='/mnt/simulations/control-center/data/parking-rules-audit/sign-atlas.tga';task.automated=True;task.prompt=False;task.replace_identical=True
assert unreal.Exporter.run_asset_export_task(task),list(task.errors)
