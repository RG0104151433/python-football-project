"""Development/global replay of collapsed jump filters; all failures preserved."""
from pathlib import Path
from collections import defaultdict
import argparse
import json
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength.global_run import load
from src.strength.io import publish,identify
from src.data_contract import file_hash,write_json


def run(model,scope,strict):
    protocol=json.loads((ROOT/'config/strength_repair_v5.json').read_text(encoding='utf-8'))
    cfg,games,inputs=load(protocol['base_protocol'])
    p=dict(q=.03,delta=.4,alpha=.65,epsilon=.05,home_q=.005,
        **{k:v for k,v in next(x for x in protocol['jump']['candidates'] if x['id']==model).items() if k!='id'})
    if scope!='global':games=[g for g in games if g['date']<='1974-12-31']
    if scope=='twenty':
        labels=set(json.loads((ROOT/'config/strength_broad_development.json').read_text())['teams20'])
        games=[g for g in games if g['home_label'] in labels and g['away_label'] in labels]
    num=dict(cfg['numerics'],ep_max_iter=500 if strict else 300,ep_tolerance=1e-8 if strict else 1e-6,
        poisson_tail_tolerance=1e-15 if strict else 1e-12)
    e=CollapsedJumpFilter({g[k] for g in games for k in ('home','away')},p,num)
    grouped=defaultdict(list)
    for g in games:grouped[g['date']].append(g)
    rows=[];states={};boundaries=[x for x in cfg['snapshots'] if x<=games[-1]['date']];begin=time.perf_counter()
    try:
        for n,(day,batch) in enumerate(sorted(grouped.items())):
            while boundaries and boundaries[0]<day:
                key=boundaries.pop(0);states[key]=dict(asof=key,state=e.state())
            rows.extend(e.day(day,batch))
            if n%500==0:print('JUMP_PROGRESS',model,scope,strict,n,day,len(rows),round(time.perf_counter()-begin,2),flush=True)
        while boundaries:
            key=boundaries.pop(0);states[key]=dict(asof=key,state=e.state())
        identity=dict(protocol_sha=file_hash(ROOT/'config/strength_repair_v5.json'),model=model,scope=scope,strict=strict,
            inputs=inputs,parameters=p,numerics=num,runner_sha=file_hash(Path(__file__)))
        prepared=identify('jump-ratings',identity,'data/processed/strength')
        study={g['match_id'] for g in games if g['study']}
        features=[dict(**{k:v for k,v in r.items() if k!='outcome_index'},rating_run_id=prepared[0],
            rating_rules_version='collapsed-jump-v1-'+model,accepted_study=r['match_id'] in study,
            input_learning_version=Path(cfg['learning']).name) for r in rows]
        sf=[r for r in features if r['accepted_study']]
        if scope=='global' and len(sf)!=24917:raise ValueError('Study population lost')
        csvs={'prematch_features.csv':features,'diagnostics.csv':e.diagnostics}
        if sf:csvs['study_prematch_features.csv']=sf
        folder,_=publish('jump-ratings',identity,csvs=csvs,jsons={'checkpoints.json':states,
            'report.json':dict(model=model,scope=scope,strict=strict,parameters=p,numerics=num,rows=len(rows),study_rows=len(sf),
                numerical_run_completed=True,forecast_admission_not_yet_tested=True,
                approximation='exact scalar collapsed counts; local block Gaussian EP; Gaussian ADF after day',
                gaussian_projection_error_not_zero=True)},texts={'runner_snapshot.py':Path(__file__).read_text(encoding='utf-8')},
            base_dir='data/processed/strength',prepared=prepared)
        write_json(ROOT/'outputs/logs/strength/repair-20261029'/f'{model}_{scope}_{"strict" if strict else "normal"}.json',
            dict(directory=folder.relative_to(ROOT).as_posix(),seconds=time.perf_counter()-begin))
        print('JUMP_COMPLETE',folder.relative_to(ROOT).as_posix(),flush=True)
        return folder
    except Exception as error:
        folder,_=publish('collapsed-jump-failure',dict(model=model,scope=scope,strict=strict,inputs=inputs,
            parameters=p,numerics=num,error=str(error),runner_sha=file_hash(Path(__file__))),
            jsons={'failure.json':dict(date=day,completed=len(rows),error=repr(error),production_accepted=False)})
        print('JUMP_FAILED',folder.relative_to(ROOT).as_posix(),day,len(rows),repr(error),flush=True)
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',choices=['jump_small','jump_full'],default='jump_small')
    p.add_argument('--scope',choices=['twenty','development','global'],default='development');p.add_argument('--strict',action='store_true')
    a=p.parse_args();run(a.model,a.scope,a.strict)
