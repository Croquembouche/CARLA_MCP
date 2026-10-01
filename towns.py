"""Discover complete installed town levels, excluding streamed tiles/sublevels."""
import re
from pathlib import Path

MAPS = Path('/mnt/simulations/carla/Unreal/CarlaUnreal/Content/Carla/Maps')
DEFAULT_TOWN = '/Game/Carla/Maps/Town10HD_Opt'


def available_towns(root=MAPS):
    candidates = list(root.glob('Town*.umap'))
    candidates += [p / (p.name + '.umap') for p in root.glob('Town*') if p.is_dir()]
    return [{'id': '/Game/Carla/Maps/' + p.relative_to(root).with_suffix('').as_posix(),
             'name': p.stem} for p in sorted(candidates)
            if p.is_file() and re.fullmatch(r'Town\d+(?:HD)?(?:_Opt)?', p.stem)]


def resolve_town(value=None, root=MAPS):
    value = value or DEFAULT_TOWN
    matches = [t['id'] for t in available_towns(root)
               if value in (t['id'], t['id'].removeprefix('/Game/'), t['name'])]
    if len(matches) != 1:
        raise ValueError('Choose an installed town from the town selector')
    return matches[0]
