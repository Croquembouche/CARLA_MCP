"""Single-owner bag writes with bounded bytes, backpressure and explicit drain."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import time


class OrderedBagWriter:
    def __init__(self, directory, max_bytes=64*1024*1024, factory=None):
        if max_bytes<=0:raise ValueError('Bag queue budget must be positive')
        self.max_bytes=max_bytes;self.pending_bytes=0;self.high_water_bytes=0
        self.pending=deque();self.closed=False;self.error=None
        self.drain_seconds=0.;self.pending_bytes_at_close=0
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='rosbag-writer')
        self.counts={};self.topics={};self.writer=None
        self.backend='rosbag2_py'
        try:self.executor.submit(self._open,directory,factory).result()
        except BaseException:
            self.executor.shutdown(wait=True)
            raise

    def _open(self,directory,factory):
        if factory is not None:
            self.writer=factory(directory)
            return
        try:
            from _bag_native import BagWriter
        except ModuleNotFoundError:
            BagWriter=None
        if BagWriter is not None:
            self.writer=BagWriter(str(directory));self.backend='native_gil_released'
            return
        import rosbag2_py
        self.writer=rosbag2_py.SequentialWriter()
        # Humble's built-in cache drops on overflow. Keep it disabled: our
        # producer blocks at its memory limit and all native calls have one owner.
        self.writer.open(rosbag2_py.StorageOptions(uri=str(directory),storage_id='sqlite3',max_cache_size=0),
                         rosbag2_py.ConverterOptions(input_serialization_format='cdr',output_serialization_format='cdr'))

    def _write(self,topic,payload,typename,timestamp):
        if self.error is not None:raise self.error
        try:
            if topic not in self.topics:
                if self.backend=='native_gil_released':self.writer.create_topic(topic,typename)
                else:
                    import rosbag2_py
                    self.writer.create_topic(rosbag2_py.TopicMetadata(name=topic,type=typename,serialization_format='cdr'))
                self.topics[topic]=typename
            elif self.topics[topic]!=typename:
                raise ValueError('Bag topic type changed: '+topic)
            self.writer.write(topic,payload,timestamp)
            self.counts[topic]=self.counts.get(topic,0)+1
        except BaseException as error:
            self.error=error
            raise

    def _reap(self,wait=False):
        while self.pending and (wait or self.pending[0][0].done()):
            future,size=self.pending.popleft()
            try:future.result()
            finally:self.pending_bytes-=size
            if wait:break

    def write(self,topic,payload,typename,timestamp):
        if self.closed:raise RuntimeError('Bag writer is closed')
        self._reap()
        if self.error is not None:raise self.error
        payload=bytes(payload);size=len(payload)
        if size>self.max_bytes:raise ValueError('Single bag message exceeds queue byte budget')
        while self.pending_bytes+size>self.max_bytes or len(self.pending)>=1024:self._reap(wait=True)
        self.pending.append((self.executor.submit(self._write,topic,payload,typename,timestamp),size))
        self.pending_bytes+=size
        self.high_water_bytes=max(self.high_water_bytes,self.pending_bytes)

    def _finish(self):
        if self.backend=='native_gil_released':self.writer.close()
        self.writer=None  # Native destructor flushes and finalizes on its owner thread.

    def close(self):
        if self.closed:
            if self.error is not None:raise self.error
            return dict(self.counts)
        self.closed=True
        started=time.perf_counter();self.pending_bytes_at_close=self.pending_bytes
        try:
            while self.pending:self._reap(wait=True)
        finally:
            try:self.executor.submit(self._finish).result()
            finally:
                self.executor.shutdown(wait=True)
                self.drain_seconds=time.perf_counter()-started
        if self.error is not None:raise self.error
        return dict(self.counts)
