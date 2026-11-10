"""True Matplotlib mplot3d projections of unchanged history-window results."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
H=Path(__file__).resolve().parent
D=json.loads((H/'assets/review_data.json').read_text(encoding='utf-8'));ranked=sorted(D['windows'],key=lambda x:-x['loss']);out=H/'assets/history3d';out.mkdir(exist_ok=True)
xs={'20y':0,'12y':1,'all':2};ys={'12y':0,'all':1};worst=ranked[0]['loss'];heights=[1000*(worst-x['loss'])+.1 for x in ranked]
for step in range(6):
 for frame in range(10):
  fig=plt.figure(figsize=(8.5,5.3),facecolor='#f4f1e9');ax=fig.add_subplot(projection='3d',facecolor='#f4f1e9');ax.view_init(24,-48)
  for i,x in enumerate(ranked[:step+1]):
   a,b=x['label'].split(' / ');z=heights[i]*(frame/9 if i==step else 1);ax.bar3d(xs[a]-.22,ys[b]-.2,0,.44,.4,z,color='#ee943a' if i==step else '#196299',shade=True)
  ax.set_xticks([0,1,2],['20y','12y','All']);ax.set_yticks([0,1],['12y','All']);ax.set_xlabel('Rating history',labelpad=10);ax.set_ylabel('Outcome history',labelpad=10);ax.set_zlabel('Improvement + 0.1 (×0.001)',labelpad=9);ax.set_zlim(0,max(heights)*1.15);ax.set_xlim(-.5,2.5);ax.set_ylim(-.5,1.5);ax.tick_params(labelsize=10);fig.subplots_adjust(left=0,right=.87,bottom=.08,top=1)
  fig.savefig(out/f'frame{step*10+frame:03}.png',dpi=90);plt.close(fig)
print('Rendered 60 true 3D animation frames; same six observed log-loss values.')
