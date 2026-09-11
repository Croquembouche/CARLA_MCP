import json,struct,pathlib,math
root=pathlib.Path('static/actors');manifest=json.loads((root/'manifest.json').read_text());catalog=json.loads(pathlib.Path('data/actor-model-catalog.json').read_text())
expected={(a['id'] if isinstance(a,dict) else a) for kind in ['vehicles','walkers'] for a in catalog[kind]}
assert expected <= set(manifest['models']),expected-set(manifest['models'])
files={p['file'] for m in manifest['models'].values() for p in m['parts']};triangles=0
for file in files:
 b=(root/file).read_bytes();magic,version,length=struct.unpack_from('<4sII',b);assert magic==b'glTF' and version==2 and length==len(b)
 n=struct.unpack_from('<I',b,12)[0];g=json.loads(b[20:20+n]);assert g.get('meshes'),file
 for v in g.get('bufferViews',[]):assert v.get('byteOffset',0)+v['byteLength']<=g['buffers'][0]['byteLength'],file
 for a in g.get('accessors',[]):
  v=g['bufferViews'][a['bufferView']];size={5120:1,5121:1,5122:2,5123:2,5125:4,5126:4}[a['componentType']]*{'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
  assert a.get('byteOffset',0)+(a['count']-1)*v.get('byteStride',size)+size<=v['byteLength'],(file,a)
 for mesh in g['meshes']:
  for p in mesh['primitives']:
   pos=g['accessors'][p['attributes']['POSITION']];assert pos['count']>0;assert all(math.isfinite(x) for x in pos.get('min',[])+pos.get('max',[]))
   if 'indices' in p:
    a=g['accessors'][p['indices']];v=g['bufferViews'][a['bufferView']];values=struct.unpack_from('<'+{5121:'B',5123:'H',5125:'I'}[a['componentType']]*a['count'],b,28+n+v.get('byteOffset',0)+a.get('byteOffset',0));assert max(values)<pos['count'],file;triangles+=a['count']//3
 for image in g.get('images',[]):
  if 'uri' in image:assert (root/image['uri']).is_file(),image
print(f'PASS: all {len(expected)} catalog actor types covered; {len(files)} nonempty meshes; {triangles:,} triangles; buffers, indices, bounds and texture files valid.')
