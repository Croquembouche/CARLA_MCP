import unreal,json,os,hashlib,traceback
ROOT='/mnt/simulations/control-center/data/scene-source'
src=json.load(open(ROOT+'/scene.json'));out={};os.makedirs(ROOT+'/textures',exist_ok=True)
for key,m in src['materials'].items():
 textures=m['textures'];name=next((n for n in ['BaseColor','Base Color','Diffuse','Albedo','Color','BaseColorTexture','SpeedSign_d','Grass'] if n in textures),None)
 if not name:continue
 paths=[textures[name]]
 if 'Opacity Mask' in textures:paths.append(textures['Opacity Mask'])
 m['browser_texture']=paths[0]
 if len(paths)>1:m['browser_alpha']=paths[1]
 for path in paths:
  if path in out:continue
  file=hashlib.sha256(path.encode()).hexdigest()[:16]+'.png'
  try:
   task=unreal.AssetExportTask();task.object=unreal.load_asset(path);task.filename=ROOT+'/textures/'+file;task.automated=True;task.prompt=False;task.replace_identical=True
   success=unreal.Exporter.run_asset_export_task(task)
   if not success:
    file=file.replace('.png','.exr');task.filename=ROOT+'/textures/'+file;success=unreal.Exporter.run_asset_export_task(task)
   out[path]={'file':file,'success':success,'errors':list(task.errors)}
  except:out[path]={'success':False,'error':traceback.format_exc()}
  open(ROOT+'/texture-export-progress.json','w').write(json.dumps({'textures':len(out)}))
open(ROOT+'/textures.json','w').write(json.dumps(out))
open(ROOT+'/scene.json','w').write(json.dumps(src,separators=(',',':')))
