"""Annual past-only fitting and a result-availability ledger; no self labels."""
from datetime import date,timedelta
import time
import threading
import numpy as np
import psutil
from src.strength_joint.design import Design
from src.strength_joint.model import predict
from src.strength_predictive_validation import fit_past
from .protocol import training_slice,label
from .contracts import id_digest


def fit_year(rows,year,window,cfg,numerics):
    train,boundary=training_slice(rows,year,window,cfg['outcome_start'])
    targets=[r for r in rows if int(r['year'])==year]
    if not targets or any(r['prediction_cutoff']>=r['date'] for r in train+targets):
        raise ValueError('INVALID_TARGET_OR_RATING_CUTOFF')
    proc=psutil.Process();peak=[proc.memory_info().rss];stop=threading.Event()
    def sample():
        while not stop.wait(.01):peak[0]=max(peak[0],proc.memory_info().rss)
    thread=threading.Thread(target=sample,daemon=True);thread.start()
    started=time.perf_counter();cpu=time.process_time()
    try:
        design=Design(train);fitted=fit_past(train,design,cfg['model'],numerics,cfg['ridge_precision'])
        fit_seconds=time.perf_counter()-started;pred_started=time.perf_counter()
        pp=predict(fitted,targets,design)
        if not np.isfinite(pp).all() or np.any((pp<0)|(pp>1)):
            raise ValueError('INVALID_PREDICTION')
        # The persisted probability is the evaluation value, so resume/audit and
        # exact ties never depend on an unrecorded full-precision prediction.
        decimals=cfg['probability_storage_decimals']
        forecasts=[dict(policy_id='outcome-'+label(window),window=label(window),match_id=r['match_id'],date=r['date'],
            year=year,era=r['era'],tournament_group=r['tournament_group'],home_region=r['home_region'],
            home_win=int(r['home_win']),probability=float(f'{float(p):.{decimals}f}'),
            model_key=f'{year}:{label(window)}',training_min=boundary['actual_min'],training_max=boundary['actual_max'],
            rating_cutoff=r['prediction_cutoff'],rating_policy='adopted_Q5_cumulative') for r,p in zip(targets,pp)]
        predicted_seconds=time.perf_counter()-pred_started
    finally:
        stop.set();thread.join();peak[0]=max(peak[0],proc.memory_info().rss)
    seconds=time.perf_counter()-started;rss=peak[0]/2**20
    if seconds>cfg['max_single_job_seconds'] or rss>cfg['max_sampled_rss_mb']:
        raise RuntimeError('OUTCOME_JOB_RESOURCE_GATE')
    fitted['encoding']=dict(anchors={side+':'+region:u for (side,region),u in design.anchor.items()},
        weights={side+':'+region+':'+unit:v for (side,region,unit),v in design.weights.items()},
        uses_test_rows=False,unseen_target_home_units=sum(r['home_unit'] not in design.units.get(('home',r['home_region']),[]) for r in targets),
        unseen_target_away_units=sum(r['away_unit'] not in design.units.get(('away',r['away_region']),[]) for r in targets))
    fitted['training_id_set_sha256']=id_digest(train)
    ledger=dict(year=year,window=label(window),**boundary,training_id_set_sha256=id_digest(train),
        target_id_set_sha256=id_digest(targets),targets=len(targets),
        preceding_year_rows=sum(int(r['year'])==year-1 for r in train),
        same_year_training_rows=0,fit_origin=f'{year}-01-01')
    telemetry=dict(year=year,window=label(window),fit_seconds=fit_seconds,predict_seconds=predicted_seconds,
        total_seconds=seconds,cpu_seconds=time.process_time()-cpu,sampled_peak_rss_mb=rss,
        memory_sampling_seconds=.01,training_rows=len(train),target_rows=len(targets),fresh_fit=True)
    return forecasts,fitted,ledger,telemetry


def feedback_rows(predictions,last_year):
    """Schedule assumptions, not fabricated historical observation timestamps."""
    return [dict(policy_id=r['policy_id'],match_id=r['match_id'],prediction_id=r['policy_id']+':'+r['match_id'],
        prediction_asof_date=r['date'],actual_home_win=r['home_win'],predicted_home_probability=r['probability'],
        result_eligible_from=(date.fromisoformat(r['date'])+timedelta(days=1)).isoformat(),
        next_scheduled_model_refit=f"{int(r['year'])+1}-01-01",
        next_model_refit_within_run=int(r['year'])<last_year,label_source='actual_outcome',
        availability_basis='next-calendar-day conservative retrospective assumption; no precise arrival timestamp',
        rating_feedback_scope='adopted_Q5_pre_date_ratings; not a new rating replay') for r in predictions]
