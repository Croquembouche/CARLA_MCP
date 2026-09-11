"""Attach lightweight source colour textures to browser actor exports."""
import json,struct,hashlib,subprocess,os
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1];source=root/'data/actor-textures';dest=root/'static/actors';(dest/'textures').mkdir(exist_ok=True)
info=json.loads((source/'manifest.json').read_text());manifest=json.loads((dest/'manifest.json').read_text());cache={};selected=set(json.loads(os.environ.get('ACTOR_MODEL_IDS','[]')));manifest['models']={k:v for k,v in manifest['models'].items() if not selected or k in selected};report={'textures':0,'materials':0,'errors':[]}
def texture(path,alpha=None):
 key=(path,alpha)
 if key in cache:return cache[key]
 def read(p):
  item=info['textures'][p]
  if not item['success']:raise ValueError('Texture export failed '+p)
  file=source/item['file']
  if file.suffix=='.exr':
   png=file.with_suffix('.converted.png')
   if not png.exists():subprocess.run(['convert',str(file),'-colorspace','sRGB','-resize','512x512>',str(png)],check=True,capture_output=True)
   file=png
  im=Image.open(file).convert('RGBA');im.thumbnail((512,512),Image.Resampling.LANCZOS);return im
 im=read(path)
 if alpha:im.putalpha(read(alpha).convert('L').resize(im.size,Image.Resampling.LANCZOS))
 else:im=im.convert('RGB')
 name=hashlib.sha256(repr(key).encode()).hexdigest()[:20]+'.png';im.save(dest/'textures'/name,optimize=True);cache[key]='textures/'+name;report['textures']+=1;return cache[key]
for file in sorted({p['file'] for m in manifest['models'].values() for p in m['parts']}):
 raw=(dest/file).read_bytes();length=struct.unpack_from('<I',raw,12)[0];data=json.loads(raw[20:20+length]);tail=raw[20+length:]
 for mat in data.get('materials',[]):
  m=info['materials'].get(mat.get('name'),{});pbr=mat.setdefault('pbrMetallicRoughness',{})
  # Unreal's unbaked complex inputs otherwise become glTF's fully metallic default.
  pbr['metallicFactor']=min(.35,max(0,pbr.get('metallicFactor',0)));pbr['roughnessFactor']=min(1,max(.2,pbr.get('roughnessFactor',.65)))
  try:
   if m.get('color_texture'):
    uri=texture(m['color_texture'],m.get('alpha_texture'));images=data.setdefault('images',[]);textures=data.setdefault('textures',[]);image=len(images);images.append({'uri':uri});tex=len(textures);textures.append({'source':image});pbr['baseColorTexture']={'index':tex};pbr['baseColorFactor']=[1,1,1,1]
    if m.get('alpha_texture'):mat['alphaMode']='MASK';mat['alphaCutoff']=.4
    report['materials']+=1
   elif 'glass' in mat.get('name','').lower():
    pbr['baseColorFactor']=[.16,.25,.3,.4];mat['alphaMode']='BLEND';mat['doubleSided']=True
  except Exception as e:report['errors'].append({'material':mat.get('name'),'error':str(e)})
 encoded=json.dumps(data,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4);output=struct.pack('<4sIII4s',b'glTF',2,20+len(encoded)+len(tail),len(encoded),b'JSON')+encoded+tail;(dest/file).write_bytes(output)
(root/'data/actor-material-report.json').write_text(json.dumps(report,indent=2));print(report)
