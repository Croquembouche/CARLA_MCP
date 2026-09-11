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
        commands=[];command_ids=[];present=set();warnings=[]
        snapshot=owner.world.get_snapshot()
        for aid,m in list(owner.managed.items()):
            a=m['actor']
            if not a.type_id.startswith('vehicle.'):continue
            present.add(aid)
            # Spawn adds the managed actor before its first world tick. Its
            # control snapshot does not exist yet. Removed actors can also
            # outlive their snapshot briefly through a cached Actor handle.
            if not snapshot.has_actor(aid):continue
            try:
                tm_active=m['planner']=='tm' and not any(m.get(k) for k in ('parked','arrived','parking_trip','_restore_hold'))
                if self.tm_modes.get(aid)!=tm_active:
                    owner.tm.update_vehicle_lights(a,tm_active);self.tm_modes[aid]=tm_active
                if tm_active:continue
                current=int(states.get(aid,L.NONE))
                parked=bool(m.get('parked'))
                control=None if parked else a.get_control()
                target=automatic_state(current,weather,control,parked=parked,arrived=bool(m.get('arrived')))
                if target!=current:
                    commands.append(carla.command.SetVehicleLightState(aid,L(target)));command_ids.append(aid)
            except RuntimeError as error:
                # Auxiliary lighting must not abort spawning or the world tick.
                warnings.append({'id':aid,'model':a.type_id,'detail':str(error)})
        self.tm_modes={aid:mode for aid,mode in self.tm_modes.items() if aid in present}
        for aid,response in zip(command_ids,owner.client.apply_batch_sync(commands,False) if commands else []):
            if response.error:warnings.append({'id':aid,'detail':response.error})
        owner.state['vehicle_lighting']={'status':'degraded' if warnings else 'ready','warnings':warnings}
