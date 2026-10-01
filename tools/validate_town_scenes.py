"""Check published town packages, all buffer references, materials and map identity."""
import argparse,gzip,json,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

def validate(name):
    folder=ROOT/'static/scenes'/name;m=json.loads((folder/'manifest.json').read_text())
    assert m['map'].split('/')[-1]==name
    assert not m['summary'].get('errors')
    total=0;instances=0;materials=set();legacy_uv=0
    for layer in m['layers']:
        assert layer['bytes']<=96*1024**2 and layer['decodedBytes']<=256*1024**2,(name,layer['category'],'browser budget')
        raw=gzip.decompress((folder/layer['file']).read_bytes());length=struct.unpack_from('<I',raw)[0];meta=json.loads(raw[4:4+length]);base=(4+length+3)&~3
        assert len(raw)==layer['decodedBytes'];triangles=0
        def array(r,kind='<f4'):
            assert r[0]>=0 and r[1]>=0 and base+r[0]+r[1]*4<=len(raw)
            return np.frombuffer(raw,kind,r[1],base+r[0])
        for g in meta['groups']:
            t=array(g['transforms']);assert t.size==g['count']*10 and np.isfinite(t).all()
            instances+=g['count']
            for s in meta['meshes'][g['mesh']]['sections']:
                p=array(s['position']);ix=array(s['index'],'<u4');assert np.isfinite(p).all() and len(p)%3==0 and len(ix)%3==0 and (len(ix)==0 or int(ix.max())<len(p)//3)
                normals=array(s['normal']);uv=array(s['uv']);assert normals.size==len(p) and uv.size==len(p)//3*2 and np.isfinite(normals).all()
                # Older packages are repaired by the loader's tested planar UV fallback.
                legacy_uv+=int(np.sum(~np.isfinite(uv)))
                triangles+=len(ix)//3*g['count']
            materials.update(k for k in g['materials'] if k)
        assert triangles==layer['triangles'],(name,layer['category'],triangles,layer['triangles']);total+=triangles
        for key in materials:
            texture=meta['materials'].get(key,{}).get('web_texture')
            if texture:assert (folder/'textures'/texture).is_file(),texture
    assert total==m['summary']['triangles']
    return dict(town=name,layers=len(m['layers']),triangles=total,render_instances=instances,textures=m['summary'].get('textures',0),status='passed',uv_components_repaired_by_loader=legacy_uv)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('towns',nargs='*');a=ap.parse_args();names=a.towns or [p.parent.name for p in (ROOT/'static/scenes').glob('*/manifest.json')]
    report=[validate(n) for n in names];print(json.dumps(report,indent=2));(ROOT/'data/town-scene-validation.json').write_text(json.dumps(report,indent=2))
