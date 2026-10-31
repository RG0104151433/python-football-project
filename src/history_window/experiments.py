"""Q6 step5 phases: exact state computation, independent truth, fixed controls."""
from collections import defaultdict,Counter
from datetime import date
from itertools import combinations
from pathlib import Path
import math,time
from datetime import datetime,timezone
import numpy as np
from threadpoolctl import threadpool_limits
from src.data_contract import atomic_bytes,csv_bytes,file_hash,fingerprint,write_json
from src.strength.io import ROOT,read_rows
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength_joint.design import Design
from src.strength_joint.model import predict
from src.strength_predictive_validation import fit_past
from .contracts import read_json
from .evaluation import summarize
from .protocol import log_losses,anniversary
from .replay import strict_replay
from .ratings import create_run,Guard,numerical_cache,annual_job,segment,adapt_facts,full_forecast,features,TASK_REQUESTS
from .simulation_long import generate,extend,TEAMS


def put_table(folder,name,rows):
    if not rows:raise ValueError('EMPTY_REQUIRED_TABLE:'+name)
    atomic_bytes(folder/name,csv_bytes(list(rows[0]),rows))


def policy_id(ctx,name):return name+'-'+ctx['rid'].split('-')[-1][:12]


def real_job(ctx,y,w,guard):
    return annual_job(ctx['games'],{g[k] for g in ctx['games'] for k in ('home','away')},ctx['params'],ctx['num'],
        y,w,ctx['log']/'jobs/real',ctx['cfg'],guard,{r['match_id'] for r in ctx['facts']})


def development(ctx):
    guard=Guard(ctx['cfg'],'real_development');timings=[]
    # One-pass cumulative replay supplies a same-machine cost reference and a
    # full numerical cross-check, not a new rating method or repeated annual fit.
    print('RATING_DEVELOPMENT cumulative_reference',flush=True)
    rr,_,_,tt=segment(ctx['games'],{g[k] for g in ctx['games'] for k in ('home','away')},ctx['params'],ctx['num'],
        '1950-01-01','2025-01-01','1980-01-01','cumulative_1950',None,ctx['log']/'jobs/cumulative_reference',
        ctx['cfg'],guard,{r['match_id'] for r in ctx['facts']})
    old={r['match_id']:r for r in read_rows(ROOT/ctx['cfg']['raw_score']/'prematch_features.csv')}
    maximum=max(abs(float(r[k])-float(old[r['match_id']][k])) for r in rr for k in ('difference','difference_variance','p_home','p_draw','p_away'))
    if maximum>2e-6:raise ValueError('CUMULATIVE_REFERENCE_MISMATCH:'+str(maximum))
    for y in ctx['cfg']['development_years']:
        for w in ctx['cfg']['windows'][:-1]:
            print('RATING_DEVELOPMENT',y,w,flush=True);_,_,_,t=real_job(ctx,y,w,guard);timings.append(dict(year=y,**t))
    # Conservative rate from the slowest development calendar for each W.
    grouped=defaultdict(list)
    for g in ctx['games']:grouped[g['date']].append(g)
    all_dates=sorted(grouped);estimate=0
    for w in ctx['cfg']['windows'][:-1]:
        rate=max(t['seconds']/max(1,t['history_dates']) for t in timings if t['years']==w)
        dates=sum(sum(f'{y-w}-01-01'<=d<f'{y+1}-01-01' for d in all_dates) for y in range(1980,2025))
        estimate+=1.5*rate*dates
    report=dict(passed=estimate<=ctx['cfg']['phase_seconds']['real_annual_features'],
        cumulative_max_reference_difference=maximum,cumulative_cost=tt,development_jobs=timings,
        conservative_full_seconds_estimate=estimate,estimate_is_not_runtime_guarantee=True,
        basis='1.5 times maximum measured date cost per window; all45years',thresholds_relaxed=False)
    write_json(ctx['log']/'real_development.json',report)
    if not report['passed']:raise RuntimeError('REAL_COST_ADMISSION_NOT_PASSED')
    return report


