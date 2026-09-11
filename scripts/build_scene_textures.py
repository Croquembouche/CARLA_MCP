"""Downsample exported source textures once, preserving foliage opacity."""
import json,subprocess,hashlib,os
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];src=ROOT/'data/scene-source';scene=json.loads((src/'scene.json').read_text());textures=json.loads((src/'textures.json').read_text());dest=ROOT/'static/scenes'/scene['map'].split('/')[-1]/'textures';dest.mkdir(parents=True,exist_ok=True)
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
  name=hashlib.sha256(repr(key).encode()).hexdigest()[:16]+'.webp';im.save(dest/name,'WEBP',quality=80,method=6);cache[key]=name;stats['textures']+=1;stats['pixels']+=im.width*im.height;stats['bytes']+=(dest/name).stat().st_size
 mat['web_texture']=cache[key]
(src/'scene.json').write_text(json.dumps(scene,separators=(',',':')))
(ROOT/'data/scene-texture-report.json').write_text(json.dumps(stats,indent=2));print(stats)
