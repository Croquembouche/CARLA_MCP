import json,time,urllib.request,subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import bootstrap,carla
base='http://127.0.0.1:8095'
for _ in range(600):
 try:s=json.load(urllib.request.urlopen(base+'/api/status',timeout=10))
 except OSError:time.sleep(1);continue
 if s['phase']=='error':raise RuntimeError(s['error'])
 if s.get('recovery_operation',{}).get('stage')=='ready':break
 time.sleep(1)
else:raise RuntimeError('Restore timeout')
ego=next(int(k) for k,v in s['managed'].items() if v['role']=='ego')
c=carla.Client('127.0.0.1',2000);c.set_timeout(10)
# Hold only the ego for repeatable same-view weather comparisons. The simulator
# still runs while applying each preset; restore its normal planner afterwards.
for response in c.apply_batch_sync([carla.command.SetAutopilot(ego,False,8005),carla.command.ApplyVehicleControl(ego,carla.VehicleControl(brake=1,hand_brake=True))],False):
 if response.error:raise RuntimeError(response.error)
print('RESTORED, EGO HELD FOR MATCHING VIEWS',ego,flush=True)
try:
 subprocess.run(['/home/william/.nvm/versions/node/v22.22.3/bin/node','data/weather-running-fix/verify-after.mjs'],check=True)
finally:
 for response in c.apply_batch_sync([carla.command.ApplyVehicleControl(ego,carla.VehicleControl()),carla.command.SetAutopilot(ego,s['managed'][str(ego)]['planner']=='tm',8005)],False):
  if response.error:print('Restore control:',response.error,flush=True)
