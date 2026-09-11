import unreal,json,traceback
out={}
try:
 path='/Game/Carla/Static/TrafficSignal/M_MovementSignal'
 material=unreal.load_asset(path)
 if not material:
  material=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_MovementSignal','/Game/Carla/Static/TrafficSignal',unreal.Material,unreal.MaterialFactoryNew())
 material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
 material.set_editor_property('two_sided',False)
 unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
 vertex=unreal.MaterialEditingLibrary.create_material_expression(material,unreal.MaterialExpressionVertexColor,-400,0)
 strength=unreal.MaterialEditingLibrary.create_material_expression(material,unreal.MaterialExpressionConstant,-400,180)
 strength.set_editor_property('r',1.)
 multiply=unreal.MaterialEditingLibrary.create_material_expression(material,unreal.MaterialExpressionMultiply,-180,0)
 connections=[unreal.MaterialEditingLibrary.connect_material_expressions(vertex,'',multiply,'A'),unreal.MaterialEditingLibrary.connect_material_expressions(strength,'',multiply,'B'),unreal.MaterialEditingLibrary.connect_material_property(multiply,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)]
 assert all(connections),connections
 unreal.MaterialEditingLibrary.recompile_material(material)
 unreal.EditorAssetLibrary.save_loaded_asset(material)
 out={'created':path,'connections':connections,'emissive_strength':1,'two_sided':False}
except:out={'error':traceback.format_exc()}
open('/mnt/simulations/control-center/data/signal-material-report.json','w').write(json.dumps(out))
