"""Build map-specific meter annotations from the read-only UE scene export."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1];source=json.loads((root/'data/scene-source/scene.json').read_text())
meters=[]
for group in source['groups'].values():
 if 'SM_Parkingmeter.' in group['mesh']:
  for i,t in enumerate(group['transforms']):meters.append({'name':f'SM_Parkingmeter:{i}','x':t[0],'y':t[2],'z':t[1]})
# Structure footprint is derived from the mesh, not assumed to be ground bays.
import numpy as np
blob=(root/'data/scene-source/geometry.bin').read_bytes();areas=[]
for group in source['groups'].values():
 if group['mesh'].endswith('/SM_Parking.SM_Parking'):
  mesh=source['meshes'][group['mesh']];v=np.concatenate([np.frombuffer(blob,dtype='<f4',count=s['position'][1],offset=s['position'][0]).reshape(-1,3) for s in mesh['sections']])
  for t in group['transforms']:
   assert abs(t[6]-1)<1e-6  # This known Town10 structure has no rotation.
   points=v*np.array(t[7:])+np.array(t[:3]);lo=points.min(axis=0);hi=points.max(axis=0)
   areas.append({'name':'Parking structure','source':'Unreal structure footprint; individual spaces unavailable','polygon':[[float(x),float(y)] for x,y in [(lo[0],lo[2]),(hi[0],lo[2]),(hi[0],hi[2]),(lo[0],hi[2])]]})
(root/'data/parking/Town10HD_Opt.json').write_text(json.dumps({'map':source['map'],'meters':meters,'areas':areas},indent=2));print(len(meters),'meters',len(areas),'parking structures')
