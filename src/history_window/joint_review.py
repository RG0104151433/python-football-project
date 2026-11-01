"""Q6 step6 closeout: fixed predictions, component costs, one arithmetic review."""
from collections import defaultdict
from pathlib import Path
import io,math,zipfile
import numpy as np
from src.data_contract import atomic_bytes,csv_bytes,file_hash,fingerprint,write_json
from src.strength.io import ROOT,environment,read_rows
from .contracts import read_json,id_digest
from .evaluation import summarize
from .protocol import log_losses


def paired(a,b,epsilon):
    a=sorted(a,key=lambda r:r['match_id']);b=sorted(b,key=lambda r:r['match_id'])
    if [(r['match_id'],r['date'],int(r['home_win'])) for r in a]!=[(r['match_id'],r['date'],int(r['home_win'])) for r in b]:
        raise ValueError('PAIRED_FACTS_DIFFER')
    y=[int(r['home_win']) for r in a]
    d=log_losses([float(r['probability']) for r in a],y,epsilon)-log_losses([float(r['probability']) for r in b],y,epsilon)
    return dict(mean_loss_minus_baseline=float(d.mean()),better_matches=int(np.sum(d<0)),worse_matches=int(np.sum(d>0)),equal_matches=int(np.sum(d==0)))


def comparisons(predictions,cfg):
    by=defaultdict(list)
    for r in predictions:by[r['combination_id']].append(r)
    if len(by)!=6 or any(len(r)!=16599 or len({x['match_id'] for x in r})!=16599 for r in by.values()):raise ValueError('SIX_COMMON_SAMPLES_REQUIRED')
    base=by[cfg['baseline']];metrics=[];yearly=[];groups=[]
    for combo,rr in by.items():
        for scope,(lo,hi) in cfg['scopes'].items():
            aa=[r for r in rr if lo<=int(r['year'])<=hi];bb=[r for r in base if lo<=int(r['year'])<=hi]
            metrics.append(dict(combination_id=combo,scope=scope,**summarize(aa,cfg['probability_clip']),**paired(aa,bb,cfg['probability_clip'])))
        for year in range(2000,2025):
            aa=[r for r in rr if int(r['year'])==year];bb=[r for r in base if int(r['year'])==year]
            yearly.append(dict(combination_id=combo,year=year,**summarize(aa,cfg['probability_clip']),**paired(aa,bb,cfg['probability_clip'])))
        for scope in ('all','evaluation'):
            lo,hi=cfg['scopes'][scope]
            for kind in sorted({r['tournament_group'] for r in rr}):
                aa=[r for r in rr if lo<=int(r['year'])<=hi and r['tournament_group']==kind]
                bb=[r for r in base if lo<=int(r['year'])<=hi and r['tournament_group']==kind]
                groups.append(dict(combination_id=combo,scope=scope,tournament_group=kind,**summarize(aa,cfg['probability_clip']),**paired(aa,bb,cfg['probability_clip'])))
    return by,metrics,yearly,groups


