"""Small valid GLB fixture, used only to validate the browser mesh loader."""
import json,struct
from pathlib import Path
vertices=[(-3,0,-3),(3,0,-3),(3,6,-3),(-3,6,-3),(-3,0,3),(3,0,3),(3,6,3),(-3,6,3)]
indices=[0,1,2,0,2,3,4,6,5,4,7,6,0,4,5,0,5,1,3,2,6,3,6,7,0,3,7,0,7,4,1,5,6,1,6,2]
binary=b''.join(struct.pack('<fff',*v) for v in vertices)+struct.pack('<36H',*indices)
j={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0}],
   'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1,'material':0}]}],
   'materials':[{'pbrMetallicRoughness':{'baseColorFactor':[1,.5,.1,1],'metallicFactor':0,'roughnessFactor':1}}],
   'buffers':[{'byteLength':len(binary)}],'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':96,'target':34962},{'buffer':0,'byteOffset':96,'byteLength':72,'target':34963}],
   'accessors':[{'bufferView':0,'componentType':5126,'count':8,'type':'VEC3','min':[-3,0,-3],'max':[3,6,3]},{'bufferView':1,'componentType':5123,'count':36,'type':'SCALAR'}]}
raw=json.dumps(j,separators=(',',':')).encode();raw+=b' '*((-len(raw))%4)
result=struct.pack('<III',0x46546c67,2,12+8+len(raw)+8+len(binary))+struct.pack('<II',len(raw),0x4e4f534a)+raw+struct.pack('<II',len(binary),0x004e4942)+binary
(Path(__file__).parent/'scene-fixture.glb').write_bytes(result)
