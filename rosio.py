"""Publish and write the exact captured samples using standard ROS 2 messages."""
import math
from dataclasses import dataclass
import time
import numpy as np
from scipy.spatial.transform import Rotation
import bootstrap
import rclpy
from rclpy.serialization import serialize_message
from rclpy.qos import QoSProfile, ReliabilityPolicy
import rosbag2_py
from builtin_interfaces.msg import Time
from std_msgs.msg import Header, String
from recording import sensor_metadata, sensor_payload
from physical_lidar import is_physical, points as physical_points, ROS_FIELDS
import json
from sensor_msgs.msg import Image, CameraInfo, PointCloud2, PointField, Imu, NavSatFix
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from tf2_msgs.msg import TFMessage
try:
    from _bag_native import serialize_image as _serialize_image
except ImportError:
    _serialize_image = None


def stamp(seconds):
    ns = round(seconds * 1e9)
    return Time(sec=ns // 1000000000, nanosec=ns % 1000000000)


def header(seconds, frame):
    return Header(stamp=stamp(seconds), frame_id=frame)


def quaternion(transform):
    m = np.asarray(transform.get_matrix())[:3, :3]
    mirror = np.diag([1, -1, 1])
    return Rotation.from_matrix(mirror @ m @ mirror).as_quat().tolist()


def sensor_message(sample, name):
    data, kind = sample['data'], sample['type']
    raw=sensor_payload(sample)
    h = header(data.timestamp, name + ('_optical' if 'camera.' in kind else ''))
    if 'camera.' in kind:
        msg = Image(header=h, height=data.height, width=data.width, is_bigendian=0,
                    encoding='32FC2' if kind.endswith('optical_flow') else 'bgra8',
                    step=data.width * (8 if kind.endswith('optical_flow') else 4),
                    data=raw)
        return msg, 'sensor_msgs/msg/Image'
    if kind=='sensor.lidar.ray_cast' and is_physical(data):
        a=physical_points(data,raw).copy();a['y']*=-1;a['azimuth']*=-1
        return PointCloud2(header=h,height=1,width=len(a),
            fields=[PointField(name=n,offset=o,datatype=t,count=1) for n,o,t in ROS_FIELDS],
            is_bigendian=False,point_step=64,row_step=len(a)*64,data=a.tobytes(),
            is_dense=bool(np.isfinite(np.column_stack([a[n] for n in ('x','y','z')])).all())), 'sensor_msgs/msg/PointCloud2'
    if 'lidar.' in kind or kind.endswith('radar'):
        fields = [('x', PointField.FLOAT32), ('y', PointField.FLOAT32), ('z', PointField.FLOAT32)]
        if kind.endswith('ray_cast_semantic'):
            a = np.frombuffer(raw, dtype=[('xyz','<f4',(3,)),('cos','<f4'),('id','<u4'),('tag','<u4')]).copy()
            a['xyz'][:, 1] *= -1
            fields += [('cos_incidence', PointField.FLOAT32), ('object_id', PointField.UINT32), ('semantic_tag', PointField.UINT32)]
        elif kind.endswith('radar'):
            raw = np.frombuffer(raw, dtype='<f4').reshape(-1,4)
            v, az, alt, d = raw.T
            a = np.column_stack((d*np.cos(alt)*np.cos(az), -d*np.cos(alt)*np.sin(az),
                                 d*np.sin(alt), v, -az, alt, d)).astype('<f4')
            fields += [(k,PointField.FLOAT32) for k in ('velocity','azimuth','altitude','depth')]
        else:
            a = np.frombuffer(raw,dtype='<f4').reshape(-1,4).copy()
            a[:,1] *= -1
            fields += [('intensity',PointField.FLOAT32)]
        size = len(fields)*4
        return PointCloud2(header=h,height=1,width=len(a),fields=[PointField(name=n,offset=i*4,datatype=t,count=1) for i,(n,t) in enumerate(fields)],
                           is_bigendian=False,point_step=size,row_step=len(a)*size,data=a.tobytes(),is_dense=True), 'sensor_msgs/msg/PointCloud2'
    if kind.endswith('imu'):
        msg = Imu(header=h)
        msg.orientation_covariance[0] = -1.0
        msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z = data.accelerometer.x, -data.accelerometer.y, data.accelerometer.z
        msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z = -data.gyroscope.x, data.gyroscope.y, -data.gyroscope.z
        return msg, 'sensor_msgs/msg/Imu'
    if kind.endswith('gnss'):
        return NavSatFix(header=h,latitude=data.latitude,longitude=data.longitude,altitude=data.altitude), 'sensor_msgs/msg/NavSatFix'
    raise ValueError('Unsupported ROS sensor type: ' + kind)


@dataclass(frozen=True)
class PreparedSensor:
    value: object
    message_type: type
    typename: str
    sample_header: object
    suffix: str
    serialized: bool
    stage_ms: dict


def prepare_sensor(sample,name,serialized):
    """Prepare one immutable captured sample without publishing any topics."""
    data=sample['data'];kind=sample['type']
    key=(getattr(data,'frame',None),data.timestamp,name,kind,serialized,_serialize_image)
    cached=sample.get('_prepared_ros')
    if cached is not None and cached[0] is data and cached[1]==key:return cached[2]
    started=time.perf_counter();stages={}
    if 'camera.' in kind and _serialize_image is not None:
        h=header(data.timestamp,name+'_optical')
        encoding='32FC2' if kind.endswith('optical_flow') else 'bgra8'
        step=data.width*(8 if encoding=='32FC2' else 4)
        value=_serialize_image(h.stamp.sec,h.stamp.nanosec,h.frame_id,
            data.height,data.width,encoding,0,step,sensor_payload(sample))
        stages['image_cdr']=(time.perf_counter()-started)*1000
        result=PreparedSensor(value,Image,'sensor_msgs/msg/Image',h,'image',True,stages)
    else:
        message,typename=sensor_message(sample,name)
        stages['sensor_message']=(time.perf_counter()-started)*1000
        value=message
        if serialized:
            started=time.perf_counter();value=serialize_message(message)
            stages['serialize']=(time.perf_counter()-started)*1000
        suffix='image' if 'camera.' in kind else 'points' if ('lidar.' in kind or kind.endswith('radar')) else 'data'
        result=PreparedSensor(value,type(message),typename,message.header,suffix,serialized,stages)
    sample['_prepared_ros']=(data,key,result)
    return result


class RosIO:
    def __init__(self):
        rclpy.init(args=[])
        self.node = rclpy.create_node('carla_control_center')
        self.publishers = {}
        self.writer = None
        self.topics = {}
        self.counts = {}
        self.stage_ms = {}

    def remove_prefix(self,prefix):
        for topic in list(self.publishers):
            if topic.startswith(prefix):self.node.destroy_publisher(self.publishers.pop(topic))

    def start_bag(self, directory):
        from bag_writer import OrderedBagWriter
        self.writer = OrderedBagWriter(directory)
        self.topics, self.counts = {}, {}

    def _stage(self,name,started):
        self.stage_ms[name]=self.stage_ms.get(name,0)+(time.perf_counter()-started)*1000

    def _publisher(self,topic,message_type):
        if topic in self.publishers and self.publishers[topic].msg_type is not message_type:
            self.node.destroy_publisher(self.publishers.pop(topic))
        if topic not in self.publishers:
            self.publishers[topic] = self.node.create_publisher(message_type, topic,
                QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT))
        return self.publishers[topic]

    def emit_serialized(self,topic,payload,typename,timestamp,message_type):
        # Both consumers receive the same immutable standard CDR sample.
        started=time.perf_counter();self._publisher(topic,message_type).publish(payload)
        self._stage('dds',started)
        if self.writer:
            started=time.perf_counter();self.writer.write(topic,payload,typename,round(timestamp*1e9))
            self._stage('bag_enqueue',started)
            self.counts[topic] = self.counts.get(topic,0)+1

    def emit(self, topic, message, typename, timestamp):
        if self.writer:
            started=time.perf_counter();payload=serialize_message(message)
            self._stage('serialize',started)
            self.emit_serialized(topic,payload,typename,timestamp,type(message))
        else:self._publisher(topic,type(message)).publish(message)

    def prepare_sample(self,sample):
        name=f"ego_{sample['parent']}/{sample['config']['name']}"
        return prepare_sensor(sample,name,bool(getattr(self,'writer',None)))

    def frame(self, timestamp, egos, samples):
        self.stage_ms={}
        self.emit('/clock',Clock(clock=stamp(timestamp)),'rosgraph_msgs/msg/Clock',timestamp)
        transforms = []
        for actor in egos:
            name = f'ego_{actor.id}'
            t, v, a = actor.get_transform(), actor.get_velocity(), actor.get_angular_velocity()
            q = quaternion(t)
            msg = Odometry(header=header(timestamp,'map'),child_frame_id=name)
            msg.pose.pose.position.x,msg.pose.pose.position.y,msg.pose.pose.position.z=t.location.x,-t.location.y,t.location.z
            msg.pose.pose.orientation.x,msg.pose.pose.orientation.y,msg.pose.pose.orientation.z,msg.pose.pose.orientation.w=q
            msg.twist.twist.linear.x,msg.twist.twist.linear.y,msg.twist.twist.linear.z=np.asarray(t.get_inverse_matrix())[:3,:3].dot([v.x,v.y,v.z])*[1,-1,1]
            msg.twist.twist.angular.x,msg.twist.twist.angular.y,msg.twist.twist.angular.z=np.asarray(t.get_inverse_matrix())[:3,:3].dot([a.x,a.y,a.z])*[-math.pi/180,math.pi/180,-math.pi/180]
            self.emit(f'/carla/{name}/odometry',msg,'nav_msgs/msg/Odometry',timestamp)
            tf=TransformStamped(header=header(timestamp,'map'),child_frame_id=name)
            tf.transform.translation.x,tf.transform.translation.y,tf.transform.translation.z=t.location.x,-t.location.y,t.location.z
            tf.transform.rotation=msg.pose.pose.orientation
            transforms.append(tf)
        for sample in samples:
            cfg=sample['config']; name=f"ego_{sample['parent']}/{cfg['name']}"
            prepared=self.prepare_sample(sample);sample_header=prepared.sample_header
            # Preparation may have overlapped sensor delivery. Preserve its
            # measured CPU cost even though frame() starts a fresh timing row.
            for key,value in prepared.stage_ms.items():
                self.stage_ms[key]=self.stage_ms.get(key,0)+value
            if prepared.serialized:
                self.emit_serialized('/carla/'+name+'/'+prepared.suffix,prepared.value,
                    prepared.typename,sample['data'].timestamp,prepared.message_type)
            else:
                self.emit('/carla/'+name+'/'+prepared.suffix,prepared.value,prepared.typename,sample['data'].timestamp)
            self.emit('/carla/'+name+'/metadata',String(data=json.dumps(sensor_metadata(sample))), 'std_msgs/msg/String',sample['data'].timestamp)
            t=sample['mount']; q=quaternion(t)
            tf=TransformStamped(header=header(timestamp,f"ego_{sample['parent']}"),child_frame_id=name)
            tf.transform.translation.x,tf.transform.translation.y,tf.transform.translation.z=t.location.x,-t.location.y,t.location.z
            tf.transform.rotation.x,tf.transform.rotation.y,tf.transform.rotation.z,tf.transform.rotation.w=q
            transforms.append(tf)
            if 'camera.' in sample['type']:
                data=sample['data']; fov=float(cfg['attributes'].get('fov',90)); f=data.width/(2*math.tan(math.radians(fov)/2))
                info=CameraInfo(header=sample_header,height=data.height,width=data.width,distortion_model='plumb_bob',d=[0.]*5,
                    k=[f,0.,data.width/2,0.,f,data.height/2,0.,0.,1.],r=[1.,0.,0.,0.,1.,0.,0.,0.,1.],
                    p=[f,0.,data.width/2,0.,0.,f,data.height/2,0.,0.,0.,1.,0.])
                self.emit('/carla/'+name+'/camera_info',info,'sensor_msgs/msg/CameraInfo',timestamp)
                optical=TransformStamped(header=header(timestamp,name),child_frame_id=name+'_optical')
                optical.transform.rotation.x,optical.transform.rotation.y,optical.transform.rotation.z,optical.transform.rotation.w=Rotation.from_euler('xyz',[-math.pi/2,0,-math.pi/2]).as_quat().tolist()
                transforms.append(optical)
        self.emit('/tf',TFMessage(transforms=transforms),'tf2_msgs/msg/TFMessage',timestamp)

    def signals(self,timestamp,state):
        payload={'frame':state['frame'],'time':timestamp,'signals':[a for a in state['actors'] if a['type'].startswith('traffic.traffic_light')],'programs':state.get('movement_programs',{})}
        self.emit('/carla/traffic_signals',String(data=json.dumps(payload)), 'std_msgs/msg/String',timestamp)

    def stop_bag(self):
        counts=dict(self.counts)
        writer=self.writer;self.writer=None
        if writer:
            written=writer.close()
            self.last_bag_stats={'budget_bytes':writer.max_bytes,'high_water_bytes':writer.high_water_bytes,
                'pending_bytes_at_close':writer.pending_bytes_at_close,'drain_seconds':writer.drain_seconds,
                'written_messages':sum(written.values()),'backend':writer.backend}
            if written!=counts:raise RuntimeError('Bag accepted/written message counts differ')
        return counts

    def close(self):
        self.stop_bag(); self.node.destroy_node(); rclpy.try_shutdown()
