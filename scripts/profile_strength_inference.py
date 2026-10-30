"""Developer equivalence/cost check, not statistical admission."""
from pathlib import Path
import argparse,cProfile,json,pstats,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_inference.contract import load
from src.strength_inference import worlds
from src.strength_inference.fast import query,install_count_cache,FrozenTargets
from src.strength_joint.design import Design
from src.strength_inference.targets import Targets
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.data_contract import write_json

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dates',type=int,default=300);a=p.parse_args()
    c=load();install_count_cache();group={}
    for g in c['games']:group.setdefault(g['date'],[]).append(g)
    games=[g for _,gs in sorted(group.items())[:a.dates] for g in gs]
    engine=CollapsedJumpFilter({g[k] for g in games for k in ('home','away')},c['score_parameters'],c['score_numerics'])
    err=0.;started=time.perf_counter()
    for day,gs in list(sorted(group.items()))[:a.dates]:
        gs=sorted(gs,key=lambda g:g['match_id']);rr,q=worlds.before_day(engine,day,gs);ss,pq=query(engine,day,gs)
        err=max(err,float(np.max(abs(q-pq))));engine.day(day,gs)
    query_seconds=time.perf_counter()-started
    models=json.loads((ROOT/c['cfg']['analysis']/'models.json').read_text())
    started2=time.perf_counter();operator=FrozenTargets(c)
    v,j=operator.evaluate(models['M0_nested']['theta'],models['M3_nested']['theta'],c['rows'],True)
    expected=np.array([float(r['estimate']) for r in c['registry']])
    report=dict(dates=a.dates,query_probability_max_error=err,query_replay_seconds=query_seconds,
        sparse_target_seconds=time.perf_counter()-started2,registered_target_max_error_pp=float(max(abs(v-expected))),
        targets=len(v),sparse_jacobian_shape=list(j.shape),passed=bool(err<2e-12 and max(abs(v-expected))<2e-8))
    write_json(ROOT/'outputs/logs/strength_inference/fast_equivalence.json',report);print(json.dumps(report))
    if not report['passed']:raise SystemExit(1)
