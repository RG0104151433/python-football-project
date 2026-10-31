"""Annual reset/date replay with immutable job publication and resumable state."""
from collections import defaultdict
from contextlib import contextmanager
from datetime import date
from functools import lru_cache
from pathlib import Path
import io,json,time,zipfile
import numpy as np
import psutil
from src.data_contract import atomic_bytes,csv_bytes,file_hash,fingerprint,write_json
from src.strength.io import ROOT,read_rows,environment
from src.strength.global_run import load as load_learning
from src.strength_joint.contract import load as load_study
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength import collapsed_jump as core
from .contracts import read_json
from .replay import forecast

TASK_REQUESTS=[]


@contextmanager
def numerical_cache(enabled=True,single_factor=True):
    """Single-worker, bounded memoization of a pure helper; restore on exit.

    Original filter source and numerical thresholds are untouched. Count keys
    are exact. The one-factor EP cavity is mathematically invariant; its tilted
    integral is reused with explicit floating-point and reference checks.
    """
    original=core.count_weights
    original_jump=core.jump_update;original_block=core.block_local
    cached=lru_cache(maxsize=8192)(original) if enabled else original
    factor_stats=dict(calls=0,reuses=0,numerical_fallbacks=0)
    cached.factor_stats=factor_stats
    core.count_weights=cached
    def jump_with_invariant_cavity(mean,cov,design,games,index,mus,params,num):
        # With one EP block factor and no other date factors, deleting that
        # factor leaves the PRIOR cavity at every iteration. Reuse its expensive
        # local moment integral; retain the original global EP/damping/update.
        # No near-equal general cavities, counts or observations are merged.
        if len(games)<=1 or len(core.components(games))!=1:
            return original_jump(mean,cov,design,games,index,mus,params,num)
        pm=design@mean;pc=design@cov@design.T;stored=[]
        def same_factor(cm,cv,*args):
            factor_stats['calls']+=1
            if np.max(np.abs(cm-pm))>1e-8 or np.max(np.abs(cv-pc))>1e-8:
                factor_stats['numerical_fallbacks']+=1
                return original_block(cm,cv,*args)
            if not stored:stored.append(original_block(cm,cv,*args))
            else:factor_stats['reuses']+=1
            return stored[0]
        core.block_local=same_factor
        try:return original_jump(mean,cov,design,games,index,mus,params,num)
        finally:core.block_local=original_block
    if enabled and single_factor:core.jump_update=jump_with_invariant_cavity
    try:yield cached
    finally:
        core.count_weights=original;core.jump_update=original_jump;core.block_local=original_block


def load_inputs(path='config/history_window_rating.json'):
    cfg=read_json(ROOT/path)
    if cfg['schema_version']!='history-window-rating-v1':raise ValueError('RATING_PROTOCOL_MISMATCH')
    _,games,inputs=load_learning(cfg['learning_config'])
    joint,facts,_,_,more=load_study(cfg['study_config']);inputs.update(more)
    raw=ROOT/cfg['raw_score'];manifest=read_json(raw/'manifest.json')
    for name in ('prematch_features.csv','manifest.json'):
        if name!='manifest.json' and file_hash(raw/name)!=manifest['outputs'][name]:raise ValueError('RAW_SCORE_CHANGED')
        inputs[(raw/name).relative_to(ROOT).as_posix()]=file_hash(raw/name)
    inputs[path]=file_hash(ROOT/path)
    facts=sorted(facts,key=lambda r:(r['date'],r['match_id']))
    return cfg,games,facts,joint,manifest['identity']['parameters'],manifest['identity']['numerics'],inputs


