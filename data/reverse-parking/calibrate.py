import sys,math,json,time
sys.path.insert(0,'.')
import bootstrap,carla
c=carla.Client('127.0.0.1',2100);c.set_timeout(20);w=c.get_world();old=w.get_settings();s=w.get_settings();s.synchronous_mode=True;s.fixed_delta_seconds=.05;w.apply_settings(s)
a=w.try_spawn_actor(w.get_blueprint_library().find('vehicle.mini.cooper'),carla.Transform(carla.Location(x=76,y=66.3,z=.5),carla.Rotation(yaw=180)))
try:
 a.set_autopilot(False,8105);a.set_simulate_physics(True)
 for _ in range(30):w.tick()
 for i in range(180):
  c.apply_batch_sync([carla.command.ApplyVehicleControl(a.id,carla.VehicleControl(throttle=.2,steer=.3,reverse=True))],False);w.tick();time.sleep(.01)
  if i%30:continue
  p=a.get_transform();h=math.radians(p.rotation.yaw);v=a.get_velocity();f=v.x*math.cos(h)+v.y*math.sin(h);lat=-v.x*math.sin(h)+v.y*math.cos(h);omega=math.radians(a.get_angular_velocity().z)
  print(i,'pose',p,'speed',f,lat,'omega',omega,'rear',lat/omega if abs(omega)>.01 else 0,'wheels',[a.get_wheel_steer_angle(x) for x in [carla.VehicleWheelLocation.FL_Wheel,carla.VehicleWheelLocation.FR_Wheel]],flush=True)
finally:a.destroy();w.apply_settings(old)
