import sys,queue,threading
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from sensor_delivery import collect_frame


def sample(frame=7,timestamp=.7):return SimpleNamespace(frame=frame,timestamp=timestamp)
def sensor():return {'queue':queue.Queue(maxsize=8),'overflow':False}


def test_arrival_order_progresses_without_waiting_for_first_sensor():
    sensors={1:sensor(),2:sensor()};notification=threading.Event();stop=threading.Event();received=[]
    sensors[2]['queue'].put(sample(6,.6));sensors[2]['queue'].put(sample())
    def on_sample(sid,s,data):
        received.append(sid)
        if sid==2:
            # The late sensor is not released until the early one is consumed.
            # A fixed sensor-order wait would time out instead of progressing.
            sensors[1]['queue'].put(sample());notification.set()
    collect_frame(sensors,7,.7,notification,stop,lambda:None,on_sample,lambda *_:None,timeout=.1)
    assert received==[2,1]


@pytest.mark.parametrize('mode',['future','timestamp','overflow','cancel','fault','missing'])
def test_delivery_errors_never_accept_incomplete_frame(mode):
    s=sensor();stop=threading.Event();received=[]
    if mode=='future':s['queue'].put(sample(8,.8))
    if mode=='timestamp':s['queue'].put(sample(7,.8))
    if mode=='overflow':s['overflow']=True
    if mode=='cancel':stop.set()
    with pytest.raises(RuntimeError):
        collect_frame({1:s},7,.7,threading.Event(),stop,lambda:'worker failed' if mode=='fault' else None,
            lambda *args:received.append(args),lambda *_:None,timeout=.01)
    assert not received
