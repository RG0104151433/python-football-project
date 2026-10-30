"""Prespecified faster-state candidates; report ALL gates, no automatic adoption."""
from pathlib import Path
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.calibration import online_offsets
from src.strength.io import read_rows,publish
from src.strength.global_run import load,gate
from src.strength.baseline import frequency,fixed_step
from src.strength.experiment import score
from src.data_contract import file_hash,write_json


def main():
    protocol=dict(rates=[.08,.32,1.28,5.12],representations=['raw','informative_component'],
        final_gate_unchanged=True,purpose='finite response-speed sensitivity; no future-independent claim',
        source='data/processed/strength/jump-ratings-451ecade0bf84ee0bfb6')
    write_json(ROOT/'config/strength_fast_calibration.json',protocol)
    cfg,games,_=load('config/strength_global_v3.json');lookup={g['match_id']:g for g in games};study={g['match_id'] for g in games if g['study']}
    raw=read_rows(ROOT/protocol['source']/'prematch_features.csv');dates=[r['date'] for r in raw]
    p=np.array([[float(r[k]) for k in ('p_home','p_draw','p_away')] for r in raw]);y=np.array([lookup[r['match_id']]['outcome'] for r in raw])
    cc=np.array([[int(lookup[r['match_id']]['friendly']),int(lookup[r['match_id']]['venue']==0)] for r in raw])
    base=frequency(games,1950);elo=fixed_step(games,40,100,.75,1950);metrics=[];predictions=[];reports={}
    periods=json.loads((ROOT/'config/strength_repair_v11.json').read_text())['periods']
    for representation in protocol['representations']:
        pp=p.copy()
        if representation=='informative_component':
            k=.95*np.where(cc[:,0],.65,1.);pp=(pp-(1-k[:,None])/3)/k[:,None]
        pp=np.maximum(pp,1e-12);pp/=pp.sum(axis=1,keepdims=True)
        for rate in protocol['rates']:
            probs,_=online_offsets(pp,y,dates,cc,rate,9)
            rows=[dict(match_id=r['match_id'],date=r['date'],p_home=float(probs[i,0]),p_draw=float(probs[i,1]),p_away=float(probs[i,2]),outcome_index=int(y[i])) for i,r in enumerate(raw)]
            name=f'{representation}_{rate}';checks=[]
            for a,b in periods:checks.extend(gate(rows,base,elo,dict(id=f'reused_{a}_{b}',start=f'{a}-01-01',end=f'{b}-12-31'),study,cfg))
            type_checks=[]
            for a,b in periods:
                for fr in (False,True):
                    rs=[r for r in rows if a<=int(r['date'][:4])<=b and r['match_id'] in study and lookup[r['match_id']]['friendly']==fr]
                    bias=float(np.mean([r['p_home']-int(r['outcome_index']==0) for r in rs]))
                    type_checks.append(dict(period=f'{a}_{b}',friendly=fr,count=len(rs),bias=bias,passed=abs(bias)<=.03))
            reports[name]=dict(checks=checks,type_checks=type_checks,passed=all(r['passed'] for r in checks+type_checks))
            selected=[r for r in rows if r['match_id'] in study]
            metrics.append(dict(model=name,**score(selected),all_gates_passed=reports[name]['passed'],
                failures=sum(not r['passed'] for r in checks+type_checks)))
            predictions.extend(dict(model=name,**r) for r in rows if r['date']>='1960-01-01')
            print('FAST',metrics[-1],[(r['period'],r.get('scope',r.get('friendly')),r.get('home_probability_bias',r.get('bias'))) for r in checks+type_checks if not r['passed']],flush=True)
    folder,_=publish('fast-calibration-diagnosis',dict(protocol=protocol,runner_sha=file_hash(Path(__file__))),
        csvs={'metrics.csv':metrics,'predictions.csv':predictions},jsons={'report.json':reports},texts={'runner_snapshot.py':Path(__file__).read_text(encoding='utf-8')})
    print('FAST_COMPLETE',folder.relative_to(ROOT).as_posix(),flush=True)


if __name__=='__main__':main()
