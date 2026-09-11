import json,hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from parking import corners,build_parking
from parking_rules import point_distance,polygon_distance,screen_spaces

def test_footprint_edges_not_just_centres_and_containment():
    p=corners(0,0,8,2,0)
    assert point_distance([0,0],p)==0
    assert point_distance([5,0],p)==1
    bay={'id':'P1','polygon':p}
    good,bad=screen_spaces([bay],{'zones':[{'id':'hydrant','point':[8,0],'clearance_m':4.572,'reason':'hydrant'}]})
    assert not good and bad[0]['restriction_reasons'][0]['distance_m']==4
    assert polygon_distance(corners(0,0,10,1,0),corners(0,0,10,1,90))==0

def test_touching_clearance_is_excluded_and_far_bay_survives():
    zones=[{'id':'crosswalk','polygon':corners(0,0,4,4,0),'clearance_m':6.096}]
    bays=[{'id':'near','polygon':corners(9.096,0,2,2,0)},{'id':'far','polygon':corners(15,0,2,2,30)}]
    good,bad=screen_spaces(bays,{'zones':zones})
    assert [p['id'] for p in good]==['far'] and bad[0]['id']=='near'

def test_town10_restrictions_have_reasons_and_do_not_renumber():
    data=json.loads(Path('data/parking/Town10HD_Opt.json').read_text())
    allowed,excluded=screen_spaces(data['validated_spaces'],data['traffic_rules'])
    reasons={p['id']:{r['kind'] for r in p['restriction_reasons']} for p in excluded}
    assert len(allowed)==53 and len(excluded)==127
    assert 'hydrant' in reasons['P009'] and 'bus_stop' in reasons['P012']
    assert 'crosswalk' in reasons['P020'] and 'posted_conditional' in reasons['P002']
    assert 'posted_mixed' in reasons['P033']
    assert all(r.get('evidence') for p in excluded for r in p['restriction_reasons'])

def test_changed_scene_rejects_stale_restriction_audit(tmp_path):
    xodr=Path('data/map-cache.xodr').read_text();data=json.loads(Path('data/parking/Town10HD_Opt.json').read_text())
    folder=tmp_path/'parking';folder.mkdir();source=folder/'Town10HD_Opt.json';source.write_text(json.dumps(data))
    scene=tmp_path/'scene-source';scene.mkdir();(scene/'scene.json').write_text('{}');(scene/'geometry.bin').write_bytes(b'changed')
    result=build_parking(SimpleNamespace(name='Town10HD_Opt'),xodr,source)
    assert result['parking_spaces']==[] and 'requires revalidation' in result['parking_source']
