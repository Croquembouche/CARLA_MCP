import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import threading
import time
import pytest
from bag_writer import OrderedBagWriter


def test_bounded_queue_blocks_producer_and_preserves_order():
    entered=threading.Event();release=threading.Event();third_done=threading.Event()
    rows=[];threads=[]
    class Sink:
        def create_topic(self,topic):threads.append(threading.get_ident())
        def write(self,*row):
            threads.append(threading.get_ident())
            if not rows:entered.set();assert release.wait(5)
            rows.append(row)
    writer=OrderedBagWriter('unused',max_bytes=4,factory=lambda _:Sink())
    payload=bytearray(b'ab')
    writer.write('/test',payload,'std_msgs/msg/String',1)
    assert entered.wait(2)
    payload[:]=b'xx'
    writer.write('/test',b'cd','std_msgs/msg/String',2)
    def producer():
        writer.write('/test',b'ef','std_msgs/msg/String',3);third_done.set()
    thread=threading.Thread(target=producer);thread.start()
    try:
        assert not third_done.wait(.1)
        assert writer.pending_bytes==4
    finally:release.set();thread.join(5)
    assert third_done.is_set()
    assert writer.close()=={'/test':3}
    assert rows==[('/test',b'ab',1),('/test',b'cd',2),('/test',b'ef',3)]
    assert len(set(threads))==1 and threads[0]!=threading.get_ident()
    assert writer.high_water_bytes<=4 and writer.pending_bytes==0
    with pytest.raises(RuntimeError,match='closed'):writer.write('/test',b'gh','std_msgs/msg/String',4)


def test_worker_error_propagates_at_drain():
    class Sink:
        def create_topic(self,topic):pass
        def write(self,*args):raise OSError('disk failure')
    writer=OrderedBagWriter('unused',factory=lambda _:Sink())
    writer.write('/test',b'abc','std_msgs/msg/String',1)
    with pytest.raises(OSError,match='disk failure'):writer.close()
    assert writer.closed and not writer.counts


def test_native_bag_flushes_all_messages_on_close(tmp_path):
    import rosbag2_py
    import sqlite3
    from std_msgs.msg import String
    from rclpy.serialization import serialize_message,deserialize_message
    directory=tmp_path/'bag'
    writer=OrderedBagWriter(directory,max_bytes=1024)
    for i in range(100):writer.write('/test',serialize_message(String(data=str(i))),'std_msgs/msg/String',i)
    assert writer.close()=={'/test':100}
    with sqlite3.connect(next(directory.glob('*.db3'))) as db:
        rows=db.execute('select timestamp,data from messages order by id').fetchall()
    assert [(t,deserialize_message(p,String).data) for t,p in rows]==[(i,str(i)) for i in range(100)]
