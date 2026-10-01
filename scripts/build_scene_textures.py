"""Downsample exported source textures once, preserving foliage opacity."""
import json,subprocess,hashlib,os,struct
from pathlib import Path
from PIL import Image
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
ROOT=Path(__file__).resolve().parents[1]
if os.environ.get('CARLA_SCENE_SOURCE'):subprocess.run([__import__('sys').executable,str(ROOT/'scripts/import_scene_landscape.py')],check=True)
src=Path(os.environ.get('CARLA_SCENE_SOURCE',ROOT/'data/scene-source'));scene=json.loads((src/'scene.json').read_text());textures=json.loads((src/'textures.json').read_text());dest=ROOT/'static/scenes'/scene['map'].split('/')[-1]/'textures';dest.mkdir(parents=True,exist_ok=True)
pool=ProcessPoolExecutor(max_workers=4,mp_context=get_context('fork'));encodes=[]
def save_texture(im,name):
 target=dest/name
 if target.exists() and target.stat().st_size:
  try:
   with Image.open(target) as previous:previous.verify()
   return
  except (OSError,ValueError):pass
 temp=target.with_name(name+'.'+str(os.getpid())+'.tmp');im.save(temp,'WEBP',quality=80,method=4);temp.replace(target)
cache={};stats={'textures':0,'pixels':0,'bytes':0,'failed':[]}
def read(path,preserve_alpha=False):
 info=textures.get(path,{})
 if not info.get('success'):return None
 filename=src/'textures'/info['file']
 try:
  if filename.suffix=='.exr':
   png=filename.with_suffix('.alpha.png' if preserve_alpha else '.opaque.png')
   if not png.exists():subprocess.run(['convert',str(filename),'-colorspace','sRGB',*([] if preserve_alpha else ['-alpha','off']),'-resize','384x384>',str(png)],check=True,capture_output=True)
   filename=png
  if filename.suffix=='.dds':
   dds=filename.read_bytes();height,width=struct.unpack_from('<II',dds,12);fmt=struct.unpack_from('<I',dds,128)[0]
   if fmt in (2,10,11):
    pixels=np.frombuffer(dds, dtype='<f4' if fmt==2 else ('<f2' if fmt==10 else '<u2'), count=width*height*4, offset=148).reshape(height,width,4).astype(np.float32)
    if fmt==11:pixels/=65535.
    pixels=np.nan_to_num(pixels,nan=0,posinf=1,neginf=0);rgb=np.clip(pixels[:,:,:3],0,1)
    pixels[:,:,:3]=np.where(rgb<=.0031308,rgb*12.92,1.055*np.power(rgb,1/2.4)-.055)
    im=Image.fromarray((np.clip(pixels,0,1)*255+.5).astype(np.uint8),'RGBA').convert('RGBA' if preserve_alpha else 'RGB');im.thumbnail((384,384),Image.Resampling.LANCZOS);return im
   if fmt==61:
    im=Image.frombytes('L',(width,height),dds[148:148+width*height]).convert('RGB');im.thumbnail((384,384),Image.Resampling.LANCZOS);return im
   if fmt in (87,91):
    im=Image.frombytes('RGBA',(width,height),dds[148:148+width*height*4],'raw','BGRA').convert('RGBA' if preserve_alpha else 'RGB');im.thumbnail((384,384),Image.Resampling.LANCZOS);return im
  im=Image.open(filename).convert('RGBA' if preserve_alpha else 'RGB');im.thumbnail((384,384),Image.Resampling.LANCZOS);return im
 except Exception as e:stats['failed'].append({'path':path,'error':str(e)});return None
for mat in scene['materials'].values():
 path=mat.get('browser_texture');alpha=mat.get('browser_alpha');preserve_alpha='MASKED' in mat.get('blend','') and not alpha;key=(path,alpha,preserve_alpha)
 if not path:continue
 if key not in cache:
  im=read(path,preserve_alpha)
  if im is None:cache[key]=None;continue
  if alpha:
   mask=read(alpha)
   if mask:im.putalpha(mask.convert('L').resize(im.size,Image.Resampling.LANCZOS))
  if 'MASKED' not in mat.get('blend',''):im=im.convert('RGB')
  name=hashlib.sha256(repr(key).encode()+im.tobytes()).hexdigest()[:16]+'.webp';encodes.append((name,pool.submit(save_texture,im,name)));cache[key]=name;stats['textures']+=1;stats['pixels']+=im.width*im.height
 mat['web_texture']=cache[key]
for name,future in encodes:
 try:future.result()
 except Exception as error:stats['failed'].append({'path':name,'error':str(error)})
pool.shutdown()
stats['bytes']=sum((dest/name).stat().st_size for name in set(cache.values()) if name and (dest/name).exists())
(src/'scene.json').write_text(json.dumps(scene,separators=(',',':')))
(src/'texture-report.json').write_text(json.dumps(stats,indent=2));print(stats)

if stats['failed']:raise SystemExit('Texture conversion failed; see texture-report.json')
