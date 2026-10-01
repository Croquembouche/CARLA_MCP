"""Export one town in one isolated editor process without saving any assets."""
import os,json
from pathlib import Path
root=Path('/mnt/simulations/control-center')
for script in ['export_scene','export_scene_splines','export_parking','export_scene_textures','export_scene_landscape']:
    path=root/'diagnostics'/(script+'.py')
    exec(compile(path.read_text(),str(path),'exec'),{'__name__':'__main__','__file__':str(path)})
    os.environ['CARLA_SCENE_ALREADY_LOADED']='1'
    if script=='export_scene':
        data=json.loads((Path(os.environ['CARLA_SCENE_SOURCE'])/'scene.json').read_text())
        if data['errors'] or not data['meshes']:raise RuntimeError('Scene export incomplete')
