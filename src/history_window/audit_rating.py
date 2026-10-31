"""Independent stage5 arithmetic, boundaries, identities and simulation truth."""
from collections import defaultdict
from pathlib import Path
from itertools import combinations
from datetime import date
import math
import numpy as np
from threadpoolctl import threadpool_limits
from src.data_contract import file_hash,write_json,fingerprint
from src.strength.io import ROOT,read_rows
from src.strength_joint.design import Design
from src.strength_joint.model import predict
from .contracts import read_json


def audit_rating(run=None,refit_examples=False):
    pointer=ROOT/'outputs/logs/history_window/rating_pointer.json'
    log=ROOT/(run or read_json(pointer)['log_directory']);man=read_json(log/'manifest.json');cfg=read_json(log/'protocol.json')
    table=ROOT/'outputs/tables/history_window'/log.name;checks=[];failures=[]
    def ck(name,passed):
        checks.append(name)
        if not passed:failures.append(name)
    for p,h in man['outputs'].items():ck('output_hash:'+p,file_hash(ROOT/p)==h)
    for p,h in man['identity']['inputs'].items():ck('input_hash:'+p,file_hash(ROOT/p)==h)
    facts=read_rows(ROOT/'data/processed/strength/joint-preparation-6fa9d025ba40d11cd2f8/analysis_matches.csv');facts={r['match_id']:r for r in facts}
    delivery=read_json(log/'real_features.json');feature_count=0;rows_by_policy={}
    for name,folder in delivery['policies'].items():
        features=read_rows(ROOT/folder/'prematch_features.csv');adapted=read_rows(ROOT/folder/'analysis_matches.csv');rows_by_policy[name]=adapted
        ck('policy_ids:'+name,len(features)==24917 and len({r['match_id'] for r in features})==24917 and {r['match_id'] for r in features}==facts.keys())
        lookup={r['match_id']:r for r in features};feature_count+=len(features)
        for r in adapted:
            f=facts[r['match_id']];s=lookup[r['match_id']];y=int(r['year'])
            left='1950-01-01' if name=='cumulative_1950' else f"{max(1950,y-int(name.split('_')[-1][:-1]))}-01-01"
            ck('fact:'+name+r['match_id'],all(r[k]==f[k] for k in ('date','year','home_win','outcome','home_region','away_region','home_unit','away_unit','tournament_group')))
            ck('feature:'+name+r['match_id'],s['window_left']==left and s['date']==r['date'] and
                (r['prediction_cutoff']=='initial_prior' or r['prediction_cutoff']<r['date']) and
                abs(float(r['strength_difference'])-float(s['difference']))<1e-9)
            base=float(r['strength_difference_base_variance']);v=float(r['strength_difference_variance'])
            ck('distribution:'+name+r['match_id'],base>0 and abs(v-base-(float(r['home_jump_intensity'])+float(r['away_jump_intensity']))*float(r['jump_scale_sd'])**2)<2e-8)
    ck('feature_count',feature_count==149502)
    preds=read_rows(table/'rating_predictions.csv');models=read_json(log/'rating_models.json');bykey=defaultdict(list);bypolicy=defaultdict(list)
    for r in preds:bykey[r['model_key']].append(r);bypolicy[r['policy_name']].append(r)
    ck('prediction_total',len(preds)==99594 and len({(r['rating_policy_id'],r['match_id']) for r in preds})==99594)
    for r in preds:
        ck('prediction_fact:'+r['model_key']+r['match_id'],r['home_win']==facts[r['match_id']]['home_win'] and r['date']==facts[r['match_id']]['date'] and
            r['training_max']<r['date'] and (r['rating_cutoff']=='initial_prior' or r['rating_cutoff']<r['date']) and
            r['outcome_training_policy']=='cumulative_since1980' and 0<=float(r['probability'])<=1)
    def metric(rr):
        p=np.array([float(r['probability']) for r in rr]);y=np.array([int(r['home_win']) for r in rr]);q=np.clip(p,1e-6,1-1e-6)
        return dict(matches=len(rr),primary_log_loss=float(np.mean(-y*np.log(q)-(1-y)*np.log1p(-q))),
            brier=float(np.mean((p-y)**2)),binary_accuracy=float(np.mean((p>=.5)==y)),calibration_bias_pp=float(100*np.mean(p-y)))
    for r in read_rows(table/'rating_metrics.csv'):
        rr=bypolicy[r['policy_name']];g=r['group']
        if g=='development':rr=[x for x in rr if int(x['year'])<=2009]
        elif g=='evaluation':rr=[x for x in rr if int(x['year'])>=2010]
        elif g!='all':
            field,value=g.split(':',1);rr=[x for x in rr if x[field]==value]
        for k,v in metric(rr).items():ck('real_metric:'+r['policy_name']+g+k,abs(float(r[k])-v)<1e-8)
    with threadpool_limits(limits=1):
        for name,rows in rows_by_policy.items():
            for y in range(2000,2025):
                train=sorted((r for r in rows if int(r['year'])<y),key=lambda r:(r['date'],r['match_id']))
                now=sorted((r for r in rows if int(r['year'])==y),key=lambda r:(r['date'],r['match_id']))
                key=f'{name}:{y}:context_cumulative';m=models[key];design=Design(train);pp=predict(m,now,design);rr=bykey[key]
                ck('year_training:'+key,m['training_ids_sha256']==fingerprint(sorted(r['match_id'] for r in train)))
                ck('year_ids:'+key,[r['match_id'] for r in rr]==[r['match_id'] for r in now])
                ck('all_model_predictions:'+key,max(abs(float(p)-float(r['probability'])) for p,r in zip(pp,rr))<2e-8)
                ck('past_encoding:'+key,m['encoding_weights']=={s+':'+g+':'+u:v for (s,g,u),v in design.weights.items()})
    old=read_rows(ROOT/'outputs/tables/history_window/outcome-0a52e15e2ae493570acb/predictions.csv');old={r['match_id']:r for r in old if r['window']=='cumulative'}
    ck('cumulative_reference_unchanged',all(float(r['probability'])==float(old[r['match_id']]['probability']) for r in bypolicy['cumulative_1950']))
    # Simulator truth is independently reconstructed from the specified base and
    # absolute calendar, not from any estimator. RNG stream reproducibility is
    # separately tested by prefix tests.
    truth=read_rows(table/'latent_truth.csv');tm={r['world_id']+':'+r['month']:r for r in truth};monthlies=read_rows(table/'latent_monthly.csv')
    ck('truth_count',len(truth)==21600 and len(tm)==21600)
    for r in truth:
        m=int(r['month']);base=tm[r['world_id']+':0'];v=np.array([float(base['true_'+t]) for t in 'ABCD'])
        if r['path']=='drift':v+=max(0,min(1,(m-240)/120))*np.array([-1.2,.6,.6,0.])
        elif r['path']=='jump' and m>=288:v+=np.array([-1.6,0.,.8,.8])
        v-=v.mean();ck('truth_path:'+r['world_id']+r['month'],max(abs(float(r['true_'+t])-x) for t,x in zip('ABCD',v))<2e-9)
    ck('monthly_count',len(monthlies)==43200 and len({(r['world_id'],r['policy_name'],r['month']) for r in monthlies})==43200)
    monthly_by=defaultdict(list)
    for r in monthlies:
        t=tm[r['world_id']+':'+r['month']];error=[]
        for a,b in combinations('ABCD',2):error.append(((float(r['estimated_'+a])-float(r['estimated_'+b]))-(float(t['true_'+a])-float(t['true_'+b])))**2)
        ck('latent_error:'+r['world_id']+r['policy_name']+r['month'],abs(sum(error)/6-float(r['gap_mse']))<1e-8 and r['prediction_cutoff']<r['date'])
        monthly_by[int(r['seed']),r['path'],r['link'],r['policy_name']].append(r)
    native=read_rows(table/'latent_native_predictions.csv');native_by=defaultdict(list)
    for r in native:native_by[r['world_id'],r['policy_name'],r['month']].append(r)
    ck('native_count',len(native)==86400)
    for r in monthlies:
        rr=native_by[r['world_id'],r['policy_name'],r['month']]
        val=sum((float(x['p_home'])-float(x['true_p_home']))**2 for x in rr)/2
        ck('latent_probability:'+r['world_id']+r['policy_name']+r['month'],len(rr)==2 and abs(val-float(r['native_probability_mse']))<1e-8)
    seedrows=read_rows(table/'latent_seed_metrics.csv');seedlookup={}
    for r in seedrows:
        key=(int(r['seed']),r['path'],r['link'],r['policy_name']);rr=monthly_by[key];seedlookup[key]=r
        for field,selected in [('gap_mse',rr),('native_probability_mse',rr),('first12_after_jump_mse',[x for x in rr if 288<=int(x['month'])<=299]),('next24_after_jump_mse',[x for x in rr if 300<=int(x['month'])<=323])]:
            sourcefield='gap_mse' if 'after_jump' in field else field
            ck('seed_metric:'+str(key)+field,abs(sum(float(x[sourcefield]) for x in selected)/len(selected)-float(r[field]))<1e-8)
    for r in read_rows(table/'latent_summary.csv'):
        deltas=[float(seedlookup[s,r['path'],r['link'],r['policy_name']]['gap_mse'])-float(seedlookup[s,r['path'],r['link'],'cumulative']['gap_mse']) for s in cfg['simulation']['formal_seeds']]
        se=float(np.std(deltas,ddof=1)/np.sqrt(10))
        ck('seed_group_mcse:'+r['path']+r['link']+r['policy_name'],int(r['independent_seed_groups'])==10 and abs(se-float(r['paired_monte_carlo_se']))<1e-8)
    probereport=read_json(log/'probes.json');ck('strict_probe_tasks',probereport['strict_jobs']==60 and probereport['strict_dates']==12)
    for r in read_rows(table/'strict_probes.csv'):
        from .protocol import anniversary
        ck('strict_probe_boundaries:'+r['match_id']+r['window'],r['strict_left']==anniversary(r['date'],int(r['window'])) and
            r['annual_left']==str(int(r['date'][:4])-int(r['window']))+'-01-01')
    for r in read_rows(table/'annual_reset_diagnostics.csv'):
        ck('reset_arithmetic:'+r['match_id']+r['window'],abs(float(r['rebuilt_difference'])-float(r['continued_difference'])-float(r['difference_change']))<1e-8)
    repeats=[]
    if refit_examples:
        from .ratings import load_inputs,annual_job,Guard,numerical_cache
        cfg2,gg,_,_,p,n,_=load_inputs();tmp=ROOT/'outputs/test_tmp'/('rating-repeat-'+log.name)
        with threadpool_limits(limits=1),numerical_cache():
            for y,w in [(1980,2),(2024,20)]:
                rr,_,_,_=annual_job(gg,{g[k] for g in gg for k in ('home','away')},p,n,y,w,tmp,cfg2,Guard(cfg2,'independent_audit'),set(facts))
                original=read_json(log/f'jobs/real/{y}-{w}y/features.json')
                err=max(abs(a[k]-b[k]) for a,b in zip(rr,original) for k in ('difference','difference_variance','p_home','p_draw','p_away'))
                ck('fresh_replay:'+str(y)+str(w),err<1e-10);repeats.append(dict(year=y,years=w,max_error=err))
    report=dict(passed=not failures,checks=len(checks),failures=failures,run_id=log.name,feature_rows=feature_count,
        real_prediction_rows=len(preds),simulated_scenario_histories=60,independent_seed_groups=10,monthly_rows=len(monthlies),
        repeats=repeats,formal_inference=False,human_review=False)
    write_json(log/'independent_audit.json',report)
    if failures:raise ValueError('RATING_AUDIT_FAILED:'+repr(failures[:10]))
    write_json(log/'adoption.json',dict(run_id=log.name,decision_log_id=cfg['decision_log_id'],
        manifest_sha256=file_hash(log/'manifest.json'),audit_sha256=file_hash(log/'independent_audit.json'),
        scope='step5 numerical/descriptive completion; annual policies not strict full-W-year; no formal inference'))
    ptr=read_json(pointer)
    if ptr['run_id']==log.name:
        ptr['independent_audit_pending']=False;ptr['adoption']=(log/'adoption.json').relative_to(ROOT).as_posix();write_json(pointer,ptr)
    print(report,flush=True);return report
