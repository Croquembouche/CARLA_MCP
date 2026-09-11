"""Read authored parking decals and bay markers without changing the UE level."""
import unreal,json,os
out={'map':'Carla/Maps/Town10HD_Opt','actors':[],'decals':[]}
unreal.EditorLevelLibrary.load_level('/Game/Carla/Maps/Town10HD_Opt')
for a in unreal.EditorLevelLibrary.get_all_level_actors():
 name=a.get_name();label=a.get_actor_label();kind=a.get_class().get_name()
 if any(t in (name+' '+label+' '+kind).lower() for t in ['park','decal']):
  t=a.get_actor_transform();p=t.translation;r=t.rotation.rotator()
  out['actors'].append({'name':name,'label':label,'class':kind,'x':p.x/100,'y':p.y/100,'z':p.z/100,'yaw':r.yaw})
 for c in a.get_components_by_class(unreal.DecalComponent):
  m=c.get_editor_property('decal_material');t=c.get_world_transform();p=t.translation;r=t.rotation.rotator();size=c.get_editor_property('decal_size');scale=t.scale3d
  out['decals'].append({'actor':name,'label':label,'material':m.get_path_name() if m else None,'x':p.x/100,'y':p.y/100,'z':p.z/100,'yaw':r.yaw,'pitch':r.pitch,'roll':r.roll,'size':[size.x/100,size.y/100,size.z/100],'scale':[scale.x,scale.y,scale.z]})
open('/mnt/simulations/control-center/data/parking/scene-parking.json','w').write(json.dumps(out,indent=2))
print('PARKING_EXPORT',len(out['actors']),len(out['decals']),flush=True)
