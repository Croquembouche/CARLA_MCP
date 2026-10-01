import collections
import queue
import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import controller


def test_late_subscription_can_miss_initial_frames_without_stalling_startup():
    sensors = [dict(queue=queue.Queue(maxsize=8), overflow=False) for _ in range(2)]
    owner = SimpleNamespace(stop_event=threading.Event(), state={'frame': 0})
    frames = []

    def tick(publish):
        assert publish is False
        frames.append(len(frames) + 1)
        owner.state['frame'] = frames[-1]
        for index, sensor in enumerate(sensors):
            if frames[-1] >= (1 if index == 0 else 4):
                sensor.setdefault('arrivals', collections.deque(maxlen=8)).append((frames[-1], 0))
                sensor['queue'].put_nowait(frames[-1])

    owner.tick = tick
    with patch.object(controller.time, 'sleep'):
        controller.Controller.settle_sensor_subscriptions(owner, sensors)
    assert frames == [1, 2, 3, 4]
    assert all(sensor['queue'].empty() and not sensor['overflow'] for sensor in sensors)


def test_missing_subscription_times_out_without_claiming_readiness():
    owner = SimpleNamespace(stop_event=threading.Event(), tick=lambda **kw: None)
    sensor = dict(queue=queue.Queue(), overflow=False)
    with patch.object(controller.time, 'monotonic', side_effect=[0, 301]):
        with pytest.raises(RuntimeError, match='did not deliver startup samples'):
            controller.Controller.settle_sensor_subscriptions(owner, [sensor])


def test_slow_worker_catches_up_before_another_startup_frame_is_queued():
    sensors = [dict(queue=queue.Queue(maxsize=8), overflow=False) for _ in range(2)]
    owner = SimpleNamespace(stop_event=threading.Event(), state={'frame': 0})
    sleeps = []

    def tick(publish):
        owner.state['frame'] += 1
        sensors[0]['arrivals'] = [(owner.state['frame'], 0)]
        sensors[0]['queue'].put_nowait(owner.state['frame'])

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 30:
            sensors[1]['arrivals'] = [(owner.state['frame'], 0)]
            sensors[1]['queue'].put_nowait(owner.state['frame'])

    owner.tick = tick
    with patch.object(controller.time, 'sleep', side_effect=sleep):
        controller.Controller.settle_sensor_subscriptions(owner, sensors)
    assert owner.state['frame'] == 1
    assert len(sleeps) == 30
    assert all(sensor['queue'].empty() for sensor in sensors)


def test_shutdown_cancels_subscription_warmup():
    owner = SimpleNamespace(stop_event=threading.Event())
    owner.stop_event.set()
    with pytest.raises(RuntimeError, match='cancelled during shutdown'):
            controller.Controller.settle_sensor_subscriptions(owner, [{}])


def test_long_first_camera_frame_does_not_queue_more_world_ticks():
    sensors = [dict(queue=queue.Queue(maxsize=8), overflow=False) for _ in range(2)]
    owner = SimpleNamespace(stop_event=threading.Event(), state={'frame': 0})
    now = [0.0]
    sleeps = []

    def tick(publish):
        owner.state['frame'] += 1
        sensors[0]['arrivals'] = [(owner.state['frame'], 0)]
        sensors[0]['queue'].put_nowait(owner.state['frame'])

    def sleep(seconds):
        now[0] += seconds
        sleeps.append(seconds)
        if len(sleeps) == 300:
            # The first renderer frame took six seconds. Advancing the primary
            # while this frame is outstanding would put this stream behind it.
            sensors[1]['arrivals'] = [(1, now[0])]
            sensors[1]['queue'].put_nowait(1)

    owner.tick = tick
    with patch.object(controller.time, 'sleep', side_effect=sleep), \
         patch.object(controller.time, 'monotonic', side_effect=lambda: now[0]):
        controller.Controller.settle_sensor_subscriptions(owner, sensors)
    assert owner.state['frame'] == 1
    assert len(sleeps) == 300
    assert all(sensor['queue'].empty() for sensor in sensors)
