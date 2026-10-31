"""Stage4 production orchestration; per-job immutable numerical resume cache."""
from datetime import datetime,timezone
from pathlib import Path
import io,json,time,zipfile
from threadpoolctl import threadpool_limits,threadpool_info
from src.data_contract import atomic_bytes,csv_bytes,file_hash,fingerprint,write_json
from src.strength.io import ROOT,environment,read_rows
from .contracts import load_outcome,read_json
from .protocol import label
from .training import fit_year,feedback_rows
from .evaluation import evaluate
from .materials import build


def run(config_path='config/history_window_analysis.json',resume=False,plan_only=False):
    cfg,joint,rows,inputs=load_outcome(config_path)
    tasks=[(year,w) for year in range(cfg['first_year'],cfg['last_year']+1) for w in cfg['windows']]
    if plan_only:
        print(json.dumps(dict(stage='outcome',logical_tasks=len(tasks),expected_predictions=99594,adaptive_predictions=9727,
                              rating_replays=0,threads=cfg['threads']),ensure_ascii=False));return
    files=[*sorted((ROOT/'src/history_window').glob('*.py')),*sorted((ROOT/'src/strength_joint').glob('*.py')),
           ROOT/'src/strength_predictive_validation.py',ROOT/'src/strength/io.py',ROOT/'src/data_contract.py',
           ROOT/'scripts/analyze_history_window.py',ROOT/'scripts/audit_history_window.py',ROOT/'tests/test_history_window_outcome.py']
    identity=dict(protocol=cfg,inputs=inputs,code={p.relative_to(ROOT).as_posix():file_hash(p) for p in files},environment=environment())
    rid='outcome-'+fingerprint(identity)[:20]
    log=ROOT/'outputs/logs/history_window'/rid;table=ROOT/'outputs/tables/history_window'/rid
    if log.exists() and not resume:raise ValueError('RUN_EXISTS_USE_RESUME')
    if (log/'manifest.json').exists():
        for name,h in read_json(log/'manifest.json')['outputs'].items():
            if file_hash(ROOT/name)!=h:raise ValueError('COMPLETED_OUTPUT_CHANGED:'+name)
        print('OUTCOME_ALREADY_COMPLETE_VERIFIED',rid,flush=True)
        return log,table
    log.mkdir(parents=True,exist_ok=True);table.mkdir(parents=True,exist_ok=True)
    if not (log/'started.json').exists():
        write_json(log/'started.json',dict(identity=identity,started_at_utc=datetime.now(timezone.utc).isoformat(),protocol_frozen_before_fits=True))
        write_json(log/'protocol.json',cfg)
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
            for p in files+[ROOT/config_path]:z.writestr(zipfile.ZipInfo(p.relative_to(ROOT).as_posix(),(1980,1,1,0,0,0)),p.read_bytes())
        atomic_bytes(log/'source_snapshot.zip',buf.getvalue())
    predictions=[];models={};boundaries=[];telemetry=[];resumed=0;started=time.perf_counter()
    try:
        with threadpool_limits(limits=cfg['threads']):
            for year,w in tasks:
                key=f'{year}:{label(w)}';job=log/'jobs'/f'{year}-{label(w)}'
                if (job/'complete.json').exists():
                    man=read_json(job/'complete.json')
                    for name,h in man['outputs'].items():
                        if file_hash(job/name)!=h:raise ValueError('JOB_CACHE_CHANGED:'+key)
                    rr=read_json(job/'predictions.json');model=read_json(job/'model.json');ledger=read_json(job/'boundary.json')
                    timing=read_json(job/'telemetry.json');resumed+=1
                else:
                    if time.perf_counter()-started>cfg['max_run_seconds_before_next_job']:
                        raise TimeoutError('RUN_BUDGET_REACHED_BEFORE_NEXT_JOB')
                    print('OUTCOME_FIT',key,flush=True)
                    rr,model,ledger,timing=fit_year(rows,year,w,cfg,joint['numerics'])
                    for name,v in [('predictions.json',rr),('model.json',model),('boundary.json',ledger),('telemetry.json',timing)]:write_json(job/name,v)
                    write_json(job/'complete.json',dict(outputs={p.name:file_hash(p) for p in job.iterdir() if p.is_file()}))
                predictions.extend(rr);models[key]=model;boundaries.append(ledger);telemetry.append(timing)
            products=evaluate(predictions,cfg)
            products['predictions.csv']=predictions
            products['feedback_ledger.csv']=feedback_rows(predictions,cfg['last_year'])
            products['training_boundaries.csv']=boundaries
            for name,rr in products.items():atomic_bytes(table/name,csv_bytes(list(rr[0]),rr))
            write_json(log/'models.json',models)
            write_json(log/'telemetry.json',dict(records=telemetry,total_job_seconds=sum(t['total_seconds'] for t in telemetry),
                logical_tasks=len(tasks),fresh_fits_this_invocation=len(tasks)-resumed,resumed_jobs=resumed,
                elapsed_this_invocation=time.perf_counter()-started,threadpools=threadpool_info(),
                scope='warm imports/input loading excluded; per-job fit/design and prediction plus10ms sampled process RSS'))
            figure_paths=build(table,ROOT/'outputs/figures/history_window'/rid,cfg,products,telemetry)
        review=dict(completed=True,logical_tasks=len(tasks),predictions=len(predictions),adaptive_predictions=len(products['adaptive_predictions.csv']),
                    numerical_gates_passed=all(m['numerical_fit_passed'] for m in models.values()),
                    formal_inference_admitted=False,new_blind_holdout=False,independent_audit_pending=True,
                    ratings_recomputed=False,prior_predictions_overwritten=False)
        if review['predictions']!=99594 or review['adaptive_predictions']!=9727:raise ValueError('OUTPUT_COUNT_MISMATCH')
        write_json(log/'review.json',review)
        outputs={p.relative_to(ROOT).as_posix():file_hash(p) for p in table.iterdir() if p.is_file()}
        outputs.update({p.relative_to(ROOT).as_posix():file_hash(p) for p in figure_paths})
        outputs.update({p.relative_to(ROOT).as_posix():file_hash(p) for p in log.iterdir() if p.is_file() and p.name not in ('manifest.json','failure.json')})
        write_json(log/'manifest.json',dict(identity=identity,outputs=outputs))
        write_json(ROOT/'outputs/logs/history_window/outcome_pointer.json',dict(run_id=rid,log_directory=log.relative_to(ROOT).as_posix(),
            table_directory=table.relative_to(ROOT).as_posix(),manifest_sha256=file_hash(log/'manifest.json'),independent_audit_pending=True))
        print('OUTCOME_COMPLETE',rid,flush=True)
        return log,table
    except Exception as e:
        write_json(log/'failure.json',dict(error_type=type(e).__name__,error=str(e),completed_tasks=len(models),
            failed_job=key if 'key' in locals() else 'aggregation',at_utc=datetime.now(timezone.utc).isoformat(),thresholds_relaxed=False))
        raise
