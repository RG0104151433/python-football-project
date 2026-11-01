"""Six fixed combinations, four verified dependencies and fifty new annual fits.

Only Q6 step6 route steps1/2. No scoring replay, search, simulation or inference.
"""
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import io,time,threading,zipfile
import numpy as np
import psutil
from threadpoolctl import threadpool_limits
from src.data_contract import atomic_bytes,csv_bytes,file_hash,fingerprint,write_json
from src.strength.io import ROOT,environment,read_rows
from src.strength_joint.design import Design
from src.strength_joint.model import predict
from src.strength_predictive_validation import fit_past
from .contracts import read_json,id_digest
from .protocol import training_slice,label


def combination_id(rating,window):
    return rating+'__outcome_'+label(window)


def legal_cutoffs(rows):
    return all(r['prediction_cutoff']=='initial_prior' or r['prediction_cutoff']<r['date'] for r in rows)


def fit_annual(rows,year,rating,cfg,numerics):
    train,boundary=training_slice(rows,year,12,cfg['outcome_start'])
    now=sorted((r for r in rows if int(r['year'])==year),key=lambda r:(r['date'],r['match_id']))
    if not now or not legal_cutoffs(train+now):raise ValueError('INVALID_JOINT_DATE_OR_CUTOFF')
    started=time.perf_counter();cpu=time.process_time();peak=[psutil.Process().memory_info().rss];stop=threading.Event()
    def sample():
        while not stop.wait(.01):peak[0]=max(peak[0],psutil.Process().memory_info().rss)
    sampler=threading.Thread(target=sample,daemon=True);sampler.start()
    try:
        design=Design(train);model=fit_past(train,design,cfg['model'],numerics,cfg['ridge_precision'])
        fit_seconds=time.perf_counter()-started;begin_predict=time.perf_counter();pp=predict(model,now,design)
        if not model['numerical_fit_passed'] or not np.isfinite(pp).all() or np.any((pp<0)|(pp>1)):
            raise ValueError('JOINT_NUMERICAL_GATE')
        rr=[dict(match_id=r['match_id'],date=r['date'],year=year,era=r['era'],tournament_group=r['tournament_group'],
            home_region=r['home_region'],home_win=int(r['home_win']),probability=float(f"{float(p):.{cfg['probability_storage_decimals']}f}"),
            training_min=boundary['actual_min'],training_max=boundary['actual_max'],rating_cutoff=r['prediction_cutoff']) for r,p in zip(now,pp)]
        predict_seconds=time.perf_counter()-begin_predict
    finally:
        stop.set();sampler.join();peak[0]=max(peak[0],psutil.Process().memory_info().rss)
    elapsed=time.perf_counter()-started
    if elapsed>cfg['max_single_job_seconds'] or peak[0]/2**20>cfg['max_rss_mib']:raise RuntimeError('JOINT_RESOURCE_GATE')
    model=dict(model,training_id_set_sha256=id_digest(train),
        encoding_weights={s+':'+g+':'+u:v for (s,g,u),v in design.weights.items()})
    boundary.update(year=year,combination_id=combination_id(rating,12),training_ids_sha256=id_digest(train),
        target_ids_sha256=id_digest(now),target_rows=len(now),same_year_training_rows=0,
        preceding_year_rows=sum(int(r['year'])==year-1 for r in train),encoding_uses_target_rows=False)
    telemetry=dict(year=year,combination_id=combination_id(rating,12),fit_seconds=fit_seconds,predict_seconds=predict_seconds,
        total_seconds=elapsed,cpu_seconds=time.process_time()-cpu,sampled_peak_rss_mib=peak[0]/2**20,
        memory_sampling_seconds=.01,training_rows=len(train),target_rows=len(now),fresh_fit=True)
    return rr,model,boundary,telemetry


