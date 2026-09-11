import unreal as u,json
cls=u.load_class(None,'/Game/Carla/Blueprints/LevelDesign/BP_Carla_Sky.BP_Carla_Sky_C')
obj=u.get_default_object(cls)
report={}
for attr in ['directional_light_component_sun','directional_light_component_moon']:
 try:
  light=obj.get_editor_property(attr)
  report[attr]={name:str(light.get_editor_property(name)) for name in ['intensity','cast_cloud_shadows','cloud_shadow_strength','cloud_shadow_on_surface_strength','cloud_shadow_extent','atmosphere_sun_light','atmosphere_sun_light_index']}
 except Exception as e:report[attr]=str(e)
try:
 light=obj.get_editor_property('sky_light_component')
 report['sky_light']={name:str(light.get_editor_property(name)) for name in ['intensity','real_time_capture','source_type','cubemap','mobility','visible','affect_global_illumination','affect_reflection','sky_distance_threshold']}
except Exception as e:report['sky_light']=str(e)
mat=u.load_asset('/Game/Carla/Static/FX/VolumetricClouds/MI_Town10Clouds')
report['cloud_parameters']={str(n):u.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(mat,n) for n in u.MaterialEditingLibrary.get_scalar_parameter_names(mat)}
with open('/mnt/simulations/control-center/data/weather-running-fix/sky-defaults.json','w') as f:json.dump(report,f,indent=2)
u.log('WEATHER_SKY_DEFAULTS '+json.dumps(report))
