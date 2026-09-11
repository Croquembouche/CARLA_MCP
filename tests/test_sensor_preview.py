import sys,io,json
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np
import pytest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sensor_preview import encode_preview,PreviewCache

def camera(raw=None):
    return NS(frame=10,timestamp=.5,width=32,height=16,raw_data=raw if raw is not None else bytes([10,30,220,255])*512)

def test_camera_preview_is_bounded_and_does_not_modify_source():
    data=camera();before=data.raw_data;payload,mime,_=encode_preview('sensor.camera.rgb',data,160)
    image=Image.open(io.BytesIO(payload));assert image.size==(32,16) and mime=='image/jpeg'
    assert image.getpixel((12,8))[0]>200 and data.raw_data==before

@pytest.mark.parametrize('kind',['depth','semantic_segmentation','instance_segmentation','normals'])
def test_other_camera_visualizations_are_valid_images(kind):
    payload,_,_=encode_preview('sensor.camera.'+kind,camera(),320)
    assert Image.open(io.BytesIO(payload)).size==(32,16)

def test_optical_flow_is_visualized_without_native_mutating_conversion():
    data=camera(np.ones((16,32,2),dtype='<f4').tobytes());payload,_,_=encode_preview('sensor.camera.optical_flow',data)
    assert Image.open(io.BytesIO(payload)).size==(32,16)

@pytest.mark.parametrize('kind',['sensor.lidar.ray_cast','sensor.lidar.ray_cast_semantic','sensor.other.radar'])
def test_large_scans_have_a_fixed_transfer_and_drawing_budget(kind):
    data=NS(raw_data=np.zeros((30000,6 if kind.endswith('semantic') else 4),dtype='<f4').tobytes());before=data.raw_data
    payload,mime,headers=encode_preview(kind,data,320)
    assert Image.open(io.BytesIO(payload)).size==(320,320) and len(payload)<100000
    assert int(headers['X-Preview-Points'])<=12000 and int(headers['X-Preview-Source-Points'])==30000
    assert data.raw_data==before

def test_measurements_keep_values_units_and_small_payload():
    d=NS(latitude=40.123456789,longitude=-75.1,altitude=12)
    raw,mime,_=encode_preview('sensor.other.gnss',d);result=json.loads(raw)
    assert result['values']['latitude']==d.latitude and result['units']['altitude']=='m'
    assert len(raw)<512 and mime=='application/json'

def test_preview_cache_is_lazy_and_reuses_encoding():
    cache=PreviewCache();assert cache.encodes==0
    d=camera();a=cache.get('one','sensor.camera.rgb',d,320);assert cache.get('one','sensor.camera.rgb',d,320) is a
    assert cache.encodes==1
    for i in range(40):cache.get(str(i),'sensor.camera.rgb',d,320)
    assert len(cache.items)==32 and cache.bytes<8*1024*1024

def test_http_preview_checks_frame_before_encoding_and_rejects_invalid_width(monkeypatch):
    import app
    from fastapi.testclient import TestClient
    cache=PreviewCache();monkeypatch.setattr(app,'preview_cache',cache)
    monkeypatch.setattr(app,'engine',NS(previews={7:(10,'sensor.camera.rgb',camera())},state={'sensors':[{'id':7}]}))
    c=TestClient(app.app)
    assert c.get('/api/preview/7?after=10').status_code==204 and cache.encodes==0
    result=c.get('/api/preview/7?width=320');assert result.status_code==200 and cache.encodes==1
    assert c.get('/api/preview/7?width=320',headers={'If-None-Match':result.headers['etag']}).status_code==304 and cache.encodes==1
    assert c.get('/api/preview/7?width=4000').status_code==422
    assert c.get('/api/preview/8').status_code==404
    app.engine.state['sensors']=[];assert c.get('/api/preview/7').status_code==404

def test_binary_points_are_bounded_quantized_and_immutable():
    xyz=np.random.default_rng(42).uniform(-120,120,(35000,4)).astype('<f4');xyz[0,0]=np.nan
    d=NS(raw_data=xyz.tobytes());before=d.raw_data
    payload,mime,h=encode_preview('sensor.lidar.ray_cast',d,format='points',point_limit=4000)
    assert mime=='application/vnd.carla.pointcloud' and len(payload)<=36000 and len(payload)%9==0
    decoded=np.frombuffer(payload,dtype=np.dtype([('xyz','<i2',(3,)),('rgb','u1',(3,))]))['xyz']*float(h['X-Point-Scale'])
    sampled=xyz[::9,:3];sampled=sampled[np.isfinite(sampled).all(axis=1)]
    assert np.max(np.abs(decoded-sampled))<=.00501 and d.raw_data==before
    assert h['X-Preview-Source-Points']=='35000'

def test_camera_preview_waits_for_render_warmup(monkeypatch):
    import app
    from fastapi.testclient import TestClient
    cache=PreviewCache();monkeypatch.setattr(app,'preview_cache',cache)
    state={'sensors':[{'id':7}],'camera_warmup':{'stage':'warming','sensor_ids':[7]}}
    monkeypatch.setattr(app,'engine',NS(previews={7:(10,'sensor.camera.rgb',camera())},state=state))
    client=TestClient(app.app)
    waiting=client.get('/api/preview/7')
    assert waiting.status_code==204 and waiting.headers['x-carla-camera-state']=='warming'
    assert not waiting.content and cache.encodes==0
    state['camera_warmup']['stage']='ready'
    assert client.get('/api/preview/7').status_code==200 and cache.encodes==1

def test_semantic_points_and_empty_scan():
    d=NS(raw_data=bytes(24*3));p,_,h=encode_preview('sensor.lidar.ray_cast_semantic',d,format='points');assert len(p)==27
    d=NS(raw_data=b'');p,_,h=encode_preview('sensor.lidar.ray_cast',d,format='points');assert p==b'' and h['X-Preview-Points']=='0'
    with pytest.raises(ValueError):encode_preview('sensor.camera.rgb',camera(),format='points')
