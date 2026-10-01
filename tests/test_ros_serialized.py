"""Exercise the native DDS serialized publish path with the exact bag bytes."""
import sys,time
import pytest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import rclpy
from rclpy.qos import QoSProfile,ReliabilityPolicy
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import Image
from rosio import RosIO


@pytest.mark.parametrize('direct_image',[False,True])
def test_recorded_serialized_image_reaches_native_subscriber(direct_image):
    io=RosIO()
    subscriber=rclpy.create_node('capture_serialized_test_subscriber')
    received=[];written=[]
    class Writer:
        def write(self,*args):written.append(args)
    io.writer=Writer()
    topic='/carla_capture_test/serialized_image'
    sub=subscriber.create_subscription(Image,topic,received.append,
        QoSProfile(depth=5,reliability=ReliabilityPolicy.BEST_EFFORT),raw=True)
    try:
        message=Image(height=512,width=512,encoding='bgra8',step=2048,data=bytes(range(256))*4096)
        io.publishers[topic]=io.node.create_publisher(Image,topic,
            QoSProfile(depth=5,reliability=ReliabilityPolicy.BEST_EFFORT))
        deadline=time.monotonic()+10
        while io.publishers[topic].get_subscription_count()<1:
            assert time.monotonic()<deadline,'DDS discovery timed out'
            rclpy.spin_once(subscriber,timeout_sec=.05)
        received.clear()
        if direct_image:
            from _bag_native import serialize_image
            payload=serialize_image(0,0,'',512,512,'bgra8',0,2048,bytes(message.data))
            io.emit_serialized(topic,payload,'sensor_msgs/msg/Image',1.25,Image)
        else:io.emit(topic,message,'sensor_msgs/msg/Image',1.25)
        while not received:
            assert time.monotonic()<deadline,'DDS image did not arrive'
            rclpy.spin_once(subscriber,timeout_sec=.05)
        assert received[-1]==written[-1][1]
        assert deserialize_message(received[-1],Image)==message
        assert written[-1][3]==1250000000
    finally:
        subscriber.destroy_subscription(sub);subscriber.destroy_node();io.node.destroy_node();rclpy.shutdown()
