"""Full adopted-core initialization sensitivity; immutable per-variant output."""
from pathlib import Path
from collections import defaultdict
import argparse
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength.global_run import load
from src.strength.io import read_rows,publish
from src.data_contract import file_hash,write_json


def run(start,variance):
    cfg,games,inputs=load('config/strength_global_v3.json');directory=ROOT/'data/processed/strength/jump-ratings-451ecade0bf84ee0bfb6'
    report=json.loads((directory/'report.json').read_text());index={r['match_id']:r for r in read_rows(directory/'study_prematch_features.csv')}
    selected=[g for g in games if int(g['date'][:4])>=start];groups=defaultdict(list)
    for g in selected:groups[g['date']].append(g)
    e=CollapsedJumpFilter({g[k] for g in selected for k in ('home','away')},report['parameters'],report['numerics'],variance,.25)
    rows=[]
    for i,(day,gs) in enumerate(sorted(groups.items())):
        for r in e.day(day,gs):
            if r['match_id'] in index:
                baseline=index[r['match_id']]
                rows.append(dict(match_id=r['match_id'],date=day,difference=r['difference'],difference_variance=r['difference_variance'],
                    max_probability_change=max(abs(r[k]-float(baseline[k])) for k in ('p_home','p_draw','p_away')),
                    gap_change=r['difference']-float(baseline['difference']),home_history=r['home_history'],away_history=r['away_history']))
        if i%1500==0:print('INITIALIZATION',start,variance,i,day,flush=True)
    if len(rows)!=24917:raise ValueError('Initialization sensitivity changed population')
    summary=[]
    for scope in ('all','both_have10'):
        rs=[r for r in rows if scope=='all' or min(r['home_history'],r['away_history'])>=10]
        summary.append(dict(scope=scope,matches=len(rs),max_probability_change=max(r['max_probability_change'] for r in rs),
            mean_probability_change=float(np.mean([r['max_probability_change'] for r in rs])),
            max_absolute_gap_change=max(abs(r['gap_change']) for r in rs)))
    folder,_=publish('repaired-initialization',dict(start=start,variance=variance,inputs=inputs,
        adopted_manifest_sha=file_hash(directory/'manifest.json'),runner_sha=file_hash(Path(__file__))),
        csvs={'study_differences.csv':rows,'summary.csv':summary},
        jsons={'report.json':dict(start=start,variance=variance,study_rows=24917,sensitivity_not_uniform_invariance_gate=True)},
        texts={'runner_snapshot.py':Path(__file__).read_text(encoding='utf-8')})
    write_json(ROOT/'outputs/logs/strength/repair-20261029'/f'initial_{start}_{variance}.json',dict(directory=folder.relative_to(ROOT).as_posix()))
    print('INITIAL_COMPLETE',folder.relative_to(ROOT).as_posix(),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=1950);p.add_argument('--variance',type=float,default=1.)
    a=p.parse_args();run(a.start,a.variance)