def build_figures(folder,metrics,costs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'svg.hashsalt':'q6-joint-review-v1','axes.unicode_minus':False})
    names=[r['combination_id'] for r in metrics if r['scope']=='all'];labels=['20 / 12','20 / all','12 / 12','12 / all','all / 12','all / all'];out=[]
    def save(fig,name):
        for ext in ('png','svg'):
            buf=io.BytesIO();fig.savefig(buf,format=ext,dpi=170,bbox_inches='tight',metadata={'Date':None} if ext=='svg' else {})
            path=folder/(name+'.'+ext);atomic_bytes(path,buf.getvalue());out.append(path)
        plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.7))
    for ax,scope in zip(axes,('all','evaluation')):
        values=[next(r['primary_log_loss'] for r in metrics if r['scope']==scope and r['combination_id']==n) for n in names]
        ax.plot(labels,values,'o-',color='#286389');ax.axhline(values[-1],color='gray',ls='--',lw=1)
        for i,v in enumerate(values):ax.annotate(f'{v:.5f}',(i,v),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
        ax.set_title('2000–2024 (16,599 matches)' if scope=='all' else '2010–2024 (9,727 matches)');ax.set_xlabel('Rating memory / outcome-training years');ax.grid(axis='y',alpha=.2);ax.margins(y=.2)
    axes[0].set_ylabel('Home-win probability log loss (lower is better)');save(fig,'joint_prediction_comparison')
    fig,axes=plt.subplots(1,2,figsize=(11,4.7))
    rating_names=['cumulative_1950','annual_reset_12y','annual_reset_20y']
    vv=[next(r['rating_replayed_rows'] for r in costs if r['rating_policy']==n) for n in rating_names]
    axes[0].bar(['Cumulative','Annual12','Annual20'],vv,color='#427c91');axes[0].set(ylabel='Replayed game rows (not unique matches)',title='Scoring workload: one pass vs annual rebuilding')
    controlled=[next(r for r in costs if r['rating_policy']=='cumulative_1950' and r['outcome_window']==w) for w in ('12y','cumulative')]
    vv=[r['outcome_job_seconds'] for r in controlled];axes[1].bar(['12 years','Cumulative'],vv,color='#b27b43')
    for i,v in enumerate(vv):axes[1].text(i,v,f'{v:.1f}s',ha='center',va='bottom')
    axes[1].set(ylabel='25 annual fit/design/prediction tasks, seconds',title='Same R10 batch, cumulative ratings held fixed');axes[1].margins(y=.15)
    save(fig,'joint_cost_components');return out


def run(config_path='config/history_window_joint_review.json'):
    cfg=read_json(ROOT/config_path)
    if cfg['schema_version']!='history-window-joint-review-v1' or cfg['probability_clip']!=1e-6:raise ValueError('REVIEW_PROTOCOL_MISMATCH')
    source=ROOT/'outputs/logs/history_window'/cfg['source_run'];man=read_json(source/'manifest.json');source_cfg=read_json(source/'protocol.json')
    inputs={config_path:file_hash(ROOT/config_path),(source/'manifest.json').relative_to(ROOT).as_posix():file_hash(source/'manifest.json')}
    def take(path,expected):
        h=file_hash(ROOT/path)
        if h!=expected:raise ValueError('REVIEW_INPUT_CHANGED:'+path)
        inputs[path]=h
    table_source='outputs/tables/history_window/'+cfg['source_run']
    for p in [table_source+'/'+n for n in ('combination_plan.csv','predictions.csv','training_boundaries.csv')]+[(source/n).relative_to(ROOT).as_posix() for n in ('protocol.json','telemetry.json','generation_checks.json','new_models.json')]:take(p,man['outputs'][p])
    if not read_json(source/'generation_checks.json')['passed']:raise ValueError('GENERATION_NOT_PASSED')
    parents={}
    for key in ('rating_run','outcome_run'):
        folder=ROOT/'outputs/logs/history_window'/source_cfg[key];path=(folder/'manifest.json').relative_to(ROOT).as_posix()
        take(path,man['identity']['inputs'][path]);pm=read_json(ROOT/path);parents[key]=(folder,pm)
    wanted={'rating_run':['real_features.json','real_development.json','rating_outcome.json'],'outcome_run':['telemetry.json']}
    for key,names in wanted.items():
        folder,pm=parents[key]
        for n in names:
            p=(folder/n).relative_to(ROOT).as_posix();take(p,pm['outputs'][p])
    code=[ROOT/'src/history_window/joint_review.py',ROOT/'src/history_window/evaluation.py',ROOT/'src/history_window/protocol.py',ROOT/'src/history_window/contracts.py',ROOT/'src/data_contract.py',ROOT/'src/strength/io.py',ROOT/'scripts/analyze_history_window.py',ROOT/'tests/test_history_window_joint_review.py']
    identity=dict(protocol=cfg,inputs=inputs,code={p.relative_to(ROOT).as_posix():file_hash(p) for p in code},environment=environment())
    rid='joint-review-'+fingerprint(identity)[:20];log=ROOT/'outputs/logs/history_window'/rid;table=ROOT/'outputs/tables/history_window'/rid;figure=ROOT/'outputs/figures/history_window'/rid
    if (log/'manifest.json').exists():
        for p,h in read_json(log/'manifest.json')['outputs'].items():
            if file_hash(ROOT/p)!=h:raise ValueError('REVIEW_OUTPUT_CHANGED')
        print('JOINT_REVIEW_VERIFIED_COMPLETE',rid,flush=True);return log,table
    for p in (log,table,figure):p.mkdir(parents=True,exist_ok=True)
    write_json(log/'started.json',dict(identity=identity,no_new_fits=True,no_new_simulations=True));write_json(log/'protocol.json',cfg)
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
        for p in code+[ROOT/config_path]:z.writestr(zipfile.ZipInfo(p.relative_to(ROOT).as_posix(),(1980,1,1,0,0,0)),p.read_bytes())
    atomic_bytes(log/'source_snapshot.zip',buf.getvalue())
    predictions=read_rows(ROOT/table_source/'predictions.csv');by,metrics,yearly,groups=comparisons(predictions,cfg)
    boundaries=read_rows(ROOT/table_source/'training_boundaries.csv');plan=read_rows(ROOT/table_source/'combination_plan.csv');costs=[]
    rt=read_json(parents['rating_run'][0]/'real_features.json')['telemetry'];cum=read_json(parents['rating_run'][0]/'real_development.json')['cumulative_cost']
    old=read_json(parents['outcome_run'][0]/'telemetry.json')['records'];rating=read_json(parents['rating_run'][0]/'rating_outcome.json')['telemetry'];new=read_json(source/'telemetry.json')['records']
    for item in plan:
        name=item['rating_policy'];combo=item['combination_id'];window=item['outcome_window'];bb=[r for r in boundaries if r['combination_id']==combo]
        ss=[cum] if name=='cumulative_1950' else [r for r in rt if r['years']==int(name.split('_')[-1][:-1])]
        if len(bb)!=25 or len(ss)!=(1 if name=='cumulative_1950' else 45):raise ValueError('INCOMPLETE_COST_COMPONENT')
        if name=='cumulative_1950':tt=[r for r in old if r['window']==window];producer=source_cfg['outcome_run'];kind='R10 controlled batch';seconds=sum(r['total_seconds'] for r in tt)
        elif window=='12y':tt=[r for r in new if r['combination_id']==combo];producer=cfg['source_run'];kind='R04 joint generation';seconds=sum(r['total_seconds'] for r in tt)
        else:tt=[r for r in rating if r['policy_name']==name and not r['reused_r10_model']];producer=source_cfg['rating_run'];kind='R13 downstream generation';seconds=sum(r['seconds'] for r in tt)
        if len(tt)!=25:raise ValueError('MISSING_PRODUCER_FIT_COST')
        costs.append(dict(combination_id=combo,rating_policy=name,outcome_window=window,rating_replayed_rows=sum(r['history_rows'] for r in ss),
            rating_producer_job_seconds=sum(r['seconds'] for r in ss),rating_cost_scope='single-process one pass' if name=='cumulative_1950' else 'sum of job elapsed; mixed serial development and at most3 parallel workers',
            outcome_training_rows=sum(int(r['rows']) for r in bb),outcome_job_seconds=seconds,outcome_producer_run=producer,outcome_cost_scope=kind,
            prediction_seconds=sum(r['predict_seconds'] for r in tt) if all('predict_seconds' in r for r in tt) else None,
            process_peak_rss_mib=max(r.get('sampled_peak_rss_mib',r.get('sampled_peak_rss_mb',0)) for r in tt) if all('sampled_peak_rss_mib' in r or 'sampled_peak_rss_mb' in r for r in tt) else None,
            total_pipeline_seconds=None,cross_batch_times_not_standardized=True,cached_cost_not_zero=True))
    controlled={r['outcome_window']:r for r in costs if r['rating_policy']=='cumulative_1950'}
    saving=1-controlled['12y']['outcome_job_seconds']/controlled['cumulative']['outcome_job_seconds']
    # One independent arithmetic / sample / date check. No refitting or simulation.
    failures=[]
    def check(name,ok):
        if not ok:failures.append(name)
    for combo,rr in by.items():
        paired(rr,by[cfg['baseline']],cfg['probability_clip'])
        check('annual_cutoffs:'+combo,all(r['training_max']<r['year']+'-01-01' and (r['rating_cutoff']=='initial_prior' or r['rating_cutoff']<r['date']) for r in rr))
    for r in metrics:
        lo,hi=cfg['scopes'][r['scope']];rr=[x for x in by[r['combination_id']] if lo<=int(x['year'])<=hi]
        loss=sum(-int(x['home_win'])*math.log(min(1-1e-6,max(1e-6,float(x['probability']))))-(1-int(x['home_win']))*math.log1p(-min(1-1e-6,max(1e-6,float(x['probability'])))) for x in rr)/len(rr)
        check('probability_loss:'+r['combination_id']+r['scope'],abs(loss-r['primary_log_loss'])<1e-10)
    for r in boundaries:
        left='1980-01-01' if r['outcome_window']=='cumulative' else f"{int(r['year'])-12}-01-01"
        check('boundary:'+r['combination_id']+r['year'],r['left_inclusive']==left and r['right_exclusive']==r['year']+'-01-01' and r['actual_min']>=left and r['actual_max']<r['right_exclusive'] and r['same_year_training_rows']=='0')
    if failures:write_json(log/'failure.json',dict(failures=failures));raise ValueError('REVIEW_CHECK_FAILED:'+str(failures[:3]))
    for name,rr in [('combination_metrics.csv',metrics),('yearly_metrics.csv',yearly),('tournament_metrics.csv',groups),('cost_components.csv',costs)]:atomic_bytes(table/name,csv_bytes(list(rr[0]),rr))
    evaluation=[r for r in metrics if r['scope']=='evaluation'];whole=[r for r in metrics if r['scope']=='all'];base=next(r for r in evaluation if r['combination_id']==cfg['baseline'])
    short=next(r for r in evaluation if r['combination_id']=='cumulative_1950__outcome_12y')
    conclusion=dict(default_retained=cfg['baseline'],main_evaluation_point_winner=min(evaluation,key=lambda r:r['primary_log_loss'])['combination_id'],full_period_point_winner=min(whole,key=lambda r:r['primary_log_loss'])['combination_id'],
        controlled_outcome_compute_saving_fraction=saving,controlled_short_outcome_evaluation_loss_increase=short['primary_log_loss']-base['primary_log_loss'],controlled_short_outcome_evaluation_relative_loss_increase=short['primary_log_loss']/base['primary_log_loss']-1,
        scope='historical point comparison; no formal equivalence/noninferiority or real-world coverage',
        recommendation='retain original cumulative baseline; no evidence here to switch to annual-reset joint variants',
        budget_alternative='cumulative rating with12year outcome history saves measured coefficient computation in R10 but worsens evaluation point loss; not adopted without budget/tolerance and reliability assessment',
        cost_limits='component times only; no end-to-end standardized frontier, unique cost optimum or universal66percent saving',
        sharing='same rating features shared by two combinations; do not sum six cost rows as actual new experiment cost',
        independent_repeats=False,new_blind_test=False,formal_inference=False,next_step='question6 internal step7 reliability and sensitivity; keep all six paired forecasts and frozen selection history')
    write_json(log/'conclusions.json',conclusion);figure_paths=build_figures(figure,metrics,costs)
    write_json(table/'display_data.json',dict(source_prediction_run=cfg['source_run'],metrics=metrics,costs=costs,conclusion=conclusion,figures=[p.relative_to(ROOT).as_posix() for p in figure_paths],no_formal_intervals=True))
    write_json(log/'review.json',dict(passed=True,scope='step6 four route steps completed, numerical/descriptive only',combinations=6,matches=16599,prediction_rows=99594,annual_boundary_rows=len(boundaries),metric_rows=len(metrics),yearly_rows=len(yearly),tournament_rows=len(groups),new_fits=0,rating_replays=0,simulations=0,checks='source hashes, paired labels/IDs, annual boundaries, independent basic loss arithmetic',human_review=False,formal_inference=False))
    outputs={p.relative_to(ROOT).as_posix():file_hash(p) for folder in (log,table,figure) for p in folder.iterdir() if p.is_file() and p.name not in ('manifest.json','failure.json')}
    write_json(log/'manifest.json',dict(identity=identity,outputs=outputs))
    write_json(log/'adoption.json',dict(run_id=rid,manifest_sha256=file_hash(log/'manifest.json'),review_sha256=file_hash(log/'review.json'),scope='step6 descriptive comparison/closeout only',question6_fully_closed=False,formal_inference=False))
    pointer=dict(run_id=rid,source_prediction_run=cfg['source_run'],log_directory=log.relative_to(ROOT).as_posix(),table_directory=table.relative_to(ROOT).as_posix(),figure_directory=figure.relative_to(ROOT).as_posix(),steps_completed=[1,2,3,4],formal_inference=False)
    write_json(ROOT/'outputs/logs/history_window/joint_review_pointer.json',pointer)
    original=ROOT/'outputs/logs/history_window/joint_pointer.json';ptr=read_json(original)
    if ptr['run_id']==cfg['source_run']:
        ptr.update(steps_completed=[1,2,3,4],comparison_pending=False,final_review_pending=False,review_run_id=rid,review_log_directory=pointer['log_directory']);write_json(original,ptr)
    print('JOINT_REVIEW_COMPLETE',rid,conclusion,flush=True);return log,table
