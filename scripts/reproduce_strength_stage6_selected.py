"""Repeat one full marginal M4 fit and one rank-restricted M3 fit; not all13."""
from pathlib import Path
import argparse,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import file_hash,write_json
from src.strength_stage6_sensitivity import read,altered_rows,EstimableDesign
from src.strength_joint.contract import load
from src.strength_joint.design import Design
from src.strength_joint.model import fit,predict


def run(fit_only=False,compare_only=False):
    started=time.perf_counter();log=ROOT/'outputs/logs/strength_stage6'
    cfg=json.loads((ROOT/'config/strength_stage6_sensitivity.json').read_text());prep=ROOT/cfg['preparation']
    jc,rows,_,_,_=load();base=Design(rows)
    ready=json.loads((prep/'readiness.json').read_text());files={r['variant_id']:r['prepared_file'] for r in ready['score_variants']}
    checks=[]
    keys=['repaired-initialization-d1f3771999bd8731b716:M4_type_slope','exclude_unknown_geography:M3_nested']
    checkpoint=log/'selected_refit_results.json'
    repeated=json.loads(checkpoint.read_text()) if compare_only else dict(results={},config_sha256=file_hash(ROOT/'config/strength_stage6_sensitivity.json'))
    if repeated['config_sha256']!=file_hash(ROOT/'config/strength_stage6_sensitivity.json'):raise ValueError('Repeat config changed')
    if not compare_only:
        for key in keys:
            label,model=key.split(':');data=altered_rows(rows,read(prep/files.get(label,files['baseline'])))
            if label=='exclude_unknown_geography':
                flags={r['match_id']:r for r in read(prep/'baseline_flags.csv.gz')}
                data=[r for r in data if flags[r['match_id']]['unknown_home']!='true' and flags[r['match_id']]['unknown_away']!='true']
            design=EstimableDesign(base,data,model,cfg['rowspace_tolerance'])
            print('REPEATING',key,len(data),flush=True)
            repeated['results'][key]=fit(data,design,model,jc['numerics'])
        repeated['fit_seconds']=time.perf_counter()-started;repeated['source_sha256']=file_hash(Path(__file__))
        write_json(checkpoint,repeated)
    if fit_only:return
    if repeated['source_sha256']!=file_hash(Path(__file__)):raise ValueError('Repeat source changed')
    dest=ROOT/json.loads((log/'sensitivity_pointer.json').read_text())['directory'];models=json.loads((dest/'models.json').read_text())
    for key in keys:
        previous=models[key];label=previous['variant_id'];model=previous['model_id']
        data=altered_rows(rows,read(prep/files.get(label,files['baseline'])))
        if label=='exclude_unknown_geography':
            flags={r['match_id']:r for r in read(prep/'baseline_flags.csv.gz')}
            data=[r for r in data if flags[r['match_id']]['unknown_home']!='true' and flags[r['match_id']]['unknown_away']!='true']
        design=EstimableDesign(base,data,model,cfg['rowspace_tolerance'])
        result=repeated['results'][key]
        a=predict(previous,data,design);b=predict(result,data,design)
        report=dict(fit_id=key,estimation_rows=len(data),loss_error=abs(result['loss']-previous['loss']),
                    max_parameter_error=float(np.max(abs(np.array(result['theta'])-previous['theta']))),
                    max_probability_error=float(np.max(abs(a-b))),
                    coefficient_names_identical=result['names']==previous['names'],
                    dropped_columns=design.dropped,both_numeric_gates_passed=result['numerical_fit_passed'] and previous['numerical_fit_passed'])
        report['passed']=report['loss_error']<1e-10 and report['max_parameter_error']<1e-7 and report['max_probability_error']<2e-8 and report['coefficient_names_identical'] and report['both_numeric_gates_passed']
        checks.append(report);print(json.dumps(report),flush=True)
    out=dict(passed=all(r['passed'] for r in checks),scope='two selected refits, three starts each; not all13 or byte-repeat of contrast package',
             source_manifest=dest.relative_to(ROOT).as_posix()+'/manifest.json',source_manifest_sha256=file_hash(dest/'manifest.json'),
             audit_script_sha256=file_hash(Path(__file__)),refit_seconds=repeated['fit_seconds'],comparison_seconds=time.perf_counter()-started,results=checks,human_review=False)
    write_json(log/'selected_refit_reproducibility.json',out)
    if not out['passed']:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--fit-only',action='store_true');g.add_argument('--compare-only',action='store_true');a=p.parse_args()
    run(a.fit_only,a.compare_only)
