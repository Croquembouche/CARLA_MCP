import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,carla,pytest
from unittest.mock import Mock
from controller import Controller

def owner(running=False):
 c=Controller.__new__(Controller);c.running=running;c.recording=None;c.mode='live';c.world=Mock()
 c.state={'frame':100,'weather':{}};c.world.get_weather.return_value=carla.WeatherParameters()
 def tick():
  c.state['frame']+=1
  w=c.world.set_weather.call_args.args[0]
  c.state['weather']={'precipitation':w.precipitation,'sun_altitude_angle':w.sun_altitude_angle}
 c.tick=Mock(side_effect=tick)
 return c

@pytest.mark.parametrize('running',[False,True])
def test_weather_applies_at_a_complete_frame_without_changing_run_state(running):
 c=owner(running)
 result=c.command('weather',{'precipitation':70,'sun_altitude_angle':35})
 assert result=={'precipitation':70,'sun_altitude_angle':35}
 assert c.running is running
 assert c.state['weather_application']['stage']=='applied'
 assert c.state['weather_application']['frame']==101
 c.tick.assert_called_once()

def test_renderer_delivery_failure_does_not_report_weather_success():
 c=owner(True);c.tick.side_effect=RuntimeError('worker disconnected')
 with pytest.raises(RuntimeError,match='worker disconnected'):c.command('weather',{'precipitation':0})
 assert c.state['weather_application']=={'stage':'failed','detail':'worker disconnected'}

@pytest.mark.parametrize('payload',[{'precipitation':101},{'sun_altitude_angle':-91},{'unknown':1}])
def test_invalid_weather_is_not_sent_to_the_world(payload):
 c=owner(True)
 with pytest.raises(ValueError):c.command('weather',payload)
 c.world.set_weather.assert_not_called()

@pytest.mark.parametrize('recording,mode',[(True,'live'),(None,'native-replay')])
def test_recording_and_replay_keep_weather_edit_guard(recording,mode):
 c=owner(True);c.recording=recording;c.mode=mode
 with pytest.raises(ValueError,match='Stop recording or replay'):c.command('weather',{'precipitation':0})
 c.world.set_weather.assert_not_called()
