"""Default ego sensors; explicit custom loadouts remain authoritative."""
from copy import deepcopy

DEFAULT_SENSORS=[
 {'name':'front_rgb','type':'sensor.camera.rgb','mount':{'x':1.5,'z':2.2},'attributes':{'image_size_x':'640','image_size_y':'360','fov':'90'}},
 {'name':'roof_lidar','type':'sensor.lidar.ray_cast','mount':{'z':2.5},'attributes':{'channels':'32','range':'80','points_per_second':'200000','rotation_frequency':'20','material_model':'true','physical_model':'true','physical_profile':'generic','output_format':'extended'}},
 {'name':'imu','type':'sensor.other.imu','mount':{},'attributes':{}},
 {'name':'gnss','type':'sensor.other.gnss','mount':{},'attributes':{}},
 {'name':'front_radar','type':'sensor.other.radar','mount':{'x':2.0,'z':1.0},'attributes':{'range':'80','points_per_second':'10000'}},
 {'name':'cabin_overview','type':'sensor.camera.rgb','mount':{'x':.55,'y':0,'z':1.2,'yaw':180,'pitch':-8,'roll':0},'attributes':{'image_size_x':'960','image_size_y':'600','fov':'120','post_process_profile':'CabinObservation','lens_k':'0','use_ray_tracing':'true'}},
]

def default_ego_loadout(model):
    sensors=deepcopy(DEFAULT_SENSORS)
    if model=='vehicle.ambulance.ford':
        cabin=sensors[-1]
        cabin['mount']={'x':1.6,'y':-.55,'z':1.65,'yaw':140,'pitch':-20}
        cabin['attributes']['post_process_profile']='AmbulanceCabinObservation'
    return sensors

def spawn_loadout(payload):
    # Saved scenes and callers may intentionally supply a custom or empty list.
    if 'sensors' in payload:return deepcopy(payload['sensors'])
    return default_ego_loadout(payload['model']) if payload.get('role','ego')=='ego' else []
