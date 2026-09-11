import unreal,json,traceback
ROOT='/mnt/simulations/control-center/data/scene-source'
src=json.load(open(ROOT+'/scene.json'))
def v(p):return [p.x,p.y,p.z] if hasattr(p,'z') else [p.x,p.y]
def tr(t):
 p=t.translation;q=t.rotation;s=t.scale3d
 return [p.x/100,p.z/100,p.y/100,-q.x,-q.z,-q.y,q.w,s.x,s.z,s.y]
unreal.EditorLevelLibrary.load_level('/Game/'+src['map'].removeprefix('/Game/'));splines=[];errors=[]
for a in unreal.EditorLevelLibrary.get_all_level_actors():
 for c in a.get_components_by_class(unreal.SplineMeshComponent):
  m=c.get_editor_property('static_mesh')
  if not m or not c.is_visible() or c.get_editor_property('hidden_in_game'):continue
  try:
   d={'mesh':m.get_path_name(),'transform':tr(c.get_world_transform()),'materials':[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())]}
   d['axis']=str(c.get_forward_axis());d['up']=v(c.get_spline_up_dir());d['smooth']=bool(c.get_editor_property('smooth_interp_roll_scale'));d['boundary']=[c.get_boundary_min(),c.get_boundary_max()]
   for k in ['start_position','end_position','start_tangent','end_tangent','start_scale','end_scale','start_offset','end_offset']:
    d[k]=v(getattr(c,'get_'+k)())
   for k in ['start_roll','end_roll']:d[k]=getattr(c,'get_'+k)()
   b=m.get_bounding_box();d['bounds']=[v(b.min),v(b.max)];splines.append(d)
  except:errors.append(traceback.format_exc())
open(ROOT+'/splines.json','w').write(json.dumps({'splines':splines,'errors':errors}))
