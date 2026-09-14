"""Read the same installed profile files consumed by native physical LiDAR."""
import hashlib
import json
import os
from pathlib import Path
import re

PROFILE_DIR=Path(os.environ.get('CARLA_LIDAR_PROFILE_DIR','/mnt/simulations/carla/Unreal/CarlaUnreal/Content/Carla/Config/Lidar'))

def catalog():
    result=[]
    for path in sorted(PROFILE_DIR.glob('*.json')):
        if path.name=='materials.json' or path.stem.endswith('-test'):continue
        try:
            raw=path.read_bytes();value=json.loads(raw)
            if value.get('version')!=1 or not isinstance(value.get('receiver',{}),dict):continue
            calibration=value.get('calibration',{})
            result.append(dict(name=path.stem,model=value.get('model','generic-pulsed-tof'),calibration_status=calibration.get('status','uncalibrated'),beam_samples=value.get('beam_samples',7),wavelength_nm=value.get('receiver',{}).get('wavelength_nm',905),max_returns=value.get('receiver',{}).get('max_returns',2),sha256=hashlib.sha256(raw).hexdigest()))
        except (ValueError,OSError,TypeError):continue
    return result

def validate(attrs):
    if attrs.get('physical_model','false').lower()!='true':
        if attrs.get('output_format','xyzi')!='xyzi':raise ValueError('Extended LiDAR output requires the physical model')
        return
    if attrs.get('material_model','true').lower()!='true':raise ValueError('Physical LiDAR requires material_model=true')
    name=attrs.get('physical_profile','generic')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name) or not (PROFILE_DIR/(name+'.json')).is_file():raise ValueError('Select an installed physical LiDAR profile')
    if attrs.get('output_format','extended') not in ('extended','xyzi'):raise ValueError('LiDAR output_format must be extended or xyzi')