def baseline_features(ctx):
    # Keep exact adopted joint-feature values, not a differently rounded replay.
    raw={r['match_id']:r for r in read_rows(ROOT/ctx['cfg']['raw_score']/'prematch_features.csv')};out=[]
    for f in ctx['facts']:
        r=raw[f['match_id']]
        q={k:r[k] for k in ('match_id','date','home','away','prediction_cutoff')}
        for k in ('home_mean','away_mean','home_term','home_term_variance','p_home','p_draw','p_away'):q[k]=float(r[k])
        for k in ('home_variance','away_variance','home_away_covariance','home_jump_intensity','away_jump_intensity','jump_scale_sd'):q[k]=float(f[k])
        q.update(difference=float(f['strength_difference']),difference_variance=float(f['strength_difference_variance']),
            difference_base_variance=float(f['strength_difference_base_variance']),home_history=int(f['home_history']),away_history=int(f['away_history']),
            cold_start=f['cold_start']=='true',previously_disconnected=f['previously_disconnected']=='true',policy_name='cumulative_1950',
            nominal_years=None,window_left='1950-01-01',allowed_history_end_exclusive=f['date'],
            allowed_history_years=(date.fromisoformat(f['date'])-date(1950,1,1)).days/365.2425)
        out.append(q)
    return out


def publish_policy(ctx,name,rows):
    pid=policy_id(ctx,name);folder=ROOT/'data/processed/history_window'/pid
    rows=[dict(r,policy_id=pid) for r in sorted(rows,key=lambda r:(r['date'],r['match_id']))]
    adapted=adapt_facts(ctx['facts'],rows,pid)
    if len(rows)!=24917:raise ValueError('INCOMPLETE_RATING_POLICY')
    folder.mkdir(parents=True,exist_ok=True)
    for filename,rr in [('prematch_features.csv',rows),('analysis_matches.csv',adapted)]:
        content=csv_bytes(list(rr[0]),rr)
        if (folder/filename).exists() and (folder/filename).read_bytes()!=content:raise ValueError('POLICY_OUTPUT_COLLISION')
        atomic_bytes(folder/filename,content)
    write_json(folder/'manifest.json',dict(policy_id=pid,policy_name=name,source_run=ctx['rid'],
        inputs=ctx['inputs'],rows=len(rows),strict_w_year=False if name.startswith('annual') else None,
        outputs={n:file_hash(folder/n) for n in ('prematch_features.csv','analysis_matches.csv')}))
    return folder,rows,adapted


def real_features(ctx):
    if not (ctx['log']/'real_development.json').exists():development(ctx)
    if not read_json(ctx['log']/'real_development.json')['passed']:raise ValueError('REAL_DEVELOPMENT_REQUIRED')
    guard=Guard(ctx['cfg'],'real_annual_features');policies={};records=[]
    for w in ctx['cfg']['windows'][:-1]:
        rows=[]
        for y in range(1980,2025):
            print('RATING_YEAR',w,y,flush=True);rr,_,_,t=real_job(ctx,y,w,guard);rows+=rr;records.append(dict(year=y,**t))
        name=f'annual_reset_{w}y';folder,rr,adapted=publish_policy(ctx,name,rows);policies[name]=folder.relative_to(ROOT).as_posix()
    folder,_,_=publish_policy(ctx,'cumulative_1950',baseline_features(ctx));policies['cumulative_1950']=folder.relative_to(ROOT).as_posix()
    write_json(ctx['log']/'real_features.json',dict(completed=True,policies=policies,feature_rows=149502,annual_jobs=225,
        telemetry=records,annual_job_seconds=sum(t['seconds'] for t in records),
        source_cumulative_reused=True,annual_is_not_strict_W_year=True))
    return policies


