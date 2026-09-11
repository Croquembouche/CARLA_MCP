import json,httpx
from pathlib import Path
root=Path('/mnt/simulations/control-center');data=root/'data';c=httpx.Client(base_url='http://localhost:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def get():return c.get('/api/status').json()
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
s=get();saved=s['movement_programs'];groups=sorted(saved,key=int);offsets={g:i for i,g in enumerate(groups)}
cmd('network-timing',{'mode':'coordinated','cycle_time':80,'offsets':offsets});epoch=get()['network_timing']['epoch'];starts={}
for i in range(220):
 cmd('step');s=get()
 for gid,p in s['movement_programs'].items():
  if p['stage']=='green' and gid not in starts:starts[gid]=p['since']
 if len(starts)==len(groups):break
assert len(starts)==len(groups),starts
for gid,start in starts.items():assert abs(start-epoch-offsets[gid])<.051,(gid,start,epoch)
print('COORDINATED_OFFSETS_VERIFIED',starts,flush=True)
cmd('network-timing',{'mode':'adaptive','min_green':.5,'max_green':1.5,'gap':.5,'distance':40})
previous={};durations=[]
for i in range(180):
 cmd('step');s=get()
 for gid,p in s['movement_programs'].items():
  old=previous.get(gid)
  if old and old['stage']=='green' and p['stage']=='yellow' and old['since']>=s['network_timing'].get('epoch',0):durations.append(p['since']-old['since'])
  previous[gid]={'stage':p['stage'],'since':p['since']}
assert s['network_timing']['detectors'];assert any(.49<=duration<=1.551 for duration in durations),durations
report={'passed':True,'epoch':epoch,'requested_offsets':offsets,'observed_starts':starts,'adaptive_green_durations':durations,'detectors':s['network_timing']['detectors']};(data/'network-live-report.json').write_text(json.dumps(report,indent=2));print('ADAPTIVE_TIMING_VERIFIED',durations,flush=True)
cmd('network-timing',{'mode':'independent'})
for gid,p in saved.items():cmd('movement-program',dict(group_id=int(gid),operation='update',**{k:p[k] for k in ('phases','yellow_time','all_red_time')}))
for _ in range(105):cmd('step')
print('ORIGINAL_INDEPENDENT_PLANS_RESTORED',flush=True)