def load_job(folder,task_sha):
    completion=read_json(folder/'complete.json')
    if completion['task_sha256']!=task_sha or file_hash(folder/'bundle.json')!=completion['bundle_sha256']:
        raise ValueError('JOINT_CHECKPOINT_CHANGED')
    return read_json(folder/'bundle.json')


def prepare(config_path):
    cfg=read_json(ROOT/config_path);inputs={config_path:file_hash(ROOT/config_path)};sources={}
    if cfg['schema_version']!='history-window-joint-v1' or cfg['outcome_windows']!=[12,None] or (cfg['first_year'],cfg['last_year'])!=(2000,2024):
        raise ValueError('JOINT_PROTOCOL_MISMATCH')
    def take(path,expected=None):
        h=file_hash(ROOT/path)
        if expected is not None and h!=expected:raise ValueError('DEPENDENCY_CHANGED:'+path)
        inputs[path]=h
    for kind,key in [('rating','rating_run'),('outcome','outcome_run')]:
        folder=ROOT/'outputs/logs/history_window'/cfg[key];man=read_json(folder/'manifest.json');adopt=read_json(folder/'adoption.json')
        take((folder/'manifest.json').relative_to(ROOT).as_posix(),adopt['manifest_sha256'])
        audit_key='audit_sha256' if kind=='rating' else 'independent_audit_sha256'
        take((folder/'independent_audit.json').relative_to(ROOT).as_posix(),adopt[audit_key])
        if not read_json(folder/'independent_audit.json')['passed']:raise ValueError('DEPENDENCY_NOT_ADMITTED')
        take((folder/'adoption.json').relative_to(ROOT).as_posix())
        numerical=[p for p in man['identity']['code'] if p.startswith('src/strength_joint/') or p in ('src/strength_predictive_validation.py','src/history_window/protocol.py')]
        for p in numerical:
            if file_hash(ROOT/p)!=man['identity']['code'][p]:raise ValueError('DEPENDENCY_MODEL_CODE_CHANGED:'+p)
        def used(path):take(path,man['outputs'][path])
        protocol=(folder/'protocol.json').relative_to(ROOT).as_posix();used(protocol);pcfg=read_json(ROOT/protocol)
        if pcfg['model']!=cfg['model'] or pcfg['ridge_precision']!=cfg['ridge_precision']:raise ValueError('DEPENDENCY_MODEL_RULES_CHANGED')
        table='outputs/tables/history_window/'+cfg[key]
        selected=[(folder/('rating_models.json' if kind=='rating' else 'models.json')).relative_to(ROOT).as_posix(),
                  table+('/rating_predictions.csv' if kind=='rating' else '/predictions.csv'),
                  table+('/rating_metrics.csv' if kind=='rating' else '/group_metrics.csv')]
        if kind=='rating':selected.append((folder/'real_features.json').relative_to(ROOT).as_posix())
        for p in selected:used(p)
        sources[kind]=dict(manifest=man,folder=folder,table=table,models=read_json(ROOT/selected[0]),predictions=read_rows(ROOT/selected[1]),metrics=read_rows(ROOT/selected[2]))
    dev=sorted((r for r in sources['rating']['metrics'] if r['group']=='development' and r['policy_name']!='cumulative_1950'),
        key=lambda r:(float(r['primary_log_loss']),int(r['policy_name'].split('_')[-1][:-1])))[:2]
    other=min((r for r in sources['outcome']['metrics'] if r['group']=='development' and r['window']!='cumulative'),key=lambda r:(float(r['primary_log_loss']),int(r['window'][:-1])))
    if [r['policy_name'] for r in dev]+['cumulative_1950']!=cfg['rating_candidates'] or other['window']!='12y':raise ValueError('PREDECLARED_CANDIDATES_CHANGED')
    delivery=read_json(sources['rating']['folder']/'real_features.json');policies={}
    shared='config/strength_joint.json'
    for source in sources.values():take(shared,source['manifest']['identity']['inputs'][shared])
    joint_cfg=read_json(ROOT/shared);base_path=joint_cfg['input']+'/analysis_matches.csv'
    for source in sources.values():
        recorded=source['manifest']['identity']['inputs'];parent_path=joint_cfg['input']+'/manifest.json'
        take(parent_path,recorded[parent_path])
        take(base_path,recorded.get(base_path,read_json(ROOT/parent_path)['outputs']['analysis_matches.csv']))
    facts=read_rows(ROOT/base_path);facts={r['match_id']:r for r in facts}
    immutable=['date','year','home_win','outcome','era','tournament_group','home_region','away_region','home_unit','away_unit','home_rating_entity','away_rating_entity']
    score_fields=['strength_difference','strength_difference_base_variance','home_jump_intensity','away_jump_intensity','jump_scale_sd']
    for name in cfg['rating_candidates']:
        path=delivery['policies'][name]+'/analysis_matches.csv';take(path,sources['rating']['manifest']['outputs'][path]);rr=read_rows(ROOT/path)
        if len(rr)!=24917 or len({r['match_id'] for r in rr})!=24917 or {r['match_id'] for r in rr}!=facts.keys():raise ValueError('POLICY_MATCH_SET_CHANGED')
        if not legal_cutoffs(rr) or any(any(r[k]!=facts[r['match_id']][k] for k in immutable) for r in rr):raise ValueError('POLICY_FACT_OR_TIME_CHANGED')
        if name=='cumulative_1950' and any(any(float(r[k])!=float(facts[r['match_id']][k]) for k in score_fields) for r in rr):raise ValueError('CUMULATIVE_FEATURES_NOT_EQUIVALENT')
        policies[name]=sorted(rr,key=lambda r:(r['date'],r['match_id']))
    return cfg,inputs,sources,policies,joint_cfg['numerics']


