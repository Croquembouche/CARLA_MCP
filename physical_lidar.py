"""Versioned physical LiDAR point schema, shared by previews, recordings and ROS."""
import numpy as np

FLOAT_FIELDS=('x','y','z','intensity','range','signal','ambient','pulse_width','azimuth','elevation','time_offset','confidence')
DTYPE=np.dtype([(name,'<f4') for name in FLOAT_FIELDS]+[('pulse_id','<u8'),('channel','<u2'),('return_id','u1'),('return_count','u1'),('flags','<u4')])
assert DTYPE.itemsize==64
ROS_FIELDS=[(name,i*4,7) for i,name in enumerate(FLOAT_FIELDS)]+[('pulse_id_low',48,6),('pulse_id_high',52,6),('channel',56,4),('return_id',58,2),('return_count',59,2),('flags',60,6)]

def is_physical(data):
    return hasattr(data,'scan_start') and hasattr(data,'pulse_count')

def points(data):
    raw=np.frombuffer(data.raw_data,dtype=DTYPE)
    if np.any(raw['channel']>=data.channels):raise ValueError('Physical LiDAR channel exceeds packet channel count')
    return raw

def xyzi(data):
    if is_physical(data):
        p=points(data)
        return np.column_stack([p[n] for n in ('x','y','z','intensity')])
    return np.frombuffer(data.raw_data,dtype='<f4').reshape(-1,4)

def metadata(data):
    p=points(data)
    return dict(output_format='extended',point_stride=64,schema_version=1,
        point_fields=[dict(name=n,offset=DTYPE.fields[n][1],dtype=DTYPE.fields[n][0].str) for n in DTYPE.names],
        scan_start=data.scan_start,scan_end=data.scan_end,pulse_count=data.pulse_count,
        scan_flags=data.flags,profile_crc=data.profile_crc,sequence=data.sequence,wavelength_nm=data.wavelength_nm,
        point_counts=np.bincount(p['channel'],minlength=data.channels).tolist(),
        calibration_status='validated' if data.flags&1 else 'uncalibrated',
        coordinates='Raw points are in the sensor frame at each firing; time_offset is relative to scan_start. Deskew before treating the cloud as one rigid frame.')
