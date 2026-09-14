"""Scene weather changes in place during live capture; retired noise settings migrate."""
import copy
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from controller import Controller, WEATHER, validate_loadout
import carla


def owner():
    o=Controller.__new__(Controller)
    o.mode='live';o.running=True;o.recording=object()
    o.state={'frame':20,'weather':{k:getattr(carla.WeatherParameters(),k) for k in WEATHER}}
    current=carla.WeatherParameters()
    def weather():
        value=carla.WeatherParameters()
        for k in WEATHER:setattr(value,k,getattr(current,k))
        return value
    def apply(value):
        for k in WEATHER:setattr(current,k,getattr(value,k))
    o.world=SimpleNamespace(get_weather=weather,set_weather=Mock(side_effect=apply))
    def tick():
        o.state['frame']+=1;o.state['weather']={k:getattr(current,k) for k in WEATHER}
    o.tick=Mock(side_effect=tick);o.configure_sensors=Mock();o.require_edit=Mock(side_effect=AssertionError('must not require editing'))
    return o


def test_live_recording_weather_keeps_running_and_sensor_instances():
    o=owner();recording=o.recording
    result=o.command('weather',{'fog_density':100,'fog_distance':0,'precipitation':75})
    assert result['fog_density']==100 and result['fog_distance']==0 and result['precipitation']==75
    assert o.running and o.recording is recording and o.state['frame']==21
    o.configure_sensors.assert_not_called();o.require_edit.assert_not_called()
    assert o.state['weather_application']['stage']=='applied'


@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,'50',-1,101])
def test_invalid_weather_does_not_reach_world(value):
    o=owner()
    with pytest.raises(ValueError):o.command('weather',{'fog_density':value})
    o.world.set_weather.assert_not_called();o.tick.assert_not_called()


def test_replay_weather_still_protected():
    o=owner();o.mode='native-replay'
    with pytest.raises(ValueError,match='replay'):o.command('weather',{'fog_density':50})
    o.world.set_weather.assert_not_called()


def test_old_noise_loadout_migrates_without_changing_sensor_settings():
    value=[{'name':'roof','type':'sensor.lidar.ray_cast','mount':{'z':2.5},'attributes':{
        'weather_rain_density':'90','weather_fog_density':'100','weather_smoke_density':'80',
        'range':'80','channels':'32','physical_model':'true','physical_profile':'generic','output_format':'extended'}}]
    before=copy.deepcopy(value);new=validate_loadout(value)
    assert value==before and new[0]['mount']==before[0]['mount']
    assert not any(k.startswith('weather_') for k in new[0]['attributes'])
    for k in ('range','channels','physical_model','physical_profile','output_format'):
        assert new[0]['attributes'][k]==before[0]['attributes'][k]


def test_retired_noise_action_rejected_without_reconfiguration():
    o=owner()
    with pytest.raises(ValueError,match='removed; use scene weather'):o.command('lidar-weather',{'rain':50,'fog':100,'smoke':0})
    o.configure_sensors.assert_not_called()
