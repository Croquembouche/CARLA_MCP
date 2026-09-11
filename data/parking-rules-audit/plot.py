import json,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.lines import Line2D
r=json.load(open('data/parking-rules-audit/report.json'));d=json.load(open('data/parking/Town10HD_Opt.json'));allowed=set(r['allowed_ids']);fig,axs=plt.subplots(3,1,figsize=(15,9))
for ax,(lo,hi,title) in zip(axs,[(5,40,'Central road'),(55,80,'Inner south road'),(120,150,'Outer south road')]):
 for zone in r['rules']['zones']:
  if zone['kind']=='crosswalk':ax.add_patch(Polygon(zone['polygon'],facecolor='#69788430',edgecolor='#697884',linewidth=.6))
 for bay in d['validated_spaces']:
  if not lo<bay['y']<hi:continue
  color='#29734c' if bay['id'] in allowed else '#b34b4b'
  ax.add_patch(Polygon(bay['polygon'],facecolor=color+'25',edgecolor=color,linewidth=1.3));ax.text(bay['x'],bay['y'],bay['id'],fontsize=8,ha='center',va='center')
 for f in r['features']:
  x,y=f['point']
  if not (-35<x<90 and lo<y<hi):continue
  if 'Hdrant' in f['id']:ax.plot(x,y,'r*',markersize=10)
  elif 'BusStop' in f['id'] and 'Glasses' not in f['id']:ax.plot(x,y,'bs',markersize=6)
  elif 'SM_Parking' in f['id']:ax.plot(x,y,'^',color='#946b12',markersize=7)
 ax.set_xlim(-35,90);ax.set_ylim(hi,lo);ax.grid(alpha=.15);ax.set_title(title);ax.set_ylabel('CARLA y (m)')
axs[-1].set_xlabel('CARLA x (m)')
fig.suptitle('Town10 parking restriction audit — 13 selectable, 28 withheld\nProvisional Delaware clearances + authored scene signs; remaining boundaries are estimates',fontsize=14)
fig.legend(handles=[Line2D([0],[0],color='#29734c',label='Selectable estimate'),Line2D([0],[0],color='#b34b4b',label='Restricted / unresolved'),Line2D([0],[0],color='r',marker='*',linestyle='',label='Hydrant'),Line2D([0],[0],color='b',marker='s',linestyle='',label='Bus stop'),Line2D([0],[0],color='#946b12',marker='^',linestyle='',label='Parking restriction sign')],loc='lower center',ncol=5)
fig.tight_layout(rect=[0,.045,1,.93]);fig.savefig('data/parking-rules-audit/restrictions.png',dpi=150)
