"""Read-only Unreal commandlet export. Never saves or modifies source assets."""
import unreal,json,traceback,os,array,collections,time
ROOT='/mnt/simulations/control-center/data/scene-source'
os.makedirs(ROOT,exist_ok=True)
MAP=os.environ.get('CARLA_SCENE_MAP','/Game/Carla/Maps/Town10HD_Opt')
out={'map':MAP.removeprefix('/Game/'),'meshes':{},'groups':{},'materials':{},'errors':[],'skipped':collections.Counter()}
binary=open(ROOT+'/geometry.bin','wb')
def buf(values,kind):
 a=array.array(kind,values);offset=binary.tell();a.tofile(binary);return [offset,len(a)]
def transform(t):
 p=t.translation;q=t.rotation;s=t.scale3d
 return [p.x/100,p.z/100,p.y/100,-q.x,-q.z,-q.y,q.w,s.x,s.z,s.y]
def category(path):
 p=path.lower()
 for cat,terms in [('vegetation',['vegetation','tree','grass','bush','plant']),('buildings',['building','skyscr','apt','museum','factory','parkingramp']),('roads',['road','sidewalk','curb','terrain','landscape','ground']),('water',['water','sea','beach']),('street',['traffic','sign','light','pole','fence','bench','trash','busstop','billboard','prop'])]:
  if any(t in p for t in terms):return cat
 return 'props'
def material(m):
 if not m:return None
 key=m.get_path_name()
 if key in out['materials']:return key
 data={'name':m.get_name(),'vectors':{},'textures':{}}
 try:
  for n in unreal.MaterialEditingLibrary.get_vector_parameter_names(m):
   c=unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(m,n) if isinstance(m,unreal.MaterialInstanceConstant) else None
   if c:data['vectors'][str(n)]=[c.r,c.g,c.b,c.a]
  for n in unreal.MaterialEditingLibrary.get_texture_parameter_names(m):
   t=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(m,n) if isinstance(m,unreal.MaterialInstanceConstant) else None
   if t:data['textures'][str(n)]=t.get_path_name()
  data['blend']=str(m.get_blend_mode())
 except Exception as e:data['error']=str(e)
 out['materials'][key]=data
 return key
try:
 unreal.EditorLevelLibrary.load_level(MAP)
 actors=unreal.EditorLevelLibrary.get_all_level_actors();out['actor_count']=len(actors)
 editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) or unreal.get_default_object(unreal.StaticMeshEditorSubsystem)
 for ai,a in enumerate(actors):
  if 'Sky' in a.get_class().get_name():out['skipped']['sky']+=1;continue
  for c in a.get_components_by_class(unreal.StaticMeshComponent):
   m=c.get_editor_property('static_mesh')
   if not m:continue
   if not c.is_visible() or c.get_editor_property('hidden_in_game'):out['skipped']['hidden']+=1;continue
   path=m.get_path_name();cat=category(path+' '+a.get_class().get_name())
   try:
    if path not in out['meshes']:
     lod=m.get_num_lods()-1;sections=[]
     for si in range(m.get_num_sections(lod)):
      v,ix,n,uv,tan=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(m,lod,si)
      if not len(ix):continue
      # Reflect y/z, preserving outward faces by reversing each triangle.
      indices=list(ix)
      for j in range(0,len(indices),3):indices[j+1],indices[j+2]=indices[j+2],indices[j+1]
      sections.append({'position':buf((k for p in v for k in [p.x/100,p.z/100,p.y/100]),'f'),'normal':buf((k for p in n for k in [p.x,p.z,p.y]),'f'),'uv':buf((k for p in uv for k in [p.x,p.y]),'f'),'index':buf(indices,'I'),'slot':editor.get_lod_material_slot(m,lod,si)})
     out['meshes'][path]={'sections':sections,'lod':lod,'category':cat}
    mats=[material(c.get_material(i)) for i in range(c.get_num_materials())]
    key=path+'|'+str(mats)
    group=out['groups'].setdefault(key,{'mesh':path,'category':cat,'materials':mats,'transforms':[]})
    if isinstance(c,unreal.InstancedStaticMeshComponent):
     for i in range(c.get_instance_count()):group['transforms'].append(transform(c.get_instance_transform(i,True)))
    else:group['transforms'].append(transform(c.get_world_transform()))
    if isinstance(c,unreal.SplineMeshComponent):out['skipped']['spline_deformation_not_baked']+=1
   except Exception:
    out['errors'].append({'actor':a.get_name(),'mesh':path,'error':traceback.format_exc()})
    open(ROOT+'/errors.json','w').write(json.dumps(out['errors']))
    if len(out['errors'])>5:raise
  if ai%100==0:
   binary.flush();open(ROOT+'/progress.json','w').write(json.dumps({'actors':ai,'total':len(actors),'meshes':len(out['meshes']),'bytes':binary.tell()}))
except:out['errors'].append({'error':traceback.format_exc()})
binary.close()
open(ROOT+'/scene.json','w').write(json.dumps(out,separators=(',',':')))
print('SCENE EXPORT COMPLETE',len(out['meshes']),len(out['groups']),len(out['errors']))
