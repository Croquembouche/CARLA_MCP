"""Local dependency locations; ROS stays confined to this application process."""
import sys
from pathlib import Path
for p in ['/mnt/simulations/venvs/carla/lib/python3.10/site-packages',
          '/mnt/simulations/carla/PythonAPI/carla',
          '/opt/ros/humble/local/lib/python3.10/dist-packages',
          '/opt/ros/humble/lib/python3.10/site-packages',
          '/usr/lib/python3/dist-packages']:
    if Path(p).exists() and p not in sys.path:
        sys.path.append(p)