def run(config_path='config/history_window_joint.json',plan_only=False):
    cfg,inputs,sources,policies,numerics=prepare(config_path)
    code=[ROOT/'src/history_window/joint.py',ROOT/'src/history_window/contracts.py',ROOT/'src/history_window/protocol.py',
          ROOT/'src/strength_predictive_validation.py',ROOT/'src/strength/io.py',ROOT/'src/data_contract.py',
          ROOT/'scripts/analyze_history_window.py',ROOT/'tests/test_history_window_joint.py',*sorted((ROOT/'src/strength_joint').glob('*.py'))]
    identity=dict(protocol=cfg,inputs=inputs,code={p.relative_to(ROOT).as_posix():file_hash(p) for p in code},environment=environment())
    rid='joint-'+fingerprint(identity)[:20];log=ROOT/'outputs/logs/history_window'/rid;table=ROOT/'outputs/tables/history_window'/rid
    if (log/'manifest.json').exists():
        for p,h in read_json(log/'manifest.json')['outputs'].items():
            if file_hash(ROOT/p)!=h:raise ValueError('JOINT_OUTPUT_CHANGED:'+p)
        print('JOINT_PREDICTIONS_VERIFIED_COMPLETE',rid,flush=True);return log,table
    log.mkdir(parents=True,exist_ok=True);table.mkdir(parents=True,exist_ok=True)
    if not (log/'started.json').exists():
        write_json(log/'started.json',dict(identity=identity,started_at_utc=datetime.now(timezone.utc).isoformat(),frozen_before_new_fits=True))
        write_json(log/'protocol.json',cfg);buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
            for p in code+[ROOT/config_path]:z.writestr(zipfile.ZipInfo(p.relative_to(ROOT).as_posix(),(1980,1,1,0,0,0)),p.read_bytes())
        atomic_bytes(log/'source_snapshot.zip',buf.getvalue())
    plan=[]
    for rating in cfg['rating_candidates']:
        for window in cfg['outcome_windows']:
            fresh=window is not None and rating!='cumulative_1950';source=cfg['rating_run'] if window is None else (rid if fresh else cfg['outcome_run'])
            plan.append(dict(combination_id=combination_id(rating,window),rating_policy=rating,outcome_window=label(window),
                execution='new_fit' if fresh else 'verified_reuse',source_run_id=source,annual_models=25,
                prediction_rows=16599,baseline=rating=='cumulative_1950' and window is None))
    atomic_bytes(table/'combination_plan.csv',csv_bytes(list(plan[0]),plan))
    write_json(log/'plan.json',dict(combinations=plan,total_combinations=6,reused_combinations=4,new_combinations=2,new_annual_fits=50,
        sample_size=16599,rating_replays=0,simulations=0,selection_period='2000-2009',main_evaluation_period='2010-2024'))
    if plan_only:print('JOINT_PLAN_FROZEN',rid,'6 combinations; 4 reused; 50 new annual fits',flush=True);return log,table
    predictions=[];boundaries=[];telemetry=[];new_models={};computed=0;cached=0;begin=time.perf_counter()
    source_predictions={kind:defaultdict(list) for kind in sources}
    for r in sources['rating']['predictions']:source_predictions['rating'][r['policy_name'],int(r['year'])].append(r)
    for r in sources['outcome']['predictions']:source_predictions['outcome'][r['window'],int(r['year'])].append(r)
    try:
        with threadpool_limits(limits=cfg['threads']):
            for item in plan:
                rating=item['rating_policy'];combo=item['combination_id'];window=None if item['outcome_window']=='cumulative' else 12;data=policies[rating]
                for year in range(2000,2025):
                    train,b=training_slice(data,year,window,cfg['outcome_start']);now=[r for r in data if int(r['year'])==year]
                    target={r['match_id']:r for r in now};source_key=''
                    if item['execution']=='new_fit':
                        if time.perf_counter()-begin>cfg['max_run_seconds']:raise TimeoutError('JOINT_PHASE_BUDGET')
                        job=log/'jobs'/combo/str(year);task=fingerprint(dict(combo=combo,year=year,train=id_digest(train),target=id_digest(now)))
                        if (job/'complete.json').exists():payload=load_job(job,task);cached+=1
                        else:
                            print('JOINT_FIT',rating,year,flush=True);rr,m,bb,t=fit_annual(data,year,rating,cfg,numerics)
                            payload=dict(predictions=rr,model=m,boundary=bb,telemetry=t);write_json(job/'bundle.json',payload)
                            write_json(job/'complete.json',dict(task_sha256=task,bundle_sha256=file_hash(job/'bundle.json')));computed+=1
                        rr=payload['predictions'];m=payload['model'];tt=payload['telemetry'];source_key=combo+':'+str(year);new_models[source_key]=m
                    else:
                        kind='rating' if window is None else 'outcome';source_key=f'{rating}:{year}:context_cumulative' if kind=='rating' else f'{year}:12y'
                        rr=source_predictions[kind][rating if kind=='rating' else '12y',year];m=sources[kind]['models'][source_key]
                        tt=dict(year=year,combination_id=combo,fit_seconds=None,predict_seconds=None,total_seconds=None,cpu_seconds=None,
                            sampled_peak_rss_mib=None,memory_sampling_seconds=None,training_rows=len(train),target_rows=len(now),fresh_fit=False)
                    model_train=m.get('training_ids_sha256',m.get('training_id_set_sha256'))
                    if model_train!=id_digest(train):raise ValueError('MODEL_TRAINING_MEMBERSHIP_CHANGED:'+combo+str(year))
                    if len(rr)!=len(now) or {r['match_id'] for r in rr}!=target.keys():raise ValueError('COMBINATION_YEAR_SAMPLE_MISMATCH')
                    for r in sorted(rr,key=lambda r:(r['date'],r['match_id'])):
                        f=target[r['match_id']];p=float(r['probability'])
                        if r['date']!=f['date'] or int(r['home_win'])!=int(f['home_win']) or not np.isfinite(p) or not 0<=p<=1:
                            raise ValueError('INVALID_COMBINATION_FORECAST')
                        if r['training_min']!=b['actual_min'] or r['training_max']!=b['actual_max'] or r['rating_cutoff']!=f['prediction_cutoff']:
                            raise ValueError('COMBINATION_BOUNDARY_CHANGED')
                        predictions.append(dict(combination_id=combo,rating_policy=rating,rating_policy_id=f['rating_run_id'],
                            outcome_window=label(window),**{k:r[k] for k in ('match_id','date','era','tournament_group','home_region')},year=year,
                            home_win=int(r['home_win']),probability=p,model_key=combo+':'+str(year),source_run_id=item['source_run_id'],
                            source_model_key=source_key,training_min=r['training_min'],training_max=r['training_max'],rating_cutoff=r['rating_cutoff']))
                    boundaries.append(dict(combination_id=combo,year=year,outcome_window=label(window),**b,
                        training_ids_sha256=id_digest(train),target_ids_sha256=id_digest(now),target_rows=len(now),same_year_training_rows=0,
                        preceding_year_rows=sum(int(r['year'])==year-1 for r in train),encoding_uses_target_rows=False,
                        execution=item['execution'],source_run_id=item['source_run_id'],source_model_key=source_key))
                    telemetry.append(tt)
        if len(predictions)!=99594 or len(new_models)!=50 or len(boundaries)!=150:raise ValueError('JOINT_COMPLETENESS_FAILED')
        for filename,rr in [('predictions.csv',predictions),('training_boundaries.csv',boundaries)]:atomic_bytes(table/filename,csv_bytes(list(rr[0]),rr))
        write_json(log/'new_models.json',new_models)
        write_json(log/'telemetry.json',dict(records=telemetry,fresh_fits_this_invocation=computed,cached_new_fits=cached,
            reused_existing_annual_models=100,wall_seconds_this_invocation=time.perf_counter()-begin,
            newly_fitted_job_seconds=sum(t['total_seconds'] for t in telemetry if t['fresh_fit']),
            reused_model_cost_is_not_zero=True,no_performance_or_cost_ranking=True))
        write_json(log/'generation_checks.json',dict(passed=True,combinations=6,common_matches=16599,prediction_rows=99594,
            new_prediction_rows=33198,reused_prediction_rows=66396,annual_models=150,new_model_fits=50,
            source_artifact_hashes_checked=True,source_model_code_checked=True,training_membership_checked=True,
            same_match_labels_and_cutoffs_checked=True,numerical_fit_gates_unchanged=True,
            rating_replays=0,simulations=0,steps_completed=[1,2],step3_comparison_pending=True,step4_final_review_pending=True,
            formal_inference=False,human_review=False))
        outputs={p.relative_to(ROOT).as_posix():file_hash(p) for folder in (log,table) for p in folder.iterdir()
                 if p.is_file() and p.name not in ('manifest.json','failure.json')}
        write_json(log/'manifest.json',dict(identity=identity,outputs=outputs,scope='step6 route steps1/2; prediction data ready only'))
        write_json(ROOT/'outputs/logs/history_window/joint_pointer.json',dict(run_id=rid,log_directory=log.relative_to(ROOT).as_posix(),
            table_directory=table.relative_to(ROOT).as_posix(),manifest_sha256=file_hash(log/'manifest.json'),steps_completed=[1,2],
            comparison_pending=True,final_review_pending=True))
    except Exception as e:
        write_json(log/'failure.json',dict(error_type=type(e).__name__,error=str(e),fresh_completed_this_invocation=computed,
            completed_boundaries=len(boundaries),incomplete=True,thresholds_relaxed=False));raise
    print('JOINT_PREDICTIONS_COMPLETE',rid,'50 new annual fits; 4 combinations reused; 99594 predictions',flush=True)
    return log,table
