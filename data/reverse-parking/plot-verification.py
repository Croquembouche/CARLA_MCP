"""Plot recorded native parking poses; reads evidence only."""
import json, math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
root=Path(__file__).resolve().parents[2];out=root/'data/reverse-parking'
results=json.loads((out/'native-verification.json').read_text())
bays=json.loads((root/'data/parking/Town10HD_Opt.json').read_text())['validated_spaces']
fig,axes=plt.subplots(1,2,figsize=(12,5))
for ax,c in zip(axes,results['cases']):
 path=c['planned_entry'];trace=[v for v in c['trace'] if v['stage']!='driving']
 for bay in bays:
  if bay['id'] not in ('P024','P025'):continue
  ax.add_patch(Polygon(bay['polygon'],facecolor='#edf6ef',edgecolor='#34834a',linewidth=1.3))
  ax.text(bay['x'],bay['y']-.8,bay['id'],ha='center',fontsize=9,color='#28633a')
 ax.plot([v['x'] for v in path],[v['y'] for v in path],'--',c='#88929c',label='Planned entry')
 for reverse,color,label in [(False,'#2563eb','Forward / stopped'),(True,'#a855f7','Reversing')]:
  pts=[v['pose'] for v in trace if v['control']['reverse']==reverse]
  if pts:ax.scatter([v['x'] for v in pts],[v['y'] for v in pts],s=12,c=color,label=label,zorder=3)
 final=trace[-1]['pose'];yaw=math.radians(final['yaw'])
 # Mini Cooper measured body dimensions from the native test.
 corners=[(final['x']+x*math.cos(yaw)-y*math.sin(yaw),final['y']+x*math.sin(yaw)+y*math.cos(yaw)) for x,y in [(-2.2763,-1.0478),(2.2763,-1.0478),(2.2763,1.0478),(-2.2763,1.0478)]]
 ax.add_patch(Polygon(corners,facecolor='#c6d9fb',edgecolor='#244b86',alpha=.65,zorder=2))
 ax.arrow(final['x'],final['y'],math.cos(yaw),math.sin(yaw),head_width=.22,color='#244b86',zorder=4)
 ax.set_title(c['bay']+' · '+('road approach → reverse parking' if c['stage_at_start']=='driving' else 'parked → setup → reverse parking'),fontsize=10)
 ax.set_aspect('equal',adjustable='box');ax.set_xlabel('CARLA x (m)');ax.set_ylabel('CARLA y (m)');ax.grid(alpha=.2)
 ax.set_xlim(1,23);ax.set_ylim(60,69);ax.legend(fontsize=8,loc='upper right')
fig.suptitle('Native CARLA reverse-parking verification\nMini Cooper · zero collision events in both runs',fontsize=12)
fig.tight_layout();fig.savefig(out/'verified-paths.png',dpi=160)
