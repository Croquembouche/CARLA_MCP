"""Build the optional local ROS bag binding against the installed ROS/Python ABI."""
import os
import subprocess
import sysconfig
from pathlib import Path

root=Path(__file__).resolve().parents[1]
ros=Path('/opt/ros/humble')
target=root/('_bag_native'+sysconfig.get_config_var('EXT_SUFFIX'))
temporary=target.with_name(target.name+'.next')
args=['g++','-O2','-shared','-fPIC','-std=c++17','-fvisibility=hidden',
      '-I'+sysconfig.get_path('include'),'-I'+str(ros/'include')]
args+=['-I'+str(p) for p in sorted((ros/'include').iterdir()) if p.is_dir()]
args += [str(root/'native/bag_native.cpp'),'-L'+str(ros/'lib'),
         '-Wl,-rpath,'+str(ros/'lib'),'-lrosbag2_cpp','-lrosbag2_storage','-lrcutils','-lfastcdr',
         '-o',str(temporary)]
subprocess.run(args,check=True)
os.replace(temporary,target)
print(target)
