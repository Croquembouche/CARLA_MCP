import unreal,json
out={}
for name in ['SunIntensity','SkylightIntensity','FogIntensity']:
 c=unreal.load_asset('/Game/Carla/Blueprints/Weather/Weather2_Curves/'+name+'_2')
 out[name]={str(v):c.get_float_value(v) for v in [-90,-35,0,8,35,65,90]}
m=unreal.load_asset('/Game/Carla/Static/FX/VolumetricClouds/MI_Town10Clouds')
out['cloud_scalars']=[str(n) for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(m)]
open('/mnt/simulations/control-center/data/weather-curves.json','w').write(json.dumps(out,indent=2))
