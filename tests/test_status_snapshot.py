import json,threading
from types import SimpleNamespace
import app


def test_status_serializes_mutating_progress_without_exposing_a_live_dictionary(monkeypatch):
    state={'actors':[{'id':i} for i in range(200)],'managed':{}}
    monkeypatch.setattr(app,'engine',SimpleNamespace(state=state))
    stop=threading.Event()
    def mutate():
        while not stop.is_set():
            state['progress']={'stage':'loading'}
            state.pop('progress',None)
    worker=threading.Thread(target=mutate);worker.start()
    try:
        for _ in range(50):
            response=app.status()
            assert len(json.loads(response.body)['actors'])==200
            assert response.media_type=='application/json'
    finally:stop.set();worker.join()
