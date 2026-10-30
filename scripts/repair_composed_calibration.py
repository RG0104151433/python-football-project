"""Separate probability-shape correction from online marginal drift correction."""
from pathlib import Path
import argparse
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.calibration import contextual_year,online_offsets
from src.strength.global_run import load,gate
from src.strength.baseline import frequency,fixed_step
from src.strength.io import read_rows,publish
from src.strength.experiment import score,calibration
from src.data_contract import file_hash,write_json


def run(strict=False):
    protocol=json.loads((ROOT/'config/strength_composed_calibration.json').read_text(encoding='utf-8'))
    cfg,games,inputs=load('config/strength_global_v3.json');lookup={g['match_id']:g for g in games};study={g['match_id'] for g in games if g['study']}
    folder=ROOT/protocol['strict_source' if strict else 'normal_source'];raw=read_rows(folder/'prematch_features.csv')
    dates=np.array([int(r['date'][:4]) for r in raw]);targets=np.array([lookup[r['match_id']]['outcome'] for r in raw])
    pp=np.array([[float(r[k]) for k in ('p_home','p_draw','p_away')] for r in raw]);pp=np.maximum(pp,1e-12);pp/=pp.sum(axis=1,keepdims=True)
    contexts=np.array([[int(lookup[r['match_id']]['friendly']),int(lookup[r['match_id']]['venue']==0)] for r in raw])
    base=frequency(games,1950);elo=fixed_step(games,40,100,.75,1950);order=17 if strict else 9
    candidates={};metrics=[];allstates={};allpredictions=[]
    for method in protocol['shape_methods']:
        baseline=np.zeros_like(pp);shape_states=[]
        for year in range(1960,2025):
            past=(dates>=year-10)&(dates<year);now=dates==year
            predicted,states=contextual_year(pp[past],targets[past],contexts[past],pp[now],contexts[now],method,8,100,order)
            baseline[now]=predicted;shape_states.extend(dict(year=year,**s) for s in states)
        mask=dates>=1960;anchor=[r for i,r in enumerate(raw) if mask[i]]
        for rate in protocol['offset_diffusions']:
            name=f'{method}__residual_{rate}'
            probs,states=online_offsets(baseline[mask],targets[mask],[r['date'] for r in anchor],contexts[mask],rate,order)
            state_by_day={(s['date'],s['friendly'],s['neutral']):s for s in states}
            rows=[dict(match_id=r['match_id'],date=r['date'],p_home=float(probs[i,0]),p_draw=float(probs[i,1]),p_away=float(probs[i,2]),
                outcome_index=lookup[r['match_id']]['outcome'],calibration_cutoff=state_by_day[(r['date'],int(contexts[mask][i,0]),int(contexts[mask][i,1]))]['prediction_cutoff']) for i,r in enumerate(anchor)]
            checks=[];types=[]
            for a,b in protocol['periods']:
                checks.extend(gate(rows,base,elo,dict(id=f'reused_{a}_{b}',start=f'{a}-01-01',end=f'{b}-12-31'),study,cfg))
                for fr in (False,True):
                    selected=[r for r in rows if a<=int(r['date'][:4])<=b and r['match_id'] in study and lookup[r['match_id']]['friendly']==fr]
                    bias=float(np.mean([r['p_home']-int(r['outcome_index']==0) for r in selected]))
                    bins=calibration(selected,name);maxerror=max((abs(r['mean_probability']-r['observed_frequency']) for r in bins if r['count']>=200),default=0)
                    types.append(dict(period=f'reused_{a}_{b}',friendly=fr,**score(selected),home_bias=bias,max_bin_error=maxerror,
                        passed=abs(bias)<=.03 and maxerror<=.1))
            accepted=all(r['passed'] for r in checks+types)
            candidates[name]=dict(forecast_checks=checks,type_checks=types,passed=accepted)
            chosen=[r for r in rows if r['match_id'] in study]
            metrics.append(dict(model=name,**score(chosen),passed=accepted,failures=sum(not r['passed'] for r in checks+types)))
            allpredictions.extend(dict(model=name,**r) for r in rows)
            snapshots={}
            for s in states:snapshots[(s['date'][:4],s['friendly'],s['neutral'])]=s
            allstates[name]=dict(shape=shape_states,offset=list(snapshots.values()))
            print('COMPOSED',metrics[-1],[(r['period'],r.get('scope',r.get('friendly')),r.get('home_probability_bias',r.get('home_bias'))) for r in checks+types if not r['passed']],flush=True)
    result,_=publish('composed-calibration',dict(protocol=protocol,strict=strict,inputs=inputs,source_manifest_sha=file_hash(folder/'manifest.json'),runner_sha=file_hash(Path(__file__))),
        csvs={'candidate_metrics.csv':metrics,'predictions.csv':allpredictions},jsons={'report.json':dict(protocol=protocol,strict=strict,candidates=candidates),
            'states.json':allstates},texts={'runner_snapshot.py':Path(__file__).read_text(encoding='utf-8')})
    print('COMPOSED_COMPLETE',result.relative_to(ROOT).as_posix(),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--strict',action='store_true');run(p.parse_args().strict)
