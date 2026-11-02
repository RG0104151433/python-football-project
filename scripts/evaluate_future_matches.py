"""Score sealed forecasts against separately confirmed, already-played results.

Results CSV: match_id, home_score, away_score, final_confirmed,
observed_at_utc, source_url. Does not modify issued forecasts or auto-tune models.
"""
import argparse
from datetime import datetime,timezone,timedelta
import math,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data_contract import file_hash,fingerprint,write_json,atomic_bytes,csv_bytes
from src.strength.io import ROOT,read_rows


def score_results(forecasts,results,now):
    by={r['match_id']:r for r in forecasts};seen=set();out=[]
    for r in results:
        mid=r['match_id']
        if mid not in by or mid in seen:raise ValueError('UNKNOWN_OR_DUPLICATE_RESULT')
        seen.add(mid);f=by[mid]
        kick=datetime.fromisoformat(f['date']+'T'+f['kickoff_cet']).replace(tzinfo=timezone(timedelta(hours=1)))
        observed=datetime.fromisoformat(r['observed_at_utc'])
        if observed.tzinfo is None or now<kick or observed<kick or observed>now:
            raise ValueError('RESULT_NOT_YET_AVAILABLE')
        if r['final_confirmed'].lower()!='true' or not r['source_url'].startswith('https://'):
            raise ValueError('UNCONFIRMED_RESULT')
        if not r['home_score'].isdigit() or not r['away_score'].isdigit():raise ValueError('INVALID_SCORE')
        hs,aws=int(r['home_score']),int(r['away_score']);outcome=0 if hs>aws else 1 if hs==aws else 2;y=int(outcome==0)
        native=[float(f[k]) for k in ['native_home_probability','native_draw_probability','native_away_probability']]
        row=dict(match_id=mid,date=f['date'],round=f['round'],home_score=hs,away_score=aws,
            home_win=y,source_url=r['source_url'],observed_at_utc=r['observed_at_utc'],
            joint_binary_log_loss=None,reference_binary_log_loss=None,joint_minus_reference_loss=None,
            native_auxiliary_threeway_log_loss=-math.log(max(1e-6,native[outcome])))
        if f['main_home_probability']:
            p=float(f['main_home_probability']);b=float(f['strength_reference_home_probability'])
            loss=-math.log(max(1e-6,p if y else 1-p));ref=-math.log(max(1e-6,b if y else 1-b))
            row.update(joint_binary_log_loss=loss,reference_binary_log_loss=ref,joint_minus_reference_loss=loss-ref)
        out.append(row)
    return out


def run(result_path,run_id=None):
    pointer=json.loads((ROOT/'outputs/logs/future_predictions/current.json').read_text())
    rid=run_id or pointer['run_id'];log=ROOT/'outputs/logs/future_predictions'/rid
    manifest=json.loads((log/'manifest.json').read_text(encoding='utf-8-sig'))
    path=f'outputs/tables/future_predictions/{rid}/forecasts.csv'
    if file_hash(ROOT/path)!=manifest['outputs'][path]:raise ValueError('FORECAST_CHANGED')
    source=(ROOT/result_path).resolve()
    if not source.is_relative_to(ROOT.resolve()):raise ValueError('RESULT_OUTSIDE_WORKSPACE')
    forecasts=read_rows(ROOT/path);results=read_rows(source)
    scored=score_results(forecasts,results,datetime.now(timezone.utc))
    if not scored:raise ValueError('NO_CONFIRMED_RESULTS')
    identity=dict(forecast_run=rid,forecast_sha256=file_hash(ROOT/path),results_sha256=file_hash(source),code_sha256=file_hash(Path(__file__)))
    eid='future-evaluation-'+fingerprint(identity)[:20];folder=ROOT/'outputs/logs/future_predictions'/eid
    if (folder/'summary.json').exists():print('EVALUATION_ALREADY_SAVED',eid);return
    folder.mkdir(parents=True,exist_ok=True)
    atomic_bytes(folder/'scored_results.csv',csv_bytes(list(scored[0]),scored))
    valid=[r for r in scored if r['joint_binary_log_loss'] is not None]
    write_json(folder/'summary.json',dict(identity=identity,results_received=len(scored),forecast_matches=len(forecasts),
        pending_matches=len(forecasts)-len(scored),joint_binary_matches=len(valid),
        joint_binary_log_loss=sum(r['joint_binary_log_loss'] for r in valid)/len(valid) if valid else None,
        mean_joint_minus_reference_loss=sum(r['joint_minus_reference_loss'] for r in valid)/len(valid) if valid else None,
        native_auxiliary_threeway_log_loss=sum(r['native_auxiliary_threeway_log_loss'] for r in scored)/len(scored),
        actual_postmatch_evaluation_complete=len(scored)==len(forecasts),human_review=False,formal_inference=False))
    print('EVALUATION_SAVED',eid,'received',len(scored),'pending',len(forecasts)-len(scored))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--results',required=True);p.add_argument('--run-id')
    a=p.parse_args();run(a.results,a.run_id)
