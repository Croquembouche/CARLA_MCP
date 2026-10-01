"""Collect one synchronized frame in arrival order, with event-driven waits."""
import queue
import time


def collect_frame(sensors,frame,timestamp,notification,stop_event,fault,on_sample,progress,timeout=90):
    pending=dict(sensors)
    deadline=time.monotonic()+timeout
    while pending:
        if stop_event.is_set():raise RuntimeError('Sensor wait cancelled during shutdown')
        error=fault()
        if error:raise RuntimeError(error)
        # Clear before inspecting queues: arrivals during/after the scan set it
        # again, so there is no lost wakeup between an empty scan and wait().
        notification.clear()
        for sid,sensor in list(pending.items()):
            if sensor['overflow']:raise RuntimeError(f'Sensor {sid} queue overflow: simulation paused; no complete recording claim')
            while True:
                try:data=sensor['queue'].get_nowait()
                except queue.Empty:break
                if data.frame<frame:continue
                if data.frame!=frame or abs(data.timestamp-timestamp)>1e-5:
                    raise RuntimeError(f'Sensor {sid} frame or timestamp mismatch')
                on_sample(sid,sensor,data)
                del pending[sid]
                break
        if not pending:return
        sid=next(iter(pending));progress(sid,pending[sid])
        remaining=deadline-time.monotonic()
        if remaining<=0:raise RuntimeError(f'Sensor {sid} did not deliver frame {frame}')
        # Periodically observe cancellation/worker failure even with no sensor
        # callbacks. Work and retained samples are bounded to this one frame.
        notification.wait(min(.25,remaining))
