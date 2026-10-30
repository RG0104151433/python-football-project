"""Known-truth stress checks for smooth and two collapsed jump candidates."""
from pathlib import Path
from datetime import date,timedelta
import json
import math
import sys
import numpy as np
from scipy.special import ndtr
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength.gaussian import GaussianStrengthFilter
from src.strength.io import publish
from src.strength.global_run import load
from src.data_contract import file_hash,write_json


def main():
    protocol=dict(seeds=list(range(9150,9158)),matches=900,teams=12,day_step=6,warmup=250,change_at=450,
        scenarios=['smooth','single_upset','forced_decline','matched_compound_jumps'],
        nominal_gap_coverage=.90,engineering_coverage_min=.85,engineering_coverage_max=.97,
        detection_threshold=.75,scope='synthetic finite cases,not guaranteed detection/coverage in real data')
    write_json(ROOT/'config/strength_jump_simulation.json',protocol)
    cfg,_,_=load('config/strength_global_v3.json')
    base=dict(q=.03,delta=.4,alpha=.65,epsilon=.05,home_q=.005,jump_rate=0,jump_sd=1.2)
    settings={'smooth':dict(base),'jump_small':dict(base,jump_rate=.03,jump_sd=.7),'jump_full':dict(base,jump_rate=.08,jump_sd=1.2)}
    records=[]
    for scenario in protocol['scenarios']:
        for seed in protocol['seeds']:
            rng=np.random.default_rng(seed);truth=rng.normal(0,1,12);teams=[f'T{i}' for i in range(12)]
            engines={name:(GaussianStrengthFilter if name=='smooth' else CollapsedJumpFilter)(teams,p,cfg['numerics']) for name,p in settings.items()}
            values={name:[] for name in engines};origins={};delays={};appearances=0
            for k in range(900):
                dt=6/365.2425
                if k:
                    truth+=rng.normal(0,math.sqrt(.03*dt),12)
                    if scenario=='matched_compound_jumps':
                        counts=rng.poisson(.08*dt,12);truth+=rng.normal(0,1.2*np.sqrt(counts))
                if k==450:
                    for name,e in engines.items():origins[name]=float(e.mean[0]-np.mean(e.mean[1:12]))
                    if scenario=='forced_decline':truth[0]-=1.5
                i,j=rng.choice(12,2,replace=False);friendly=bool(rng.random()<.3);neutral=bool(rng.random()<.2)
                diff=truth[i]-truth[j];mu=diff+(0 if neutral else .4)
                probs=np.array([ndtr(mu-.4),ndtr(.4-mu)-ndtr(-.4-mu),ndtr(-.4-mu)])
                kappa=.95*(.65 if friendly else 1);probs=kappa*probs+(1-kappa)/3
                y=int(rng.choice(3,p=probs))
                if scenario=='single_upset' and k==450:y=2 if probs[0]>probs[2] else 0
                day=(date(1960,1,1)+timedelta(days=6*k)).isoformat()
                game=dict(match_id=str(k),home=teams[i],away=teams[j],venue=0 if neutral else 1,friendly=friendly,outcome=y)
                if k>=450 and 0 in (i,j):appearances+=1
                for name,e in engines.items():
                    row=e.day(day,[game])[0]
                    if k>=250:
                        error=row['difference']-diff
                        values[name].append((error*error,diff*diff,abs(error)<=1.6448536269514722*math.sqrt(row['difference_variance']),
                            -math.log(row[('p_home','p_draw','p_away')[y]])))
                    if scenario=='forced_decline' and k>=450 and 0 in (i,j) and name not in delays:
                        if e.mean[0]-np.mean(e.mean[1:12])-origins[name]<=-.75:delays[name]=appearances
            for name,v in values.items():
                a=np.array(v)
                records.append(dict(scenario=scenario,seed=seed,model=name,matches=len(v),gap_mse=float(a[:,0].mean()),
                    zero_gap_mse=float(a[:,1].mean()),coverage90=float(a[:,2].mean()),log_loss=float(a[:,3].mean()),
                    decline_detection_matches=delays.get(name)))
            print('SIMULATION',scenario,seed,flush=True)
    summary=[]
    for scenario in protocol['scenarios']:
        for model in settings:
            rs=[r for r in records if r['scenario']==scenario and r['model']==model]
            delays=[r['decline_detection_matches'] for r in rs if r['decline_detection_matches'] is not None]
            summary.append(dict(scenario=scenario,model=model,**{k:float(np.mean([r[k] for r in rs])) for k in
                ('gap_mse','zero_gap_mse','coverage90','log_loss')},detected_replicates=len(delays),
                mean_detection_matches=float(np.mean(delays)) if delays else None))
    accepted={name:all(.85<=r['coverage90']<=.97 and r['gap_mse']<r['zero_gap_mse'] for r in summary if r['model']==name)
              for name in settings}
    folder,_=publish('jump-repair-simulation',dict(protocol=protocol,runner_sha=file_hash(Path(__file__))),
        csvs={'replicates.csv':records,'summary.csv':summary},jsons={'report.json':dict(protocol=protocol,
            engineering_simulation_gate_by_model=accepted,real_data_coverage_proven=False)},
        texts={'runner_snapshot.py':Path(__file__).read_text(encoding='utf-8')})
    print('SIMULATION_COMPLETE',folder.relative_to(ROOT).as_posix(),json.dumps(accepted),flush=True)


if __name__=='__main__':main()
