"""Validate published texture references and the opaque-alpha regression assets."""
import gzip,json,struct
from pathlib import Path
from PIL import Image,ImageStat
root=Path(__file__).resolve().parents[1];scene=root/'static/scenes/Town10HD_Opt';manifest=json.loads((scene/'manifest.json').read_text());materials=None
for layer in manifest['layers']:
 raw=gzip.decompress((scene/layer['file']).read_bytes());length=struct.unpack_from('<I',raw)[0];current=json.loads(raw[4:4+length])['materials']
 if materials is not None:assert materials==current,'Layer material mappings differ'
 materials=current
for m in materials.values():
 if m.get('web_texture'):
  with Image.open(scene/'textures'/m['web_texture']) as im:im.verify()
repaired=[]
for item in json.loads((root/'data/dark-scene-textures.json').read_text()):
 m=materials[item['key']];im=Image.open(scene/'textures'/m['web_texture']).convert('RGB')
 assert sum(ImageStat.Stat(im).mean)/3>15, f"Opaque source colour lost: {m['name']}"
 repaired.append(m['name'])
print(f'PASS: all scene texture references decode; {len(repaired)} opaque materials retain source colour')
