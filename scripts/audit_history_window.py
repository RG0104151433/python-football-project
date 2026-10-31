"""Independent reconstruction of Q6 feasibility boundaries, metrics and schemas."""
from pathlib import Path
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data_contract import file_hash,write_json,fingerprint
from src.strength.io import ROOT,read_rows


def audit(folder):
    folder=ROOT/folder; checks=[]
    def check(name,value):
        checks.append(dict(check=name,passed=bool(value)))
    man=json.loads((folder/'manifest.json').read_text())
    for name,digest in man['outputs'].items():
        check('hash:'+name,file_hash(folder/name)==digest)
    cfg=json.loads((folder/'protocol.json').read_text())
    source=read_rows(ROOT/'data/processed/strength/joint-preparation-6fa9d025ba40d11cd2f8/analysis_matches.csv')
    preds=read_rows(folder/'pilot_predictions.csv'); metrics=read_rows(folder/'pilot_metrics.csv')
    models=json.loads((folder/'models.json').read_text())
    for m in metrics:
        rr=[r for r in preds if r['year']==m['year'] and r['window']==m['window']]
        actual={r['match_id'] for r in source if r['year']==m['year']}
        check('full_same_year:'+m['year']+m['window'],{r['match_id'] for r in rr}==actual and len(rr)==len(actual))
        loss=0.; brier=0.; correct=0; bias=0
        for r in rr:
            p=float(r['probability']); y=int(r['home_win']); q=min(1-1e-6,max(1e-6,p))
            loss-=y*math.log(q)+(1-y)*math.log1p(-q); brier+=(p-y)**2; correct+=(p>=.5)==y; bias+=p-y
            check('cutoff:'+r['match_id']+r['window'],r['training_max']<r['date'] and r['rating_cutoff']<r['date'])
        for key,value in [('primary_clipped_log_loss',loss/len(rr)),('brier',brier/len(rr)),('binary_accuracy',correct/len(rr)),('calibration_bias_pp',100*bias/len(rr))]:
            check('metric:'+m['year']+m['window']+key,abs(float(m[key])-value)<1e-7)
    learning=read_rows(ROOT/'outputs/logs/strength/learning-b2889411cc93b44f88b6/learning_matches.csv')
    memberships=read_rows(folder/'rating_history_membership.csv')
    for b in read_rows(folder/'rating_boundaries.csv'):
        expected={r['match_id'] for r in learning if b['left_inclusive']<=r['date']<b['right_exclusive']}
        recorded=[r for r in memberships if r['target_day']==b['target_day'] and r['window']==b['window']]
        check('exact_membership:'+b['target_day']+b['window'],{r['match_id'] for r in recorded}==expected and len(recorded)==len(expected)==int(b['history_rows']))
        check('membership_digest:'+b['target_day']+b['window'],fingerprint(sorted(expected))==b['history_id_set_sha256'])
    for b in read_rows(folder/'training_boundaries.csv'):
        expected=[r for r in source if b['left_inclusive']<=r['date']<b['right_exclusive']]
        check('training_boundary:'+b['year']+b['window'],len(expected)==int(b['rows']) and max(r['date'] for r in expected)==b['actual_max'])
    truth={r['match_id']:r for r in read_rows(folder/'simulation_truth.csv')}
    sim=read_rows(folder/'simulation_diagnostics.csv')
    for r in sim:
        t=truth[r['match_id']]
        check('latent_error:'+r['match_id']+r['window'],abs((float(r['estimated_difference'])-float(t['true_difference']))**2-float(r['squared_gap_error']))<1e-8)
    check('simulation_scope',len(truth)==1440 and len(sim)==216)
    check('fit_count',len(models)==6)
    check('pilot_completed',json.loads((folder/'review.json').read_text())['passed'])
    report=dict(passed=all(c['passed'] for c in checks),checks=len(checks),failures=[c for c in checks if not c['passed']],
                run_directory=folder.relative_to(ROOT).as_posix(),human_review=False,formal_window_selection=False)
    write_json(folder/'independent_audit.json',report)
    print(json.dumps(report,ensure_ascii=False))
    if not report['passed']:raise ValueError('HISTORY_AUDIT_FAILED')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run');p.add_argument('--stage',choices=['pilot','outcome'],default='pilot')
    p.add_argument('--refit-examples',action='store_true');args=p.parse_args()
    if args.stage=='outcome':
        from src.history_window.audit_outcome import audit_outcome
        audit_outcome(args.run,args.refit_examples)
    else:
        path=args.run or json.loads((ROOT/'outputs/logs/history_window/feasibility_pointer.json').read_text())['directory']
        audit(path)