def create_run(config_path='config/history_window_rating.json'):
    cfg,games,facts,joint,params,num,inputs=load_inputs(config_path)
    files=[*sorted((ROOT/'src/history_window').glob('*.py')),*sorted((ROOT/'src/strength').glob('*.py')),
        *sorted((ROOT/'src/strength_joint').glob('*.py')),ROOT/'src/data_contract.py',ROOT/'src/strength_predictive_validation.py',
        ROOT/'scripts/analyze_history_window.py',ROOT/'scripts/audit_history_window.py',
        *sorted((ROOT/'tests').glob('test_history_window_*.py'))]
    identity=dict(protocol=cfg,inputs=inputs,code={p.relative_to(ROOT).as_posix():file_hash(p) for p in files},environment=environment())
    rid='rating-memory-'+fingerprint(identity)[:20];log=ROOT/'outputs/logs/history_window'/rid
    log.mkdir(parents=True,exist_ok=True)
    if not (log/'started.json').exists():
        write_json(log/'protocol.json',cfg);write_json(log/'started.json',dict(identity=identity,settings_frozen_before_comparison=True))
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
            for p in files+[ROOT/config_path]:z.writestr(zipfile.ZipInfo(p.relative_to(ROOT).as_posix(),(1980,1,1,0,0,0)),p.read_bytes())
        atomic_bytes(log/'source_snapshot.zip',buf.getvalue())
    return dict(cfg=cfg,games=games,facts=facts,joint=joint,params=params,num=num,inputs=inputs,identity=identity,rid=rid,log=log)


class Guard:
    def __init__(self,cfg,phase):
        self.started=time.perf_counter();self.limit=cfg['phase_seconds'][phase];self.cfg=cfg
    def check(self,job_started):
        if time.perf_counter()-self.started>self.limit:raise TimeoutError('PHASE_BUDGET')
        if time.perf_counter()-job_started>self.cfg['max_job_seconds']:raise TimeoutError('JOB_BUDGET')
        if psutil.Process().memory_info().rss/2**20>self.cfg['max_rss_mib']:raise MemoryError('RSS_BUDGET')


def full_forecast(engine,day,targets):
    rr=forecast(engine,day,targets);lookup={g['match_id']:g for g in targets}
    for r in rr:
        g=lookup[r['match_id']];i,j=engine.index[g['home']],engine.index[g['away']]
        h=len(engine.teams)+(int(g['friendly']) if engine.home_dimensions==2 else 0)
        dt_h=(date.fromisoformat(day)-date.fromisoformat(engine.last.get(g['home'],day))).days/365.2425
        dt_a=(date.fromisoformat(day)-date.fromisoformat(engine.last.get(g['away'],day))).days/365.2425
        r.update(home_variance=float(engine.cov[i,i]+(engine.params['q']+engine.params['jump_rate']*engine.params['jump_sd']**2)*dt_h),
            away_variance=float(engine.cov[j,j]+(engine.params['q']+engine.params['jump_rate']*engine.params['jump_sd']**2)*dt_a),
            home_away_covariance=float(engine.cov[i,j]),home_term_variance=float(engine.cov[h,h]+engine.params.get('home_q',0)*
                ((date.fromisoformat(day)-date.fromisoformat(engine.last_day)).days/365.2425 if engine.last_day else 0)),
            previously_disconnected=engine.find(g['home'])!=engine.find(g['away']))
    return rr


def features(rows,day,engine_last,params,left,policy,years,mus):
    result=[]
    for r in rows:
        out={k:v for k,v in r.items() if k not in ('outcome_index','prediction_basis')}
        mh,ma=mus[r['home']],mus[r['away']]
        out.update(policy_name=policy,nominal_years=years,window_left=left,allowed_history_end_exclusive=day,
            allowed_history_years=(date.fromisoformat(day)-date.fromisoformat(left)).days/365.2425,
            difference_base_variance=float(r['difference_variance']-(mh+ma)*params['jump_sd']**2),
            home_jump_intensity=mh,away_jump_intensity=ma,jump_scale_sd=params['jump_sd'])
        if out['difference_base_variance']<=0:raise ValueError('INVALID_FEATURE_VARIANCE')
        result.append(out)
    return result


