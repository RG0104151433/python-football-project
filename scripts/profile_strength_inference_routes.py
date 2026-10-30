"""Two representative, same-world cost/replay comparisons of A versus B."""
from pathlib import Path
import json,os,sys,time
import numpy as np
from scipy.linalg import block_diag
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_inference import comparison
from src.strength_inference.fast import FrozenTargets
from src.strength_inference.methods import refit_pair,score_geometry
from src.data_contract import write_json,file_hash


if __name__=='__main__':
    cfg,c,folder=comparison.protocol();comparison.initialize(cfg,str(folder));op=FrozenTargets(c)
    output=[]
    for i,(sc,seed) in enumerate([(cfg['scenarios'][0],720000),(cfg['scenarios'][1],820000)]):
        arrays,meta=comparison.cached_world(sc,'calibration',seed);rows=comparison.rows_from(arrays)
        truth=json.loads((folder/sc['id']/'truth.json').read_text());beta0=np.array(truth['theta_M0'])
        m3=comparison._CTX['models']['M3_nested'];theta3=np.array(m3['theta']);value={}
        def route_A():
            start=time.perf_counter();fits=refit_pair(rows,comparison._CTX['design'],c['joint_cfg']['numerics'])
            estimates,_=op.evaluate(fits['M0_nested']['theta'],fits['M3_nested']['theta'],rows)
            known,_=op.evaluate(beta0,theta3,rows)
            value['A_seconds']=time.perf_counter()-start;value['A_error']=estimates-known
            value['models']=fits
        def route_B():
            start=time.perf_counter();_,jac=op.evaluate(beta0,theta3,rows,True)
            fixed={'M0_nested':dict(model_id='M0_nested',theta=beta0.tolist()),'M3_nested':m3}
            hs=[];gs=[]
            for model in ('M0_nested','M3_nested'):
                score,h,_=score_geometry(fixed[model],rows,comparison._CTX['design']);gs.append(score.sum(axis=0));hs.append(h)
            value['B_error']=jac@np.linalg.solve(block_diag(*hs),np.concatenate(gs));value['B_seconds']=time.perf_counter()-start
        if i%2:route_B();route_A()
        else:route_A();route_B()
        saved=json.loads((folder/'fits'/sc['id']/'calibration'/f'{seed}.json').read_text())
        output.append(dict(scenario=sc['id'],seed=seed,generation_seconds=meta['seconds'],A_seconds=value['A_seconds'],B_seconds=value['B_seconds'],
            repeated_A_error_max_difference_pp=float(max(abs(value['A_error']-saved['A_error_pp']))),
            repeated_B_error_max_difference_pp=float(max(abs(value['B_error']-saved['B_linearized_error_pp']))),
            parameter_max_difference=max(float(max(abs(np.array(value['models'][m]['theta'])-saved['models'][m]['theta']))) for m in value['models'])))
        print('PROFILE_ROUTES_COMPLETE',seed,output[-1],flush=True)
    a=float(np.mean([r['A_seconds'] for r in output]));b=float(np.mean([r['B_seconds'] for r in output]));g=float(np.mean([r['generation_seconds'] for r in output]))
    report=dict(representative_worlds=output,A_specific_mean_seconds=a,B_specific_mean_seconds=b,generation_mean_seconds=g,
        B_whole_run_relative_saving=(a-b)/(g+a),scope='two measured worlds under current load; shared setup/truth costs excluded, so B saving is optimistic',
        all_replayed_values_passed=all(max(r['repeated_A_error_max_difference_pp'],r['repeated_B_error_max_difference_pp'])<2e-8 for r in output),
        source_sha256=file_hash(Path(__file__)))
    write_json(ROOT/'outputs/logs/strength_inference/route_timing.json',report);print(json.dumps(report))
    if not report['all_replayed_values_passed']:raise SystemExit(1)
