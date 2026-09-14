"""Publish and write the exact captured samples using standard ROS 2 messages."""
import math
import numpy as np
from scipy.spatial.transform import Rotation
import bootstrap
import rclpy
from rclpy.serialization import serialize_message
from rclpy.qos import QoSProfile, ReliabilityPolicy
import rosbag2_py
from builtin_interfaces.msg import Time
from std_msgs.msg import Header, String
from recording import sensor_metadata
from physical_lidar import is_physical, points as physical_points, ROS_FIELDS
import json
from sensor_msgs.msg import Image, CameraInfo, PointCloud2, PointField, Imu, NavSatFix
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from tf2_msgs.msg import TFMessage


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
    h = header(data.timestamp, name + ('_optical' if 'camera.' in kind else ''))
    if 'camera.' in kind:
        msg = Image(header=h, height=data.height, width=data.width, is_bigendian=0,
                    encoding='32FC2' if kind.endswith('optical_flow') else 'bgra8',
                    step=data.width * (8 if kind.endswith('optical_flow') else 4),
                    data=bytes(data.raw_data))
        return msg, 'sensor_msgs/msg/Image'
    if kind=='sensor.lidar.ray_cast' and is_physical(data):
        a=physical_points(data).copy();a['y']*=-1;a['azimuth']*=-1
        return PointCloud2(header=h,height=1,width=len(a),
            fields=[PointField(name=n,offset=o,datatype=t,count=1) for n,o,t in ROS_FIELDS],
            is_bigendian=False,point_step=64,row_step=len(a)*64,data=a.tobytes(),
            is_dense=bool(np.isfinite(np.column_stack([a[n] for n in ('x','y','z')])).all())), 'sensor_msgs/msg/PointCloud2'
    if 'lidar.' in kind or kind.endswith('radar'):
        fields = [('x', PointField.FLOAT32), ('y', PointField.FLOAT32), ('z', PointField.FLOAT32)]
        if kind.endswith('ray_cast_semantic'):
            a = np.frombuffer(data.raw_data, dtype=[('xyz','<f4',(3,)),('cos','<f4'),('id','<u4'),('tag','<u4')]).copy()
            a['xyz'][:, 1] *= -1
            fields += [('cos_incidence', PointField.FLOAT32), ('object_id', PointField.UINT32), ('semantic_tag', PointField.UINT32)]
        elif kind.endswith('radar'):
            raw = np.frombuffer(data.raw_data, dtype='<f4').reshape(-1,4)
            v, az, alt, d = raw.T
            a = np.column_stack((d*np.cos(alt)*np.cos(az), -d*np.cos(alt)*np.sin(az),
                                 d*np.sin(alt), v, -az, alt, d)).astype('<f4')
            fields += [(k,PointField.FLOAT32) for k in ('velocity','azimuth','altitude','depth')]
        else:
            a = np.frombuffer(data.raw_data,dtype='<f4').reshape(-1,4).copy()
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


class RosIO:
    def __init__(self):
        rclpy.init(args=[])
        self.node = rclpy.create_node('carla_control_center')
        self.publishers = {}
        self.writer = None
        self.topics = {}
        self.counts = {}

    def remove_prefix(self,prefix):
        for topic in list(self.publishers):
            if topic.startswith(prefix):self.node.destroy_publisher(self.publishers.pop(topic))

    def start_bag(self, directory):
        self.writer = rosbag2_py.SequentialWriter()
        self.writer.open(rosbag2_py.StorageOptions(uri=str(directory),storage_id='sqlite3'),
                         rosbag2_py.ConverterOptions(input_serialization_format='cdr',output_serialization_format='cdr'))
        self.topics, self.counts = {}, {}

    def emit(self, topic, message, typename, timestamp):
        if topic in self.publishers and self.publishers[topic].msg_type is not type(message):
            self.node.destroy_publisher(self.publishers.pop(topic))
        if topic not in self.publishers:
            self.publishers[topic] = self.node.create_publisher(type(message), topic,
                QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT))
        self.publishers[topic].publish(message)
        if self.writer:
            if topic not in self.topics:
                self.writer.create_topic(rosbag2_py.TopicMetadata(name=topic,type=typename,serialization_format='cdr'))
                self.topics[topic] = typename
            self.writer.write(topic,serialize_message(message),round(timestamp*1e9))
            self.counts[topic] = self.counts.get(topic,0)+1

    def frame(self, timestamp, egos, samples):
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
            msg,typename=sensor_message(sample,name)
            suffix = 'image' if 'camera.' in sample['type'] else 'points' if ('lidar.' in sample['type'] or sample['type'].endswith('radar')) else 'data'
            self.emit('/carla/'+name+'/'+suffix,msg,typename,sample['data'].timestamp)
            self.emit('/carla/'+name+'/metadata',String(data=json.dumps(sensor_metadata(sample))), 'std_msgs/msg/String',sample['data'].timestamp)
            t=sample['mount']; q=quaternion(t)
            tf=TransformStamped(header=header(timestamp,f"ego_{sample['parent']}"),child_frame_id=name)
            tf.transform.translation.x,tf.transform.translation.y,tf.transform.translation.z=t.location.x,-t.location.y,t.location.z
            tf.transform.rotation.x,tf.transform.rotation.y,tf.transform.rotation.z,tf.transform.rotation.w=q
            transforms.append(tf)
            if 'camera.' in sample['type']:
                data=sample['data']; fov=float(cfg['attributes'].get('fov',90)); f=data.width/(2*math.tan(math.radians(fov)/2))
                info=CameraInfo(header=msg.header,height=data.height,width=data.width,distortion_model='plumb_bob',d=[0.]*5,
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
        self.writer=None  # Humble finalizes metadata in SequentialWriter destructor.
        return counts

    def close(self):
        self.stop_bag(); self.node.destroy_node(); rclpy.shutdown()
