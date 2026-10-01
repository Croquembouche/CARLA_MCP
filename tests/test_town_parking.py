"""Town isolation and native-surface acceptance, without a live CARLA server."""
import hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import parking
from tools.build_town_parking import surface_kind

def test_scene_revision_is_resolved_per_town(tmp_path):
    source=tmp_path/'parking'/'Town02_Opt.json';source.parent.mkdir()
    scene=tmp_path/'scene-sources'/'Town02_Opt';scene.mkdir(parents=True)
    (scene/'geometry.bin').write_bytes(b'town two geometry');(scene/'scene.json').write_bytes(b'town two materials')
    annotation={'map':'Carla/Maps/Town02_Opt','validated_spaces':[{'id':'P0001'}],'validation':{'opendrive_sha256':hashlib.sha256(b'xml').hexdigest(),'geometry_sha256':hashlib.sha256((scene/'geometry.bin').read_bytes()).hexdigest(),'scene_sha256':hashlib.sha256((scene/'scene.json').read_bytes()).hexdigest()}}
    source.write_text(json.dumps(annotation))
    assert parking.build_parking(SimpleNamespace(name='Carla/Maps/Town02_Opt'),'xml',source)['parking_spaces']==[{'id':'P0001'}]
    assert not parking.build_parking(SimpleNamespace(name='Town01_Opt'),'xml',source)['parking_spaces']
    (scene/'geometry.bin').write_bytes(b'changed native geometry')
    result=parking.build_parking(SimpleNamespace(name='Town02_Opt'),'xml',source)
    assert not result['parking_spaces'] and 'revalidation' in result['parking_source']

def test_curbs_paint_and_grass_cannot_be_used_as_parking_pavement():
    for material in ('MI_LaneMarking','MI_CurbConcrete','Grass','MI_Gutter'):
        assert surface_kind('/Road/Town03',material) is None
    assert surface_kind('/Road/Town02','MI_WetRoad_1')=='pavement'
    assert surface_kind('/SideWalk/Unique','MI_WetSideWalk_4') is None
    assert surface_kind('/Road/Town12','Asphalt1_Road')=='pavement'

def pavement_fixture(quads,materials=None,**options):
    import numpy as np
    from tools.build_town_parking import Pavement
    binary=bytearray();sections=[]
    def put(a):
        result=[len(binary),a.size];binary.extend(a.tobytes());return result
    for qi,quad in enumerate(quads):
        sections.append({'position':put(np.asarray(quad,dtype='<f4').reshape(-1)),
                         'index':put(np.asarray([0,1,2,0,2,3],dtype='<u4')),'slot':qi if materials else 0})
    scene={'meshes':{'/Road/Test':{'sections':sections}},'groups':{'test':{'mesh':'/Road/Test','category':'roads','materials':materials or ['MI_WetRoad_1'],'transforms':[[0,0,0,0,0,0,1,1,1,1]]}}}
    return Pavement(scene,bytes(binary),**options)

def test_parking_follows_native_slope_and_rejects_an_internal_pavement_gap():
    import pytest
    surface=pavement_fixture([[[0,0,0],[10,.4,0],[10,.4,10],[0,0,10]]])
    bay={'x':5,'y':5,'z':.2,'polygon':parking.corners(5,5,6,2,0)}
    assert surface.fits(bay)
    assert bay['corner_z']==pytest.approx([.08,.32,.32,.08])
    # Corners are supported, but the complete footprint crosses a missing strip.
    gap=pavement_fixture([[[0,0,0],[4.5,0,0],[4.5,0,10],[0,0,10]],[[5.5,0,0],[10,0,0],[10,0,10],[5.5,0,10]],[[0,10,0],[10,10,0],[10,10,10],[0,10,10]]])
    assert not gap.fits({'z':0,'polygon':parking.corners(5,5,6,2,0)})


def test_paint_can_fill_a_native_pavement_seam_but_cannot_create_a_bay():
    quads=[[[0,0,0],[4.9,0,0],[4.9,0,10],[0,0,10]],[[5.1,0,0],[10,0,0],[10,0,10],[5.1,0,10]],[[4.9,0,0],[5.1,0,0],[5.1,0,10],[4.9,0,10]]]
    surface=pavement_fixture(quads,['MI_WetRoad_1','MI_WetRoad_1','MI_LaneMarking'],include_markings=True,min_base_fraction=.8)
    assert surface.fits({'z':0,'polygon':parking.corners(5,5,6,2,0)})
    paint=pavement_fixture([[[0,0,0],[10,0,0],[10,0,10],[0,0,10]]],['MI_LaneMarking'],include_markings=True,min_base_fraction=.8)
    assert not paint.fits({'z':0,'polygon':parking.corners(5,5,6,2,0)})
