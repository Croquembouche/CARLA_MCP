import unreal,json,os,hashlib,traceback,shutil
from pathlib import Path
ROOT=os.environ.get('CARLA_SCENE_SOURCE','/mnt/simulations/control-center/data/scene-source')
src=json.load(open(ROOT+'/scene.json'));out={};os.makedirs(ROOT+'/textures',exist_ok=True)
cache=Path('/mnt/simulations/control-center/data/scene-texture-cache');cache.mkdir(exist_ok=True)
def link_or_copy(source,target):
 source=Path(source);target=Path(target)
 if target.exists() and os.path.samefile(source,target):return
 temp=target.with_name(target.name+'.'+str(os.getpid())+'.tmp')
 if temp.exists():temp.unlink()
 try:os.link(source,temp)
 except OSError:shutil.copy2(source,temp)
 os.replace(temp,target)

# CPU DDS exports retain opaque RGB even where unused alpha is zero. Reuse
# identical unmodified source textures across towns instead of re-exporting them.
for manifest in Path('/mnt/simulations/control-center/data/scene-sources').glob('*/textures.json'):
 try:exported=json.loads(manifest.read_text())
 except (OSError,ValueError):continue
 for item in exported.values():
  if not item.get('success') or not item.get('file','').endswith('.dds'):continue
  f=manifest.parent/'textures'/item['file'];target=cache/f.name
  if f.exists() and not target.exists():
   try:os.link(f,target)
   except OSError:shutil.copy2(f,target)
for key,m in src['materials'].items():
 textures=m['textures'];name=next((n for n in ['BaseColor','Base Color','Diffuse','Albedo','Color','BaseColorTexture','SpeedSign_d','Grass','Sticker Diffuse','FakeInterior'] if n in textures),None)
 if not name:continue
 paths=[textures[name]]
 if 'Opacity Mask' in textures:paths.append(textures['Opacity Mask'])
 m['browser_texture']=paths[0]
 if len(paths)>1:m['browser_alpha']=paths[1]
 for path in paths:
  if path in out:continue
  file=hashlib.sha256(path.encode()).hexdigest()[:16]+'.dds'
  try:
   cached=cache/file
   package=path.split('.')[0]
   asset=Path('/mnt/simulations/carla/Unreal/CarlaUnreal/Content')/(package.removeprefix('/Game/')+'.uasset') if package.startswith('/Game/') else Path('/mnt/simulations/UnrealEngine5_carla/Engine/Content')/(package.removeprefix('/Engine/')+'.uasset')
   if cached.exists() and asset.exists() and cached.stat().st_mtime>=asset.stat().st_mtime:
    target=Path(ROOT)/'textures'/file
    link_or_copy(cached,target)
    out[path]={'file':file,'success':True,'cached':True};continue
   target=Path(ROOT)/'textures'/file
   if target.exists() and target.stat().st_nlink>1:target.unlink()
   task=unreal.AssetExportTask();task.object=unreal.load_asset(path);task.filename=ROOT+'/textures/'+file;task.exporter=unreal.TextureExporterDDS();task.automated=True;task.prompt=False;task.replace_identical=True
   success=unreal.Exporter.run_asset_export_task(task)
   if not success:
    file=file.replace('.dds','.png');task.filename=ROOT+'/textures/'+file;task.exporter=None;success=unreal.Exporter.run_asset_export_task(task)
   if not success:
    file=file.replace('.png','.exr');task.filename=ROOT+'/textures/'+file;success=unreal.Exporter.run_asset_export_task(task)
   if success and file.endswith('.dds'):link_or_copy(ROOT+'/textures/'+file,cache/file)
   out[path]={'file':file,'success':success,'errors':list(task.errors)}
  except:out[path]={'success':False,'error':traceback.format_exc()}
  open(ROOT+'/texture-export-progress.json','w').write(json.dumps({'textures':len(out)}))
open(ROOT+'/textures.json','w').write(json.dumps(out))
open(ROOT+'/scene.json','w').write(json.dumps(src,separators=(',',':')))
