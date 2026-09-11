import unreal,json,traceback
out={}
try:
 material=unreal.load_asset('/Game/Carla/Static/FX/VolumetricClouds/MI_Town10Clouds')
 out['cloud_scalars']=[str(n) for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(material)]
 out['curves']={}
 for name in ['SunIntensity','SkylightIntensity','FogIntensity']:
  c=unreal.load_asset('/Game/Carla/Blueprints/Weather/Weather2_Curves/'+name+'_2')
  out['curves'][name]={str(v):c.get_float_value(v) for v in [-90,-35,0,8,35,65,90]}

 unreal.EditorLevelLibrary.load_level('/Game/Carla/Maps/Town10HD_Opt')
 actors=unreal.EditorLevelLibrary.get_all_level_actors()
 skies=[a for a in actors if 'Sky' in a.get_class().get_name()]
 out['skies']=[]
 for a in skies:
  entry={'name':a.get_name(),'class':a.get_class().get_path_name(),'components':[]}
  for c in a.get_components_by_class(unreal.ActorComponent):
   d={'name':c.get_name(),'class':c.get_class().get_name()}
   for k in ['intensity','mobility','relative_rotation','fog_density']:
    try:d[k]=str(c.get_editor_property(k))
    except:pass
   entry['components'].append(d)
  entry['functions']=[k for k in dir(a) if any(x in k.lower() for x in ['weather','update','sun'])]
  entry['properties']={}
  for k in ['SunAltitudeAngle','SunAzimuthAngle','Cloudiness','Weather','WeatherParameters','SunOrientation']:
   try:entry['properties'][k]=str(a.get_editor_property(k))
   except Exception as e:entry['properties'][k]=str(e)
  entry['update_test']={} 
  try:
   weather=unreal.WeatherParameters();weather.set_editor_property('sun_altitude_angle',-35.)
   a.set_editor_property('SunAltitudeAngle',-35.)
   a.set_editor_property('SunAzimuthAngle',0.)
   a.set_editor_property('Cloudiness',0.)
   a.call_method('Update')
   entry['update_test']['result']='called'
   entry['update_test']['components']=[{'name':c.get_name(),'rotation':str(c.get_editor_property('relative_rotation')),'intensity':c.get_editor_property('intensity')} for c in a.get_components_by_class(unreal.DirectionalLightComponent)]
  except Exception as e:entry['update_test']['error']=str(e)
  entry['weather_function_tests']={}
  for name in ['UpdateSun','UpdateAtmosphereAndPrecipitation','UpdateSunRotation']:
   try:a.call_method(name,args=(weather,));entry['weather_function_tests'][name]='called'
   except Exception as e:entry['weather_function_tests'][name]=str(e)
  out['skies'].append(entry)
 cls=unreal.EditorAssetLibrary.load_blueprint_class('/Game/Carla/Blueprints/Weather/BP_CarlaWeather')
 open('/mnt/simulations/control-center/data/weather-asset-inspection.json','w').write(json.dumps(out,indent=2))
 w=unreal.EditorLevelLibrary.spawn_actor_from_class(cls,unreal.Vector(0,0,0))
 out['weather_class']=w.get_class().get_path_name();out['props']={}
 for k in ['BP_CarlaSky','BP Carla Sky','SunLight','Sun Light','SkyLight','SunIntensity_Curve','SkyIntensity_Curve']:
  try:out['props'][k]=str(w.get_editor_property(k))
  except Exception as e:out['props'][k]=str(e)
 try:
  w.apply_weather(weather)
  w.set_editor_property('BP_CarlaSky',skies[0])
  out['weather_direct_calls']={}
  for name in ['UpdateSunRotation','UpdateSunAndSky','UpdateSkyAtmosphereAndPrecipitation']:
   try:
    w.call_method(name)
    out['weather_direct_calls'][name]=[{'name':c.get_name(),'rotation':str(c.get_editor_property('relative_rotation')),'intensity':c.get_editor_property('intensity')} for c in skies[0].get_components_by_class(unreal.DirectionalLightComponent)]
   except Exception as e:out['weather_direct_calls'][name]=str(e)
  out['bound_refresh']=[{'name':c.get_name(),'rotation':str(c.get_editor_property('relative_rotation')),'intensity':c.get_editor_property('intensity')} for c in skies[0].get_components_by_class(unreal.DirectionalLightComponent)]
 except Exception as e:out['bound_refresh_error']=str(e)
 out['functions']=[k for k in dir(w) if any(s in k.lower() for s in ['weather','sky','sun'])]
except:out['error']=traceback.format_exc()
open('/mnt/simulations/control-center/data/weather-asset-inspection.json','w').write(json.dumps(out,indent=2))
unreal.SystemLibrary.quit_editor()
