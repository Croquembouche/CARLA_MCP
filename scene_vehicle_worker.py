"""Short-lived visibility client for a render worker; owns no world clock."""
import json,sys,os
import bootstrap,carla

def apply_visibility(world,all_names,hidden_names):
    objects=[o for label in ('Car','Truck','Bus','Motorcycle','Bicycle') for o in world.get_environment_objects(getattr(carla.CityObjectLabel,label))]
    world.enable_environment_objects({o.id for o in objects if o.name in all_names-hidden_names},True)
    world.enable_environment_objects({o.id for o in objects if o.name in hidden_names},False)
    # A synchronous request drains the preceding visibility commands before exit.
    world.get_environment_objects(carla.CityObjectLabel.Car)

if __name__=='__main__':
    request=json.load(sys.stdin)
    client=carla.Client('127.0.0.1',request['port']);client.set_timeout(90)
    apply_visibility(client.get_world(),set(request['all_names']),set(request['hidden_names']))
    print('SCENERY_VISIBILITY_APPLIED',flush=True)
    # All RPCs have completed and output is flushed. This isolated helper owns
    # no clock or persistent files; avoid native CARLA background-thread teardown
    # racing the Python interpreter after a successful worker update.
    os._exit(0)
