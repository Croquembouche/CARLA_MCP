"""Apply source texture mappings to all browser layers without re-exporting scene geometry."""
import json,gzip,struct,hashlib,subprocess
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1];src=root/'data/scene-material-patch';info=json.loads((src/'manifest.json').read_text());dest=root/'static/scenes/Town10HD_Opt';cache={};report={'textures':0,'materials':0,'errors':[]}
current_manifest=json.loads((dest/'manifest.json').read_text());raw=gzip.decompress((dest/current_manifest['layers'][0]['file']).read_bytes());current_n=struct.unpack_from('<I',raw)[0];current_materials=json.loads(raw[4:4+current_n])['materials']
# Recover opaque textures whose unused alpha was previously premultiplied to black.
dark_manifest=root/'data/dark-textures/manifest.json'
if dark_manifest.exists():
 dark=json.loads(dark_manifest.read_text())
 for item in json.loads((root/'data/dark-scene-textures.json').read_text()):
  path=item['texture'];export=dark[path]
  if export['success']:
   info['textures'][path]={**export,'file':str(root/'data/dark-textures'/export['file']),'source_2d':True}
   mat=info['materials'][item['key']];mat.pop('web_texture',None);mat['browser_texture']=path;mat['source_opaque_repair']=True
for key,mat in info['materials'].items():
 if not mat.get('source_opaque_repair') and not mat.get('web_texture') and current_materials.get(key,{}).get('web_texture'):mat['web_texture']=current_materials[key]['web_texture']
 path=mat.get('browser_texture');sticker=path and path==mat.get('textures',{}).get('Sticker Diffuse');tint=tuple(mat.get('vectors',{}).get('Base Color',[1,1,1])[:3]) if sticker else None
 texture_key=repr((path,tint)) if sticker else path
 if sticker:mat.pop('web_texture',None)
 if mat.get('web_texture') or path not in info['textures']:continue
 try:
  if texture_key not in cache:
   item=info['textures'][path]
   if not item['success']:raise ValueError('Texture export failed')
   file=src/item['file']
   if file.suffix=='.exr':
    png=file.with_suffix('.converted.png')
    if not png.exists():subprocess.run(['convert',str(file),'-colorspace','sRGB','-resize','512x512>',str(png)],check=True,capture_output=True)
    file=png
   if file.suffix=='.dds':
    dds=file.read_bytes();height,width=struct.unpack_from('<II',dds,12);mips=struct.unpack_from('<I',dds,28)[0] or 1;fmt=struct.unpack_from('<I',dds,128)[0]
    if fmt not in (87,91):raise ValueError('Unsupported cube source format '+str(fmt))
    # Use an upright interior wall face for a lightweight static window preview.
    stride=sum(max(1,width>>i)*max(1,height>>i)*4 for i in range(mips));start=148+(0 if item.get('source_2d') else 3*stride);im=Image.frombytes('RGBA',(width,height),dds[start:start+width*height*4],'raw','BGRA').convert('RGB');mat['browser_projection']='source_2d' if item.get('source_2d') else 'interior_wall'
   else:
    im=Image.open(file).convert('RGBA' if sticker or 'MASKED' in mat['blend'] else 'RGB')
    if sticker:
     rgb=tuple(round(255*(12.92*max(0,c) if c<=.0031308 else 1.055*min(1,c)**(1/2.4)-.055)) for c in tint)
     im=Image.alpha_composite(Image.new('RGBA',im.size,(*rgb,255)),im).convert('RGB')
     mat['browser_projection']='paint_and_stickers'
   im.thumbnail((512,512),Image.Resampling.LANCZOS);name=hashlib.sha256(texture_key.encode()).hexdigest()[:20]+'.webp';im.save(dest/'textures'/name,'WEBP',quality=88,method=6);cache[texture_key]=name;report['textures']+=1
  mat['web_texture']=cache[texture_key];report['materials']+=1
 except Exception as e:report['errors'].append({'material':key,'error':str(e)})
manifest=json.loads((dest/'manifest.json').read_text());delta=0
for layer in manifest['layers']:
 raw=gzip.decompress((dest/layer['file']).read_bytes());n=struct.unpack_from('<I',raw)[0];meta=json.loads(raw[4:4+n]);binary=raw[(4+n+3)//4*4:];meta['materials'].update(info['materials']);header=json.dumps(meta,separators=(',',':')).encode();packed=gzip.compress(struct.pack('<I',len(header))+header+b'\0'*((-len(header))%4)+binary,compresslevel=9,mtime=0);name=layer['category']+'-'+hashlib.sha256(packed).hexdigest()[:12]+'.scene.gz';(dest/name).write_bytes(packed);delta+=len(packed)-layer['bytes'];layer.update(file=name,bytes=len(packed),decodedBytes=4+len(header)+(-len(header))%4+len(binary))
texture_names={m['web_texture'] for m in meta['materials'].values() if m.get('web_texture')};texture_bytes=sum((dest/'textures'/n).stat().st_size for n in texture_names);geometry_bytes=sum(l['bytes'] for l in manifest['layers']);manifest['summary'].update(geometryBytes=geometry_bytes,textureBytes=texture_bytes,bytes=geometry_bytes+texture_bytes,textures=len(texture_names));manifest['summary']['layers']=manifest['layers'];manifest['materialMappingUpgrade']=True;(dest/'manifest.json.tmp').write_text(json.dumps(manifest,separators=(',',':')));(dest/'manifest.json.tmp').replace(dest/'manifest.json');(root/'data/scene-material-patch-report.json').write_text(json.dumps(report,indent=2));print(report)
