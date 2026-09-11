import unreal,json,hashlib,os
root='/mnt/simulations/control-center/data';dest=root+'/dark-textures';os.makedirs(dest,exist_ok=True);out={}
for item in json.load(open(root+'/dark-scene-textures.json')):
 path=item['texture']
 if path in out:continue
 name=hashlib.sha256(path.encode()).hexdigest()[:20]+'.dds';task=unreal.AssetExportTask();task.object=unreal.load_asset(path);task.filename=dest+'/'+name;task.exporter=unreal.TextureExporterDDS();task.automated=True;task.prompt=False;task.replace_identical=True
 out[path]={'file':name,'success':unreal.Exporter.run_asset_export_task(task),'errors':[str(e) for e in task.errors]}
json.dump(out,open(dest+'/manifest.json','w'))
