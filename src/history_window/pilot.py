"""Small, predeclared Q6 feasibility run; no ranking or production release."""
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import io
import json
import platform
import threading
import time
import zipfile
import numpy as np
import psutil
from threadpoolctl import threadpool_limits, threadpool_info
from src.data_contract import atomic_bytes, csv_bytes, file_hash, fingerprint, write_json
from src.strength.io import ROOT, read_rows, environment
from src.strength.global_run import load as load_learning
from src.strength_joint.contract import load as load_analysis
from src.strength_joint.design import Design
from src.strength_joint.model import predict
from src.strength_predictive_validation import fit_past, metrics
from .protocol import training_slice, label, log_losses, paired_radius
from .replay import strict_replay
from .simulation import generate


@contextmanager
def measurement(records, job, budget):
    proc = psutil.Process(); stop = threading.Event(); peak = [proc.memory_info().rss]
    def sample():
        while not stop.wait(.01):
            peak[0] = max(peak[0], proc.memory_info().rss)
    thread = threading.Thread(target=sample, daemon=True); before = time.perf_counter()
    cpu = time.process_time(); baseline = proc.memory_info().rss; status = 'completed'
    thread.start()
    try:
        yield
    except Exception:
        status = 'failed'; raise
    finally:
        stop.set(); thread.join(); peak[0] = max(peak[0], proc.memory_info().rss)
        seconds = time.perf_counter()-before
        records.append(dict(job=job, status=status, seconds=seconds, cpu_seconds=time.process_time()-cpu,
                            baseline_rss_mb=baseline/2**20, sampled_peak_rss_mb=peak[0]/2**20,
                            peak_increment_mb=max(0, peak[0]-baseline)/2**20, memory_sample_seconds=.01,
                            budget_passed=seconds <= budget['max_single_job_seconds'] and peak[0]/2**20 <= budget['max_rss_mb']))


def emit_table(folder, name, rows):
    if not rows:
        raise ValueError('EMPTY_PILOT_TABLE: '+name)
    atomic_bytes(folder/name, csv_bytes(list(rows[0]), rows))