def write_checkpoint(path,payload):
    """Bounded Windows sharing-violation retry, preserving old atomic target."""
    for attempt in range(7):
        try:write_json(path,payload);return
        except PermissionError:
            if attempt==6:raise
            time.sleep(.02*2**attempt)


def segment(games,roster,params,num,left,right,emit_start,policy,years,job,cfg,guard,
            emit_ids=None,collect_sim=False,resume=True):
    """A fresh prior for this left boundary. Warmup outputs never published."""
    requested=time.perf_counter();job=Path(job);job.mkdir(parents=True,exist_ok=True)
    task=dict(left=left,right=right,emit_start=emit_start,policy=policy,years=years,
              history_sha=fingerprint(games),roster=sorted(roster),params=params,numerics=num)
    digest=fingerprint(task)
    if (job/'complete.json').exists():
        m=read_json(job/'complete.json')
        if m['task_sha']!=digest:raise ValueError('JOB_IDENTITY_MISMATCH')
        for name,h in m['outputs'].items():
            if file_hash(job/name)!=h:raise ValueError('JOB_OUTPUT_CHANGED')
        TASK_REQUESTS.append(dict(job=str(job),source='verified_cache',request_seconds=time.perf_counter()-requested))
        return read_json(job/'features.json'),read_json(job/'pairs.json'),read_json(job/'final_state.json'),read_json(job/'telemetry.json')
    engine=CollapsedJumpFilter(roster,params,num,1.,.25);out=[];pairs=[];done=0;prior_seconds=0.;begin=time.perf_counter()
    if resume and (job/'checkpoint.json').exists():
        cp=read_json(job/'checkpoint.json')
        if cp['task_sha']!=digest:raise ValueError('CHECKPOINT_IDENTITY_MISMATCH')
        engine=CollapsedJumpFilter.restore(cp['state']);out=cp['features'];pairs=cp['pairs'];done=cp['dates'];prior_seconds=cp['seconds']
    grouped=defaultdict(list)
    for g in games:
        if left<=g['date']<right:grouped[g['date']].append(g)
    history=sorted(grouped)
    def checkpoint():
        write_checkpoint(job/'checkpoint.json',dict(task_sha=digest,state=engine.state(),features=out,pairs=pairs,
            dates=done,seconds=prior_seconds+time.perf_counter()-begin))
    peak=psutil.Process().memory_info().rss/2**20
    try:
        for day in history:
            if engine.last_day and day<=engine.last_day:continue
            guard.check(begin-prior_seconds)
            batch=grouped[day];before=engine.last_day
            mus={t:params['jump_rate']*(date.fromisoformat(day)-date.fromisoformat(engine.last.get(t,day))).days/365.2425
                 for t in {g[k] for g in batch for k in ('home','away')}}
            pending_pairs=[]
            if collect_sim and day>=emit_start:
                from itertools import combinations
                for a,b in combinations(sorted(roster),2):
                    pending_pairs.append(dict(date=day,home=a,away=b,difference=float(engine.mean[engine.index[a]]-engine.mean[engine.index[b]]),
                        home_mean=float(engine.mean[engine.index[a]]),away_mean=float(engine.mean[engine.index[b]]),
                        home_variance=float(engine.cov[engine.index[a],engine.index[a]]+(params['q']/params['jump_rate']+params['jump_sd']**2)*mus[a]),
                        away_variance=float(engine.cov[engine.index[b],engine.index[b]]+(params['q']/params['jump_rate']+params['jump_sd']**2)*mus[b]),
                        prediction_cutoff=before or 'initial_prior'))
            rr=engine.day(day,batch);done+=1
            if day>=emit_start:
                selected=[r for r in rr if emit_ids is None or r['match_id'] in emit_ids]
                out.extend(features(selected,day,before,params,left,policy,years,mus));pairs.extend(pending_pairs)
            peak=max(peak,psutil.Process().memory_info().rss/2**20)
            if done%cfg['checkpoint_dates']==0:checkpoint()
        for name,v in [('features.json',out),('pairs.json',pairs),('final_state.json',engine.state())]:write_json(job/name,v)
        telemetry=dict(policy=policy,years=years,left=left,right=right,history_rows=sum(map(len,grouped.values())),history_dates=len(history),
            emitted_rows=len(out),seconds=prior_seconds+time.perf_counter()-begin,peak_rss_mib=peak,
            resumed=prior_seconds>0,prior_checkpoint_seconds=prior_seconds,phase_guard='cooperative checks before each full date, not hard process kill')
        write_json(job/'telemetry.json',telemetry)
        write_json(job/'complete.json',dict(task_sha=digest,outputs={n:file_hash(job/n) for n in ('features.json','pairs.json','final_state.json','telemetry.json')}))
        TASK_REQUESTS.append(dict(job=str(job),source='computed',request_seconds=time.perf_counter()-requested))
        return out,pairs,read_json(job/'final_state.json'),telemetry
    except Exception as e:
        # A failure inside the numerical update may have mutated the engine:
        # preserve the last *committed* checkpoint instead of saving a bad state.
        write_json(job/'failure.json',dict(error_type=type(e).__name__,error=str(e),last_committed_checkpoint=(job/'checkpoint.json').exists(),
                                        last_day_before_attempt=before if 'before' in locals() else engine.last_day))
        raise


