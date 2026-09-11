import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt,json
from matplotlib.collections import PolyCollection
from pathlib import Path
r=Path(__file__).parent;sets=[json.loads((r/'before-bays.json').read_text()),json.loads((r/'corrected-bays.json').read_text())];quads=json.loads((r/'road-strips.json').read_text());meters=json.loads((r/'before-annotations.json').read_text())['meters'];fig,axes=plt.subplots(3,2,figsize=(16,10))
for row,(bounds,label) in enumerate([((-36,95,5,36),'Central road'),((-35,35,57,70),'Inner south road'),((-30,51,122,149),'Outer south road')]):
 for col,bays in enumerate(sets):
  ax=axes[row,col];ax.add_collection(PolyCollection(quads,facecolor='#b9c7cc',edgecolor='none'));ax.add_collection(PolyCollection([b['polygon'] for b in bays],facecolor='#9766de30',edgecolor='#6633aa',linewidth=1));ax.scatter([m['x'] for m in meters],[m['y'] for m in meters],s=8,c='#267b97',zorder=3)
  for b in bays:
   if bounds[0]<b['x']<bounds[1] and bounds[2]<b['y']<bounds[3]:ax.text(b['x'],b['y'],b['id'],ha='center',va='center',fontsize=6)
  ax.set_xlim(bounds[:2]);ax.set_ylim(bounds[3],bounds[2]);ax.set_aspect('equal');ax.set_title(label+' — '+('before' if col==0 else 'corrected'));ax.set_xlabel('CARLA x (m)');ax.set_ylabel('CARLA y (m)');ax.grid(alpha=.15)
fig.suptitle('Town10 parking footprint audit\nGrey: continuous OpenDRIVE parking shoulder · Purple: estimated bay · Blue: authored parking meter',fontsize=12);fig.tight_layout(rect=[0,0,1,.95]);fig.savefig(r/'before-after.png',dpi=150)