def execute(config_path='config/history_window.json'):
    cfg = json.loads((ROOT/config_path).read_text(encoding='utf-8-sig'))
    if cfg['schema_version'] != 'history-window-v1':
        raise ValueError('UNKNOWN_HISTORY_PROTOCOL')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    code = [*sorted((ROOT/'src/history_window').glob('*.py')), ROOT/'scripts/check_history_window.py',
            ROOT/'scripts/audit_history_window.py', ROOT/'tests/test_history_window.py',
            ROOT/'src/strength_predictive_validation.py', ROOT/'src/data_contract.py',
            *sorted((ROOT/'src/strength').glob('*.py')), *sorted((ROOT/'src/strength_joint').glob('*.py'))]
    identity = dict(config_sha256=file_hash(ROOT/config_path), code={p.relative_to(ROOT).as_posix():file_hash(p) for p in code},
                    environment=environment())
    folder = ROOT/'outputs/logs/history_window'/('feasibility-'+stamp+'-'+fingerprint(identity)[:8])
    folder.mkdir(parents=True, exist_ok=False)
    write_json(folder/'protocol.json', cfg)
    write_json(folder/'started.json', dict(created_at_utc=stamp, identity=identity, protocol_frozen_before_execution=True))
    snapshot = io.BytesIO()
    with zipfile.ZipFile(snapshot, 'w', compression=zipfile.ZIP_STORED) as z:
        for path in code+[ROOT/config_path]:
            z.writestr(zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), (1980,1,1,0,0,0)), path.read_bytes())
    atomic_bytes(folder/'source_snapshot.zip', snapshot.getvalue())
    telemetry=[]; checks=[]; failures=[]; fits={}; forecasts=[]; boundaries=[]; summary=[]
    rating_rows=[]; rating_bounds=[]; included=[]; simulation_rows=[]; truth_rows=[]
    p = cfg['pilot']
    def check(name, passed, details=None):
        checks.append(dict(check=name, passed=bool(passed), details=details))
    with threadpool_limits(limits=p['threads']):
        try:
            joint, rows, _, _, inputs = load_analysis()
            learning_cfg, games, learning_inputs = load_learning('config/strength_global_v3.json')
            score_path = ROOT/'data/processed/strength/jump-ratings-451ecade0bf84ee0bfb6'
            score_manifest = json.loads((score_path/'manifest.json').read_text())
            params=score_manifest['identity']['parameters']; numerics=score_manifest['identity']['numerics']
            inputs.update(learning_inputs)
            inputs[score_path.relative_to(ROOT).as_posix()+'/manifest.json'] = file_hash(score_path/'manifest.json')
            inputs[config_path] = file_hash(ROOT/config_path)
            write_json(folder/'inputs.json', inputs)
            # Boundary ledger for all proposed years: no fitting on evaluation outcomes.
            future_boundary_rows=[]
            for year in range(2000, 2025):
                for w in cfg['candidate_years']:
                    train, ledger=training_slice(rows, year, w, cfg['outcome_start'])
                    future_boundary_rows.append(dict(year=year, window=label(w), **ledger))
            emit_table(folder, 'training_boundaries.csv', future_boundary_rows)
            for year in p['outcome_years']:
                if not cfg['development_years'][0] <= year <= cfg['development_years'][1]:
                    raise ValueError('PILOT_OUTSIDE_DEVELOPMENT')
                test=sorted((r for r in rows if int(r['year'])==year), key=lambda r:(r['date'],r['match_id']))
                for w in p['outcome_windows']:
                    job=f'outcome:{year}:{label(w)}'; print('PILOT_JOB',job,flush=True)
                    with measurement(telemetry, job, p):
                        train, ledger=training_slice(rows,year,w,cfg['outcome_start']); design=Design(train)
                        fitted=fit_past(train,design,cfg['model'],joint['numerics'],cfg['ridge_precision'])
                        pp=predict(fitted,test,design)
                    fits[job]=dict(fitted, encoding_anchors={str(k):v for k,v in design.anchor.items()},
                                   encoding_weights={str(k):v for k,v in design.weights.items()}, uses_test_rows=False)
                    boundaries.append(dict(year=year,window=label(w),**ledger))
                    rr=[dict(match_id=r['match_id'],date=r['date'],year=year,window=label(w),probability=float(prob),
                             home_win=int(r['home_win']),tournament_group=r['tournament_group'],
                             training_max=ledger['actual_max'], rating_cutoff=r['prediction_cutoff']) for r,prob in zip(test,pp)]
                    forecasts.extend(rr)
                    summary.append(dict(year=year,window=label(w),**metrics(rr),
                                        primary_clipped_log_loss=float(log_losses(pp,[int(r['home_win']) for r in test],cfg['probability_clip']).mean())))
                    check(job+':past_only',ledger['actual_max']<f'{year}-01-01' and all(r['prediction_cutoff']<r['date'] for r in train+test))
                    check(job+':probability',np.isfinite(pp).all() and (pp>=0).all() and (pp<=1).all())
            raw=read_rows(score_path/'prematch_features.csv')
            for day in p['rating_dates']:
                targets=[g for g in games if g['date']==day]
                if not 2000 <= int(day[:4]) <= 2009:
                    raise ValueError('PILOT_RATING_OUTSIDE_DEVELOPMENT')
                for w in p['rating_windows']:
                    job=f'rating:{day}:{label(w)}'; print('PILOT_JOB',job,flush=True)
                    with measurement(telemetry,job,p):
                        rr, ledger, _=strict_replay(games,targets,day,w,params,numerics,budget_seconds=p['max_single_job_seconds'])
                    rating_rows.extend(dict(window=label(w),**r) for r in rr)
                    past=[g for g in games if ledger['left_inclusive']<=g['date']<day]
                    included.extend(dict(target_day=day,window=label(w),match_id=g['match_id'],history_date=g['date']) for g in past)
                    rating_bounds.append(dict(target_day=day,window=label(w),**{k:v for k,v in ledger.items() if k!='elapsed_seconds'},
                                              history_id_set_sha256=fingerprint(sorted(g['match_id'] for g in past))))
                    check(job+':membership',len(past)==ledger['history_rows'] and all(ledger['left_inclusive']<=g['date']<day for g in past))
                    check(job+':forecast',all(abs(r['p_home']+r['p_draw']+r['p_away']-1)<p['gate_probability_sum'] and r['difference_base_variance']>0 for r in rr))
                    if day==p['rating_dates'][0] and w==p['rating_windows'][0]:
                        with measurement(telemetry,job+':repeat_mutation',p):
                            changed=[dict(g,outcome=(g['outcome']+1)%3) if not ledger['left_inclusive']<=g['date']<day else g for g in games]
                            changed_targets=[dict(g,outcome=(g['outcome']+2)%3) for g in targets]
                            repeated,_,_=strict_replay(changed,changed_targets,day,w,params,numerics)
                        check(job+':outside_and_current_outcomes_invariant',rr==repeated)
                        with measurement(telemetry,job+':strict_numerics',p):
                            strict,_,_=strict_replay(games,targets,day,w,params,dict(numerics,ep_max_iter=500,ep_tolerance=1e-8,poisson_tail_tolerance=1e-15))
                        err=max(abs(a[k]-b[k]) for a,b in zip(rr,strict) for k in ('p_home','p_draw','p_away'))
                        check(job+':strict_numerical_reference',err<=p['gate_reference_probability'],dict(max_probability_difference=err))
                # Archived cumulative predictions are a distinct policy, never a finite-window checkpoint.
                archived=[r for r in raw if r['date']==day]
                check('cumulative_archive:'+day,{r['match_id'] for r in archived}=={g['match_id'] for g in targets})
            # Independent path generator: bounded smoke scope, not window ranking/coverage admission.
            for seed in p['simulation_seeds']:
                for path in p['simulation_paths']:
                    for link in p['simulation_links']:
                        job=f'simulation:{seed}:{path}:{link}'; print('PILOT_JOB',job,flush=True)
                        gg, tt=generate(seed,path,link,p['simulation_months']); truth_rows.extend(tt)
                        truth={r['match_id']:r for r in tt}
                        with measurement(telemetry,job,p):
                            for month in p['simulation_target_months']:
                                day=tt[2*month]['date']; targets=[g for g in gg if g['date']==day]
                                for w in p['simulation_windows']:
                                    rr,_,_=strict_replay(gg,targets,day,w,params,numerics,start='2000-01-01')
                                    for r in rr:
                                        t=truth[r['match_id']]
                                        simulation_rows.append(dict(seed=seed,path=path,link=link,month=month,window=label(w),
                                            match_id=r['match_id'],date=day,true_difference=t['true_difference'],
                                            estimated_difference=r['difference'],squared_gap_error=(r['difference']-t['true_difference'])**2,
                                            true_home_probability=t['true_home_probability'],estimated_home_probability=r['p_home'],
                                            squared_probability_error=(r['p_home']-t['true_home_probability'])**2,
                                            prediction_cutoff=r['prediction_cutoff'],outcome=t['outcome']))
                        check(job+':finite',all(np.isfinite(r['squared_gap_error']) for r in simulation_rows if r['seed']==seed and r['path']==path and r['link']==link))
            for year in p['outcome_years']:
                sets=[{r['match_id'] for r in forecasts if r['year']==year and r['window']==label(w)} for w in p['outcome_windows']]
                check(f'paired_sample:{year}',len(sets)>0 and all(s==sets[0] for s in sets))
            check('all_job_budgets',all(r['budget_passed'] for r in telemetry))
            check('no_evaluation_period_forecasts',all(int(r['date'][:4])<=2009 for r in forecasts+rating_rows))
            write_json(folder/'models.json',fits)
            for name, rr in [('pilot_predictions.csv',forecasts),('pilot_metrics.csv',summary),('pilot_fit_boundaries.csv',boundaries),
                             ('rating_predictions.csv',rating_rows),('rating_boundaries.csv',rating_bounds),('rating_history_membership.csv',included),
                             ('simulation_truth.csv',truth_rows),('simulation_diagnostics.csv',simulation_rows)]:
                emit_table(folder,name,rr)
        except Exception as exc:
            failures.append(dict(error_type=type(exc).__name__,error=str(exc),admitted=False))
        write_json(folder/'telemetry.json',dict(records=telemetry,threadpools=threadpool_info(),hardware=dict(processor=platform.processor(),
            logical_cpus=psutil.cpu_count(),ram_mb=psutil.virtual_memory().total/2**20),
            scope='wall/cpu and10ms process RSS sampling; warm imports and input loading excluded; no inference of universal runtime or exact OS peak'))
    review=dict(passed=bool(checks) and all(c['passed'] for c in checks) and not failures,checks=checks,failures=failures,
                step1_scope_implemented=True,step2_math_protocol_documented=True,step3_development_feasibility=True,
                new_best_window_selected=False,production_window_comparison_completed=False,
                independent_human_review=False,development_reused=True,new_blind_holdout=False,
                conditional_bound_example_radius=paired_radius([1,2,3],cfg['probability_clip']),
                fit_count=len(fits),prediction_rows=len(forecasts),rating_prediction_rows=len(rating_rows),
                simulated_histories=len(p['simulation_seeds'])*len(p['simulation_paths'])*len(p['simulation_links']),
                simulation_diagnostic_rows=len(simulation_rows))
    write_json(folder/'review.json',review)
    manifest=dict(identity=identity,outputs={f.name:file_hash(f) for f in folder.iterdir() if f.is_file()})
    write_json(folder/'manifest.json',manifest)
    # Only successful run can update current pointer. All failed runs remain on disk.
    if review['passed']:
        write_json(ROOT/'outputs/logs/history_window/feasibility_pointer.json',dict(directory=folder.relative_to(ROOT).as_posix(),
            manifest_sha256=file_hash(folder/'manifest.json'),decision_log_id=cfg['decision_log_id'],production_admitted=False))
    print('PILOT_COMPLETE',folder.relative_to(ROOT).as_posix(),json.dumps({k:v for k,v in review.items() if k not in ('checks','failures')}),flush=True)
    if not review['passed']:
        raise RuntimeError('HISTORY_FEASIBILITY_NOT_PASSED: '+str(folder))
    return folder