def annual_job(games,roster,params,num,year,years,store,cfg,guard,emit_ids=None,collect_sim=False,start='1950-01-01'):
    left=max(start,f'{year-years}-01-01');policy=f'annual_reset_{years}y'
    return segment(games,roster,params,num,left,f'{year+1}-01-01',f'{year}-01-01',policy,years,
                   Path(store)/f'{year}-{years}y',cfg,guard,emit_ids,collect_sim)


def adapt_facts(facts,feature_rows,policy_id):
    lookup={r['match_id']:r for r in feature_rows}
    if len(lookup)!=len(feature_rows) or set(lookup)!={r['match_id'] for r in facts}:raise ValueError('POLICY_FEATURE_IDS_MISMATCH')
    result=[]
    for r in facts:
        s=lookup[r['match_id']]
        if s['date']!=r['date'] or s['home']!=r['home_rating_entity'] or s['away']!=r['away_rating_entity']:raise ValueError('POLICY_IDENTITY_MISMATCH')
        if s['prediction_cutoff']=='initial_prior':
            if s['home_history'] or s['away_history']:raise ValueError('INVALID_INITIAL_PRIOR_CUTOFF')
        elif s['prediction_cutoff']>=s['date']:raise ValueError('FUTURE_POLICY_FEATURE')
        if s['difference_base_variance']<=0 or abs(s['difference_variance']-s['difference_base_variance']-
            (s['home_jump_intensity']+s['away_jump_intensity'])*s['jump_scale_sd']**2)>2e-8:raise ValueError('POLICY_DISTRIBUTION_INVALID')
        q=dict(r,strength_difference=s['difference'],strength_difference_variance=s['difference_variance'],
            strength_difference_base_variance=s['difference_base_variance'],home_jump_intensity=s['home_jump_intensity'],
            away_jump_intensity=s['away_jump_intensity'],jump_scale_sd=s['jump_scale_sd'],home_variance=s['home_variance'],
            away_variance=s['away_variance'],home_away_covariance=s['home_away_covariance'],home_history=s['home_history'],
            away_history=s['away_history'],cold_start=s['cold_start'],previously_disconnected=s['previously_disconnected'],
            rating_run_id=policy_id,raw_rating_run_id=policy_id,prediction_cutoff=s['prediction_cutoff'],
            rating_rules_version='q6-annual-reset-v1',initialization_status='not_recomputed')
        for k in ('initialization_raw_probability_max_change','initialization_sensitive','initialization_gap_min','initialization_gap_max'):q[k]=None
        result.append(q)
    return result
