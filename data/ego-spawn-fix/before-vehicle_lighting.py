"""Automatic native vehicle lights, including vehicles outside Traffic Manager."""
import carla

L=carla.VehicleLightState
OWNED=int(L.Position)|int(L.LowBeam)|int(L.Fog)|int(L.Brake)|int(L.Reverse)|int(L.LeftBlinker)|int(L.RightBlinker)

def automatic_state(current,weather,control,*,parked=False,arrived=False):
    # Preserve explicitly selected high beams, interior and special/emergency lights.
    state=int(current)&~OWNED
    sun=float(weather.sun_altitude_angle)
    dim=sun<15 or float(weather.precipitation)>80 or float(weather.fog_density)>20
    if sun<35:state|=int(L.Position)
    if dim:state|=int(L.Position)|int(L.LowBeam)
    if float(weather.fog_density)>20:state|=int(L.Fog)
    if not parked:
        if arrived or control.brake>.1:state|=int(L.Brake)
        if control.reverse or control.gear<0:state|=int(L.Reverse)
        if not arrived:
            if control.steer<-.25:state|=int(L.LeftBlinker)
            elif control.steer>.25:state|=int(L.RightBlinker)
    return state

class AutomaticVehicleLights:
    def __init__(self):self.tm_modes={}
    def update(self,owner):
        if owner.mode!='live':return
        weather=owner.world.get_weather()
        states=owner.world.get_vehicles_light_states()
        commands=[];present=set()
        for aid,m in list(owner.managed.items()):
            a=m['actor']
            if not a.type_id.startswith('vehicle.'):continue
            present.add(aid)
            tm_active=m['planner']=='tm' and not any(m.get(k) for k in ('parked','arrived','parking_trip','_restore_hold'))
            if self.tm_modes.get(aid)!=tm_active:
                owner.tm.update_vehicle_lights(a,tm_active);self.tm_modes[aid]=tm_active
            # TM uses its route to signal upcoming turns and its commanded brake.
            if tm_active:continue
            current=int(states.get(aid,L.NONE))
            target=automatic_state(current,weather,a.get_control(),parked=bool(m.get('parked')),arrived=bool(m.get('arrived')))
            if target!=current:commands.append(carla.command.SetVehicleLightState(aid,L(target)))
        self.tm_modes={aid:mode for aid,mode in self.tm_modes.items() if aid in present}
        for response in owner.client.apply_batch_sync(commands,False) if commands else []:
            if response.error:raise RuntimeError('Automatic vehicle lighting failed: '+response.error)
