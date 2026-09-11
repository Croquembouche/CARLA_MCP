import unreal,json,os
ROOT='/mnt/simulations/control-center/data/scene-material-patch';m=json.load(open(ROOT+'/manifest.json'))
for path,item in m['textures'].items():
 if item['success']:continue
 task=unreal.AssetExportTask();task.object=unreal.load_asset(path);task.filename=ROOT+'/'+item['file'].rsplit('.',1)[0]+'.dds';task.exporter=unreal.TextureExporterDDS();task.automated=True;task.prompt=False;task.replace_identical=True
 item['success']=unreal.Exporter.run_asset_export_task(task)
 if item['success']:item['file']=os.path.basename(task.filename)
 item['class']=str(task.object.get_class());item['errors']=[str(e) for e in task.errors]
open(ROOT+'/manifest.json','w').write(json.dumps(m))
