import json,httpx
from pathlib import Path
root=Path('/mnt/simulations/control-center');c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
s=c.get('/api/status').json();assert s['mode']=='live' and not s['recording'];cmd('pause')
for group,p in s['movement_programs'].items():
 phases=p['defaults']
 if group=='8':phases=[{'name':'Opposing through · permissive left','duration':15,'states':{'8':{'left':'Permissive','straight':'Protected'},'16':{'straight':'Protected'}}}]+phases
 if group=='18':phases=[{'name':'Protected through · permissive right','duration':15,'states':{'18':{'right':'Permissive'},'19':{'straight':'Protected'}}}]+phases
 cmd('movement-program',{'group_id':int(group),'operation':'enable','yellow_time':3,'all_red_time':2,'phases':phases})
for _ in range(160):
 cmd('step');s=c.get('/api/status').json()
 if all(p['stage']=='green' for p in s['movement_programs'].values()):break
else:raise AssertionError('A junction is still occupied during initial clearance')
cmd('pause');s=c.get('/api/status').json();(root/'data/movement-verification/final-state.json').write_text(json.dumps(s,indent=2));print('ALL_GROUPS_CONFIGURED',s['frame'],flush=True)
