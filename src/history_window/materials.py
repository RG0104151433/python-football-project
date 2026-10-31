"""Same-version scientific figures; no inference or best-period guarantee."""
import io,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from src.data_contract import atomic_bytes,write_json


def build(table,figures,cfg,products,telemetry):
    figures.mkdir(parents=True,exist_ok=True)
    available={f.name for f in font_manager.fontManager.ttflist}
    font=next((f for f in ('Microsoft YaHei','SimHei','Noto Sans CJK SC') if f in available),'DejaVu Sans')
    plt.rcParams.update({'font.family':font,'axes.unicode_minus':False,'svg.hashsalt':'history-window-step4-v1'})
    names=['2y','4y','8y','12y','20y','cumulative']
    whole=[next(r for r in products['group_metrics.csv'] if r['group']=='all' and r['window']==w) for w in names]
    paths=[]
    def save(fig,name):
        for ext in ('png','svg'):
            b=io.BytesIO();fig.savefig(b,format=ext,dpi=170,bbox_inches='tight',metadata={'Date':None} if ext=='svg' else {})
            p=figures/(name+'.'+ext);atomic_bytes(p,b.getvalue());paths.append(p)
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.5));values=[r['primary_log_loss'] for r in whole]
    ax.plot(names,values,'o-',color='#2b6385');ax.axhline(values[-1],ls='--',color='#777777',lw=1,label='Cumulative reference')
    for i,y in enumerate(values):ax.annotate(f'{y:.5f}',(i,y),xytext=(0,8),textcoords='offset points',ha='center')
    ax.set(xlabel='Outcome-model training history',ylabel='Log loss (lower is better)',title='Fixed Q5 ratings; same 16,599 matches, 2000–2024')
    ax.legend();ax.grid(axis='y',alpha=.2);save(fig,'fixed_history_loss')
    fig,ax=plt.subplots(figsize=(10,4.7))
    for w in names:
        rr=[r for r in products['yearly_metrics.csv'] if r['window']==w]
        ax.plot([r['year'] for r in rr],[r['primary_log_loss'] for r in rr],label=w,lw=1.5)
    ax.set(xlabel='Forecast year',ylabel='Log loss',title='Annual forecasts use preceding years only')
    ax.legend(ncol=3);ax.grid(alpha=.2);save(fig,'annual_history_loss')
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True)
    decisions=products['selection_decisions.csv'];years=[r['year'] for r in decisions]
    axes[0].step(years,[names.index(r['selected_window']) for r in decisions],where='mid',color='#277d6b')
    axes[0].set(yticks=range(6),yticklabels=names,ylabel='Chosen history',title='Policy chosen before each year from earlier losses')
    for w in ('cumulative','20y'):
        rr=[r for r in products['yearly_metrics.csv'] if r['window']==w and r['year']>=2010]
        axes[1].plot(years,[r['primary_log_loss'] for r in rr],label=w)
    rr=[r for r in products['adaptive_metrics.csv'] if r['group'].startswith('year:')]
    axes[1].plot(years,[r['primary_log_loss'] for r in rr],label='Past-only selection',ls='--',color='#277d6b')
    axes[1].set(xlabel='Forecast year',ylabel='Log loss');axes[1].legend()
    for ax in axes:ax.grid(alpha=.2)
    save(fig,'adaptive_history_selection')
    display=dict(scope='retrospective point results; no new blind test or inference',
        whole_period=whole,adaptive_summary=products['adaptive_metrics.csv'][0],decisions=decisions,
        matplotlib=matplotlib.__version__,font=font,windows_fitted_each_year=6,
        job_seconds_by_window={w:sum(r['total_seconds'] for r in telemetry if r['window']==w) for w in names})
    write_json(table/'display_data.json',display)
    return paths
