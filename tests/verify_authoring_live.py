import json,time,httpx
from pathlib import Path
root=Path('/mnt/simulations/control-center');data=root/'data';c=httpx.Client(base_url='http://localhost:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def get(path='/api/status'):
 r=c.get(path);r.raise_for_status();return r.json()
def cmd(action,p={}):
 r=c.post('/api/command/'+action,json=p);r.raise_for_status();return r.json()
s=get();original=get('/api/configuration');(data/'before-authoring-live-test.json').write_text(json.dumps(original,indent=2));catalog=get('/api/catalog');model=catalog['vehicles'][1]['id']
flow=s['authoring']['config']['flows'][0];flow['remove_arrived']=False
config={'flows':[flow],'events':[{'id':'timeline_car','time':.1,'action':'spawn_vehicle','model':model,'spawn':60,'destination':10},{'id':'timeline_walker','time':.2,'action':'spawn_pedestrian','model':catalog['walkers'][0],'spawn':0,'destination':1},{'id':'clear_weather','time':.5,'action':'weather','preset':'clear'},{'id':'reroute_car','time':1,'action':'destination','actor':'timeline_car','destination':0},{'id':'hold_signal','time':2,'action':'signal_hold','group_id':15},{'id':'select_phase','time':3,'action':'signal_phase','group_id':18,'index':1},{'id':'resume_signal','time':4,'action':'signal_resume','group_id':15},{'id':'restore_rain','time':5,'action':'weather','preset':'rain'}]}
cmd('authoring-configure',{'config':config});cmd('authoring-start');before=get()['authoring']['elapsed'];time.sleep(.3);assert get()['authoring']['elapsed']==before
record=cmd('record-start',{'rosbag':True});samples=[]
for i in range(240):
 cmd('step');s=get();samples.append(s)
 if i==39:cmd('record-stop')
 if i%60==59:print('SCHEDULE_STEP',i+1,s['authoring']['elapsed'],flush=True)
s=get();log=s['authoring']['log'];failures=[e for e in log if e['status'] in ('failed','skipped')];assert not failures,failures
assert all(e['status']=='executed' for e in s['authoring']['events']);assert s['authoring']['flows'][0]['spawned']==2,s['authoring']
assert any(x['weather']['cloudiness']==5 for x in samples);assert s['weather']['precipitation']==70
walk=s['authoring']['actors']['timeline_walker'];positions=[next((a['pose'] for a in x['actors'] if a['id']==walk),None) for x in samples];positions=[p for p in positions if p];distance=((positions[-1]['x']-positions[0]['x'])**2+(positions[-1]['y']-positions[0]['y'])**2)**.5
assert distance>.5,distance
created=set(s['managed'])-set(original_actor_ids:=str(a['id']) for a in original['actors'])
report={'passed':True,'departures':2,'executed_events':len(s['authoring']['events']),'walker_distance':distance,'recording':record,'pause_clock_verified':True,'log':log}
(data/'authoring-live-report.json').write_text(json.dumps(report,indent=2));print('SCHEDULE_VERIFIED',json.dumps({k:v for k,v in report.items() if k not in ('recording','log')}),flush=True)
cmd('authoring-stop')
for aid in created:cmd('delete',{'id':int(aid)})
cmd('authoring-configure',{'config':{'flows':[],'events':[]}})
cmd('weather',original['weather'])
for gid in (15,18):
 p=original['movement_programs'][str(gid)];cmd('movement-program',dict(group_id=gid,operation='update',**{k:p[k] for k in ('phases','yellow_time','all_red_time')}))
for i in range(105):cmd('step')
print('TEST_ACTORS_REMOVED_AND_ORIGINAL_PLANS_RESTORED',flush=True)
