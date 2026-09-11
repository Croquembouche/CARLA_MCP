"""Register the separately configured and audited background motorcycle copies."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1];content=Path('/mnt/simulations/carla/Unreal/CarlaUnreal/Content')
path=content/'Carla/Config/VehicleParameters.json';raw=path.read_bytes();data=json.loads(raw)
presets=json.loads((root/'data/scene-vehicles/motorcycle-presets.json').read_text());audit=json.loads((root/'data/scene-vehicles/physics-audit.json').read_text())
known={(p['Make'].lower(),p['Model'].lower()) for p in data['Vehicles']};added=[]
for name,make,model in [('Harley','Harley','low_rider'),('Vespa','Vespa','zx125'),('Yamaha','Yamaha','yzf'),('KawasakiNinja','Kawasaki','ninja')]:
    p=presets[name];checked=audit['vehicle.verified.'+name.lower()]
    assert len(checked['wheels'])==4 and checked['max_torque']>0,'Physics preset has not passed its reload audit'
    if (make.lower(),model.lower()) in known:continue
    asset=p['blueprint'].split('.')[0].removeprefix('/Game/')+'.uasset';assert (content/asset).exists()
    data['Vehicles'].append(dict(Make=make,Model=model,Class=p['blueprint'],NumberOfWheels=2,Generation=3,ObjectType='background_motorcycle_preset',BaseType='motorcycle',SpecialType='',HasDynamicDoors=False,HasLights=True,RecommendedColors=[],SupportedDrivers=[]))
    added.append('vehicle.'+make.lower()+'.'+model.lower())
if added:
    backup=root/'data/scene-vehicles/backup/VehicleParameters.json'
    if not backup.exists():backup.write_bytes(raw)
    if path.read_bytes()!=raw:raise RuntimeError('Catalogue changed concurrently; retry with latest contents')
    temp=path.with_suffix('.scene-vehicles.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
print(json.dumps({'added':added,'total':len(data['Vehicles'])}))