def probes(ctx):
    guard=Guard(ctx['cfg'],'strict_probes');results=[];reset=[]
    facts_byday=defaultdict(list)
    for r in ctx['facts']:facts_byday[r['date']].append(r)
    dates=[]
    for y in ctx['cfg']['development_years']:
        for quarter in range(4):dates.append(min(d for d in facts_byday if int(d[:4])==y and (int(d[5:7])-1)//3==quarter))
    for day in dates:
        targets=[g for g in ctx['games'] if g['date']==day]
        for w in ctx['cfg']['windows'][:-1]:
            job=ctx['log']/'jobs/strict'/f'{day}-{w}y';print('STRICT_PROBE',day,w,flush=True)
            if (job/'result.json').exists():payload=read_json(job/'result.json')
            else:
                start=time.perf_counter();guard.check(start)
                rr,ledger,_=strict_replay(ctx['games'],targets,day,w,ctx['params'],ctx['num'],budget_seconds=ctx['cfg']['max_job_seconds'])
                ar,_,_,_=real_job(ctx,int(day[:4]),w,guard);lookup={r['match_id']:r for r in ar}
                pp=[]
                for r in rr:
                    if r['match_id'] not in lookup:continue
                    a=lookup[r['match_id']]
                    pp.append(dict(date=day,window=w,match_id=r['match_id'],strict_difference=r['difference'],annual_difference=a['difference'],
                        strict_variance=r['difference_variance'],annual_variance=a['difference_variance'],
                        strict_p_home=r['p_home'],annual_p_home=a['p_home'],strict_home_term=r['home_term'],annual_home_term=a['home_term'],
                        strict_left=ledger['left_inclusive'],annual_left=a['window_left'],
                        scope='native rating diagnostic, not complete downstream policy evaluation'))
                payload=dict(rows=pp,ledger=ledger,seconds=time.perf_counter()-start);write_json(job/'result.json',payload)
            results+=payload['rows']
    # Same-date diagnostic at the first research day of each available year.
    for w in ctx['cfg']['windows'][:-1]:
        for y in range(1981,2025):
            old=ctx['log']/f'jobs/real/{y-1}-{w}y/final_state.json'
            if not old.exists():continue
            engine=CollapsedJumpFilter.restore(read_json(old));day=min(d for d in facts_byday if int(d[:4])==y)
            grouped=defaultdict(list)
            for g in ctx['games']:
                if f'{y}-01-01'<=g['date']<day:grouped[g['date']].append(g)
            for d,batch in sorted(grouped.items()):engine.day(d,batch)
            targets=[g for g in ctx['games'] if g['date']==day];rr=full_forecast(engine,day,targets)
            fresh=read_json(ctx['log']/f'jobs/real/{y}-{w}y/features.json');lookup={r['match_id']:r for r in fresh}
            for r in rr:
                if r['match_id'] not in lookup:continue
                a=lookup[r['match_id']]
                reset.append(dict(year=y,window=w,date=day,match_id=r['match_id'],continued_difference=r['difference'],
                    rebuilt_difference=a['difference'],continued_p_home=r['p_home'],rebuilt_p_home=a['p_home'],
                    difference_change=a['difference']-r['difference'],probability_change=a['p_home']-r['p_home'],
                    scope='same-date reset diagnostic, no current outcome seen'))
    table=ROOT/'outputs/tables/history_window'/ctx['rid'];table.mkdir(parents=True,exist_ok=True)
    put_table(table,'strict_probes.csv',results);put_table(table,'annual_reset_diagnostics.csv',reset)
    write_json(ctx['log']/'probes.json',dict(completed=True,strict_dates=len(dates),strict_jobs=len(dates)*5,
        strict_rows=len(results),reset_rows=len(reset),reset_first_year=1981,reset_missing1980_reason='no prior1979 annual task in study'))


def evaluate_real(ctx):
    delivery=read_json(ctx['log']/'real_features.json');guard=Guard(ctx['cfg'],'downstream_evaluation')
    predictions=[];metrics=[];yearly=[];models={};telemetry=[];beg=time.perf_counter()
    oldlog=ROOT/'outputs/logs/history_window/outcome-0a52e15e2ae493570acb';oldmodels=read_json(oldlog/'models.json')
    for name,folder in delivery['policies'].items():
        rows=read_rows(ROOT/folder/'analysis_matches.csv');rows.sort(key=lambda r:(r['date'],r['match_id']))
        for y in range(2000,2025):
            key=f'{name}:{y}:context_cumulative';job=ctx['log']/'jobs/outcome'/f'{name}-{y}';print('RATING_OUTCOME',name,y,flush=True)
            if (job/'complete.json').exists():
                m=read_json(job/'complete.json')
                for n,h in m['outputs'].items():
                    if file_hash(job/n)!=h:raise ValueError('OUTCOME_CACHE_CHANGED')
                rr=read_json(job/'predictions.json');model=read_json(job/'model.json');t=read_json(job/'telemetry.json')
            else:
                start=time.perf_counter();guard.check(start);train=[r for r in rows if int(r['year'])<y];now=[r for r in rows if int(r['year'])==y]
                if any(r['prediction_cutoff']!='initial_prior' and r['prediction_cutoff']>=r['date'] for r in train+now):raise ValueError('FUTURE_RATING')
                design=Design(train)
                if name=='cumulative_1950':model=oldmodels[f'{y}:cumulative'];reused=True
                else:model=fit_past(train,design,'M3_nested',ctx['joint']['numerics'],1.);reused=False
                pp=predict(model,now,design)
                rr=[dict(policy_name=name,rating_policy_id=policy_id(ctx,name),outcome_training_policy='cumulative_since1980',
                    match_id=r['match_id'],date=r['date'],year=y,era=r['era'],tournament_group=r['tournament_group'],home_region=r['home_region'],
                    home_win=int(r['home_win']),probability=float(f'{float(p):.10f}'),model_key=key,
                    training_min=train[0]['date'],training_max=train[-1]['date'],rating_cutoff=r['prediction_cutoff']) for r,p in zip(now,pp)]
                t=dict(policy_name=name,year=y,seconds=time.perf_counter()-start,training_rows=len(train),target_rows=len(now),
                       reused_r10_model=reused,encoding_uses_target_rows=False,training_ids_sha256=fingerprint(sorted(r['match_id'] for r in train)))
                model=dict(model,training_ids_sha256=t['training_ids_sha256'],encoding_weights={s+':'+g+':'+u:v for (s,g,u),v in design.weights.items()})
                for n,v in [('predictions.json',rr),('model.json',model),('telemetry.json',t)]:write_json(job/n,v)
                write_json(job/'complete.json',dict(outputs={n:file_hash(job/n) for n in ('predictions.json','model.json','telemetry.json')}))
            predictions+=rr;models[key]=model;telemetry.append(t);yearly.append(dict(policy_name=name,year=y,**summarize(rr,1e-6)))
        subset=[r for r in predictions if r['policy_name']==name]
        for scope,lo,hi in [('all',2000,2024),('development',2000,2009),('evaluation',2010,2024)]:
            metrics.append(dict(policy_name=name,group=scope,**summarize([r for r in subset if lo<=r['year']<=hi],1e-6)))
        for field in ('tournament_group','era','home_region'):
            for value in sorted({r[field] for r in subset}):metrics.append(dict(policy_name=name,group=field+':'+value,**summarize([r for r in subset if r[field]==value],1e-6)))
    table=ROOT/'outputs/tables/history_window'/ctx['rid'];table.mkdir(parents=True,exist_ok=True)
    for filename,rr in [('rating_predictions.csv',predictions),('rating_metrics.csv',metrics),('rating_yearly.csv',yearly)]:put_table(table,filename,rr)
    write_json(ctx['log']/'rating_models.json',models);write_json(ctx['log']/'rating_outcome.json',dict(completed=True,logical_fits=150,
        fresh_fits=sum(not t['reused_r10_model'] for t in telemetry),reused_models=sum(t['reused_r10_model'] for t in telemetry),
        telemetry=telemetry,prediction_rows=len(predictions),seconds_this_invocation=time.perf_counter()-beg,no_rating_automatic_selection=True))


def world_job(ctx,seed,path,link,guard):
    gg,tt=generate(seed,path,link,240)
    for months in range(252,361,12):gg,tt=extend(seed,path,link,gg,tt,months)
    direct,dt=generate(seed,path,link,360)
    if gg!=direct or tt!=dt:raise ValueError('LONG_PREFIX_TEST_FAILED')
    world=tt[0]['world_id'];base=ctx['log']/'jobs/worlds'/world.replace(':','_');monthly=[];native=[];times=[]
    truth_bydate={r['date']:r for r in tt};games_byid={g['match_id']:g for g in gg}
    for w in ctx['cfg']['windows']:
        if w is None:
            rows,pairs,_,timing=segment(gg,TEAMS,ctx['params'],ctx['num'],'2000-01-01','2030-01-01','2020-01-01',
                'cumulative_2000',None,base/'cumulative',ctx['cfg'],guard,collect_sim=True)
            times.append(timing);name='cumulative'
        else:
            rows=[];pairs=[];name=f'annual_reset_{w}y'
            for y in range(2020,2030):
                rr,pr,_,timing=annual_job(gg,TEAMS,ctx['params'],ctx['num'],y,w,base,ctx['cfg'],guard,collect_sim=True,start='2000-01-01')
                rows+=rr;pairs+=pr;times.append(timing)
        pairdays=defaultdict(list);rdays=defaultdict(list)
        for r in rows:rdays[r['date']].append(r)
        for r in pairs:pairdays[r['date']].append(r)
        previous=None
        for day,ps in sorted(pairdays.items()):
            truth=truth_bydate[day];gaps=np.array([r['difference'] for r in ps]);true=np.array([truth['true_'+r['home']]-truth['true_'+r['away']] for r in ps])
            rr=rdays[day];p_error=np.mean([(r['p_home']-games_byid[r['match_id']]['true_p_home'])**2 for r in rr])
            means={};variances={}
            for r in ps:
                means[r['home']]=r['home_mean'];means[r['away']]=r['away_mean'];variances[r['home']]=r['home_variance'];variances[r['away']]=r['away_variance']
            monthly.append(dict(world_id=world,seed=seed,path=path,link=link,policy_name=name,month=truth['month'],date=day,
                gap_mse=float(np.mean((gaps-true)**2)),native_probability_mse=float(p_error),
                pair_step_mse=None if previous is None else float(np.mean((gaps-previous)**2)),
                **{'estimated_'+t:means[t] for t in TEAMS},**{'variance_'+t:variances[t] for t in TEAMS},
                prediction_cutoff=rr[0]['prediction_cutoff']))
            previous=gaps
            for r in rr:
                g=games_byid[r['match_id']]
                native.append(dict(world_id=world,seed=seed,path=path,link=link,policy_name=name,month=truth['month'],
                    match_id=r['match_id'],date=day,home=r['home'],away=r['away'],p_home=r['p_home'],true_p_home=g['true_p_home'],
                    outcome=g['outcome'],home_history=r['home_history'],away_history=r['away_history'],prediction_cutoff=r['prediction_cutoff']))
    return monthly,native,gg,tt,times


def simulation(ctx,development_only=False):
    phase='simulation_development' if development_only else 'formal_simulation';guard=Guard(ctx['cfg'],phase)
    seeds=ctx['cfg']['simulation']['development_seeds' if development_only else 'formal_seeds'];monthly=[];native=[];truth=[];games=[];times=[]
    for seed in seeds:
        for path in ctx['cfg']['simulation']['paths']:
            for link in ctx['cfg']['simulation']['links']:
                print('LONG_SIMULATION',phase,seed,path,link,flush=True)
                mm,nn,gg,tt,ts=world_job(ctx,seed,path,link,guard);monthly+=mm;native+=nn;truth+=tt;games+=gg;times+=ts
    if development_only:
        # Projection uses all six scenarios, not whichever policy happened to win.
        total=sum(t['seconds'] for t in times);estimate=1.5*total*len(ctx['cfg']['simulation']['formal_seeds'])/len(seeds)
        report=dict(passed=estimate<=ctx['cfg']['phase_seconds']['formal_simulation'],development_seed_groups=len(seeds),
            scenario_histories=len(seeds)*6,job_seconds=total,estimated_formal_seconds=estimate,prefix_checked=True,estimate_not_guarantee=True)
        write_json(ctx['log']/'simulation_development.json',report)
        if not report['passed']:raise RuntimeError('SIMULATION_COST_ADMISSION_NOT_PASSED')
        return
    table=ROOT/'outputs/tables/history_window'/ctx['rid'];table.mkdir(parents=True,exist_ok=True)
    for filename,rr in [('latent_monthly.csv',monthly),('latent_native_predictions.csv',native),('latent_truth.csv',truth),('simulated_games.csv',games)]:put_table(table,filename,rr)
    summary=[];seedmetrics=[];policies=sorted({r['policy_name'] for r in monthly})
    for seed in seeds:
        for path in ctx['cfg']['simulation']['paths']:
            for link in ctx['cfg']['simulation']['links']:
                for policy in policies:
                    rr=[r for r in monthly if r['seed']==seed and r['path']==path and r['link']==link and r['policy_name']==policy]
                    seedmetrics.append(dict(seed=seed,path=path,link=link,policy_name=policy,months=len(rr),
                        gap_mse=float(np.mean([r['gap_mse'] for r in rr])),native_probability_mse=float(np.mean([r['native_probability_mse'] for r in rr])),
                        mean_pair_step_mse=float(np.mean([r['pair_step_mse'] for r in rr if r['pair_step_mse'] is not None])),
                        first12_after_jump_mse=float(np.mean([r['gap_mse'] for r in rr if 288<=r['month']<=299])),
                        next24_after_jump_mse=float(np.mean([r['gap_mse'] for r in rr if 300<=r['month']<=323]))))
    for path in ctx['cfg']['simulation']['paths']:
        for link in ctx['cfg']['simulation']['links']:
            for policy in policies:
                rr=[r for r in seedmetrics if r['path']==path and r['link']==link and r['policy_name']==policy]
                base=[r for r in seedmetrics if r['path']==path and r['link']==link and r['policy_name']=='cumulative']
                delta=np.array([r['gap_mse']-b['gap_mse'] for r,b in zip(rr,base)])
                summary.append(dict(path=path,link=link,policy_name=policy,independent_seed_groups=len(seeds),
                    gap_mse=float(np.mean([r['gap_mse'] for r in rr])),native_probability_mse=float(np.mean([r['native_probability_mse'] for r in rr])),
                    paired_gap_mse_minus_cumulative=float(delta.mean()),paired_monte_carlo_se=float(delta.std(ddof=1)/np.sqrt(len(delta))),
                    first12_after_jump_mse=float(np.mean([r['first12_after_jump_mse'] for r in rr])),
                    next24_after_jump_mse=float(np.mean([r['next24_after_jump_mse'] for r in rr])),
                    interpretation='specified-generator point results and seed-group MonteCarlo precision, not real-world interval'))
    put_table(table,'latent_seed_metrics.csv',seedmetrics);put_table(table,'latent_summary.csv',summary)
    write_json(ctx['log']/'formal_simulation.json',dict(completed=True,independent_seed_groups=len(seeds),scenario_histories=len(seeds)*6,
        monthly_rows=len(monthly),native_rows=len(native),truth_rows=len(truth),simulated_games=len(games),prefix_checked=True,
        job_seconds=sum(t['seconds'] for t in times),jobs=len(times),full_inference_admitted=False))


def seal(ctx):
    log=ctx['log'];table=ROOT/'outputs/tables/history_window'/ctx['rid']
    needed=['real_development.json','simulation_development.json','real_features.json','rating_outcome.json','probes.json','formal_simulation.json']
    if not all((log/n).exists() for n in needed):raise ValueError('STAGE5_INCOMPLETE')
    figure_paths=build_materials(ctx)
    outputs={p.relative_to(ROOT).as_posix():file_hash(p) for p in log.iterdir() if p.is_file() and p.name not in ('manifest.json','failure.json')}
    outputs.update({p.relative_to(ROOT).as_posix():file_hash(p) for p in table.iterdir() if p.is_file()})
    outputs.update({p.relative_to(ROOT).as_posix():file_hash(p) for p in figure_paths})
    for folder in read_json(log/'real_features.json')['policies'].values():
        outputs.update({p.relative_to(ROOT).as_posix():file_hash(p) for p in (ROOT/folder).iterdir() if p.is_file()})
    write_json(log/'manifest.json',dict(identity=ctx['identity'],outputs=outputs,independent_audit_pending=True))
    write_json(ROOT/'outputs/logs/history_window/rating_pointer.json',dict(run_id=ctx['rid'],log_directory=log.relative_to(ROOT).as_posix(),
        table_directory=table.relative_to(ROOT).as_posix(),manifest_sha256=file_hash(log/'manifest.json'),independent_audit_pending=True))


def build_materials(ctx):
    import io
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    table=ROOT/'outputs/tables/history_window'/ctx['rid'];folder=ROOT/'outputs/figures/history_window'/ctx['rid'];folder.mkdir(parents=True,exist_ok=True)
    available={f.name for f in font_manager.fontManager.ttflist};font=next((f for f in ('Microsoft YaHei','SimHei','Noto Sans CJK SC') if f in available),'DejaVu Sans')
    plt.rcParams.update({'font.family':font,'axes.unicode_minus':False,'svg.hashsalt':'q6-rating-memory-v1'})
    names=[f'annual_reset_{w}y' for w in ctx['cfg']['windows'][:-1]]+['cumulative_1950'];labels=['Annual2','Annual4','Annual8','Annual12','Annual20','Cumulative']
    real=read_rows(table/'rating_metrics.csv');rr=[next(r for r in real if r['group']=='all' and r['policy_name']==name) for name in names]
    out=[]
    def save(fig,name):
        for ext in ('png','svg'):
            b=io.BytesIO();fig.savefig(b,format=ext,dpi=170,bbox_inches='tight',metadata={'Date':None} if ext=='svg' else {})
            p=folder/(name+'.'+ext);atomic_bytes(p,b.getvalue());out.append(p)
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.8));values=[float(r['primary_log_loss']) for r in rr]
    ax.plot(labels,values,'o-',color='#2b6385');ax.axhline(values[-1],ls='--',color='gray',lw=1)
    for x,y in enumerate(values):ax.annotate(f'{y:.5f}',(x,y),xytext=(0,8),textcoords='offset points',ha='center')
    ax.margins(y=.15);ax.set(xlabel='Rating memory: annual reset, then daily updates',ylabel='Home-win log loss (lower is better)',title='Same 16,599 matches; outcome model always learns cumulative history')
    ax.grid(axis='y',alpha=.2);save(fig,'real_rating_memory')
    monthly=read_rows(table/'latent_monthly.csv');simnames=[f'annual_reset_{w}y' for w in ctx['cfg']['windows'][:-1]]+['cumulative']
    fig,axes=plt.subplots(3,1,figsize=(10,11),sharex=True)
    for ax,path in zip(axes,ctx['cfg']['simulation']['paths']):
        for name,label in zip(simnames,labels):
            vals=[]
            for m in range(240,360):
                selected=[float(r['gap_mse']) for r in monthly if r['path']==path and r['policy_name']==name and int(r['month'])==m]
                vals.append(np.mean(selected))
            ax.plot(range(240,360),vals,label=label,lw=1.3)
        if path=='jump':ax.axvline(288,ls='--',color='gray',lw=1)
        if path=='drift':ax.axvline(240,ls='--',color='gray',lw=1)
        ax.set(ylabel='Relative-skill MSE',title=path+'; mean over both noise links, 10 seed groups');ax.grid(alpha=.2)
    axes[0].legend(ncol=3);axes[-1].set_xlabel('Synthetic month (first 240 months are prior history)');save(fig,'latent_tracking')
    strict=read_rows(table/'strict_probes.csv');reset=read_rows(table/'annual_reset_diagnostics.csv')
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    strictmax={};resetmax={}
    for j,w in enumerate(ctx['cfg']['windows'][:-1]):
        s=[abs(float(r['strict_p_home'])-float(r['annual_p_home'])) for r in strict if int(r['window'])==w]
        a=[abs(float(r['probability_change'])) for r in reset if int(r['window'])==w]
        strictmax[str(w)]=max(s);resetmax[str(w)]=max(a)
        axes[0].scatter(np.full(len(s),j),s,s=14,alpha=.5);axes[1].scatter(np.full(len(a),j),a,s=12,alpha=.4)
    for ax in axes:ax.set_xticks(range(5),['2','4','8','12','20']);ax.set_xlabel('Nominal years at annual reset');ax.grid(axis='y',alpha=.2)
    axes[0].set(ylabel='Absolute native probability difference',title='Strict vs annual: predeclared development dates')
    axes[1].set(ylabel='Absolute native probability change',title='Same-date new-year reset effect, 1981–2024')
    save(fig,'policy_boundary_diagnostics')
    write_json(table/'display_data.json',dict(real_results=rr,strict_max_native_probability_difference=strictmax,
        annual_reset_max_native_probability_change=resetmax,font=font,matplotlib=matplotlib.__version__,
        figures=[p.relative_to(ROOT).as_posix() for p in out],no_formal_intervals=True,
        annual_not_strict_W_year=True,simulation_seed_groups=10,simulation_scenarios=60))
    return out


