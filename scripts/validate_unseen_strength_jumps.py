"""Previously unused jump strengths/seeds; no tuning after these checks."""
from pathlib import Path
from datetime import date,timedelta
import json
import math
import sys
import numpy as np
from scipy.special import ndtr
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength.io import publish
from src.strength.global_run import load
from src.data_contract import file_hash,write_json


def main():
    protocol=dict(worlds=[dict(rate=.03,sd=.7),dict(rate=.12,sd=1.)],seeds=list(range(9170,9178)),matches=900,
        warmup=250,coverage_gate=[.85,.97],model_rate=.08,model_sd=1.2,not_real_football_holdout=True)
    write_json(ROOT/'config/strength_unseen_simulation.json',protocol)
    cfg,_,_=load('config/strength_global_v3.json');records=[]
    for world in protocol['worlds']:
        for seed in protocol['seeds']:
            rng=np.random.default_rng(seed);truth=rng.normal(0,1,12);teams=[f'T{i}' for i in range(12)]
            p=dict(q=.03,jump_rate=.08,jump_sd=1.2,delta=.4,alpha=.65,epsilon=.05,home_q=.005)
            e=CollapsedJumpFilter(teams,p,cfg['numerics']);values=[]
            for k in range(900):
                dt=6/365.2425
                if k:
                    truth+=rng.normal(0,math.sqrt(.03*dt),12)
                    count=rng.poisson(world['rate']*dt,12);truth+=rng.normal(0,world['sd']*np.sqrt(count))
                i,j=rng.choice(12,2,replace=False);fr=bool(rng.random()<.3);neutral=bool(rng.random()<.2)
                diff=truth[i]-truth[j];mu=diff+(0 if neutral else .4)
                pp=np.array([ndtr(mu-.4),ndtr(.4-mu)-ndtr(-.4-mu),ndtr(-.4-mu)]);kap=.95*(.65 if fr else 1)
                y=int(rng.choice(3,p=kap*pp+(1-kap)/3));day=(date(1960,1,1)+timedelta(days=6*k)).isoformat()
                r=e.day(day,[dict(match_id=str(k),home=teams[i],away=teams[j],venue=0 if neutral else 1,friendly=fr,outcome=y)])[0]
                if k>=250:
                    error=r['difference']-diff;values.append((error*error,diff*diff,abs(error)<=1.6448536269514722*math.sqrt(r['difference_variance'])))
            a=np.array(values);records.append(dict(world_rate=world['rate'],world_sd=world['sd'],seed=seed,
                gap_mse=float(a[:,0].mean()),zero_mse=float(a[:,1].mean()),coverage90=float(a[:,2].mean())))
            print('UNSEEN_SIM',world,seed,records[-1],flush=True)
    summary=[]
    for world in protocol['worlds']:
        rs=[r for r in records if r['world_rate']==world['rate']]
        summary.append(dict(world_rate=world['rate'],world_sd=world['sd'],**{k:float(np.mean([r[k] for r in rs])) for k in ('gap_mse','zero_mse','coverage90')}))
    passed=all(.85<=r['coverage90']<=.97 and r['gap_mse']<r['zero_mse'] for r in summary)
    folder,_=publish('unseen-jump-validation',dict(protocol=protocol,runner_sha=file_hash(Path(__file__))),
        csvs={'replicates.csv':records,'summary.csv':summary},jsons={'report.json':dict(passed=passed,protocol=protocol)},
        texts={'runner_snapshot.py':Path(__file__).read_text(encoding='utf-8')})
    write_json(ROOT/'outputs/logs/strength/repair-20261029/unseen_simulation.json',dict(directory=folder.relative_to(ROOT).as_posix(),passed=passed))
    print('UNSEEN_COMPLETE',folder.relative_to(ROOT).as_posix(),passed,flush=True)


if __name__=='__main__':main()
