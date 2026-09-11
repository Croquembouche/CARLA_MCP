"""Stream an uncompressed session tar without creating another copy on disk."""
import queue
import tarfile
import threading


def archive_stream(root):
    chunks=queue.Queue(maxsize=8);cancel=threading.Event()
    def put(data):
        while not cancel.is_set():
            try:chunks.put(data,timeout=.2);return
            except queue.Full:pass
        raise BrokenPipeError('Download disconnected')
    class Sink:
        def write(self,data):put(data);return len(data)
    def produce():
        try:
            with tarfile.open(fileobj=Sink(),mode='w|',bufsize=1024*1024) as tar:
                tar.add(root,arcname=root.name,recursive=True)
            put(None)
        except BrokenPipeError:pass
        except Exception as e:
            try:put(e)
            except BrokenPipeError:pass
    worker=threading.Thread(target=produce,daemon=True,name='recording-download');worker.start()
    try:
        while True:
            data=chunks.get()
            if data is None:return
            if isinstance(data,Exception):raise data
            yield data
    finally:cancel.set();worker.join(timeout=1)