def run(stage='all',mode='full',config='config/history_window_rating.json'):
    ctx=create_run(config)
    TASK_REQUESTS.clear()
    if mode=='plan':
        print(dict(run_id=ctx['rid'],annual_tasks=225,strict_tasks=60,real_feature_rows=149502,real_predictions=99594,
                   formal_seed_groups=10,formal_scenarios=60));return ctx
    try:
        with threadpool_limits(limits=1),numerical_cache() as cache:
            if stage in ('all','rating'):
                development(ctx)
                if mode=='full':real_features(ctx);probes(ctx);evaluate_real(ctx)
            if stage in ('all','latent'):
                simulation(ctx,True)
                if mode=='full':simulation(ctx,False)
            write_json(ctx['log']/'numerical_cache.json',dict(hits=cache.cache_info().hits,misses=cache.cache_info().misses,
                maxsize=8192,exact_count_keys=True,single_factor_cavity=cache.factor_stats,thresholds_changed=False))
            if stage=='all' and mode=='full':seal(ctx)
    except Exception as e:
        write_json(ctx['log']/'failure.json',dict(stage=stage,mode=mode,error_type=type(e).__name__,error=str(e),
            incomplete=True,no_silent_dropping=True));raise
    finally:
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        write_json(ctx['log']/'invocations'/f'{stamp}.json',dict(stage=stage,mode=mode,task_requests=TASK_REQUESTS,
            computed_requests=sum(r['source']=='computed' for r in TASK_REQUESTS),cache_requests=sum(r['source']=='verified_cache' for r in TASK_REQUESTS)))
    print('RATING_MEMORY_PHASE_COMPLETE',ctx['rid'],stage,mode,flush=True);return ctx
