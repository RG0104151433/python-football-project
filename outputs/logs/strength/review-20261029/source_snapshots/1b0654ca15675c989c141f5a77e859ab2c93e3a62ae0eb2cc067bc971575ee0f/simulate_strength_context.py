"""Known-strength checks, including changing venue states and an abrupt decline."""
from pathlib import Path
from datetime import date,timedelta
import json
import math
import sys
import numpy as np
from scipy.special import ndtr

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.gaussian import GaussianStrengthFilter
from src.strength.global_run import load
from src.strength.io import publish
from src.data_contract import file_hash,write_json


def run():
    protocol=dict(seeds=list(range(8710,8718)),teams=12,matches=900,warmup=250,day_step=2,
        scenarios=["matched_static","matched_type_dynamic","unmodelled_abrupt_decline"],
        models=["static","dynamic_shared","type_dynamic"],
        parameters=dict(q=.03,jump_rate=0,jump_sd=1.2,delta=.4,alpha=.65,epsilon=.05),
        matched_acceptance=dict(gap_mse_less_than_zero_predictor=True,conditional_90pct_gap_coverage_min=.8),
        caveat="known synthetic truth under limited generators, not calibration proof for real football")
    write_json(ROOT/"config/strength_context_simulation.json",protocol)
    cfg,_,_=load("config/strength_global_v3.json")
    teams=[f"T{k}" for k in range(12)];records=[]
    for scenario in protocol["scenarios"]:
        for seed in protocol["seeds"]:
            rng=np.random.default_rng(seed)
            truth=rng.normal(0,1,12);home=np.array([.45,.2])
            engines={name:GaussianStrengthFilter(teams,{**protocol["parameters"],
                "home_q":.005 if name!="static" else 0,"home_by_type":name=="type_dynamic"},cfg["numerics"]) for name in protocol["models"]}
            values={name:[] for name in engines}
            for k in range(protocol["matches"]):
                dt=2/365.2425
                if k:
                    truth+=rng.normal(0,math.sqrt(.03*dt),12)
                    if scenario=="matched_type_dynamic":home+=rng.normal(0,math.sqrt(.005*dt),2)
                if scenario=="unmodelled_abrupt_decline" and k==450:truth[0]-=1.5
                i,j=rng.choice(12,size=2,replace=False);friendly=bool(rng.random()<.3)
                neutral=bool(rng.random()<.2);h=(home[int(friendly)] if scenario=="matched_type_dynamic" else .4)
                d=truth[i]-truth[j];mu=d+(0 if neutral else h)
                base=np.array([ndtr(mu-.4),ndtr(.4-mu)-ndtr(-.4-mu),ndtr(-.4-mu)])
                kappa=.95*(.65 if friendly else 1)
                probs=kappa*base+(1-kappa)/3;y=int(rng.choice(3,p=probs))
                day=(date(1960,1,1)+timedelta(days=2*k)).isoformat()
                game=dict(match_id=str(k),home=teams[i],away=teams[j],venue=0 if neutral else 1,friendly=friendly,outcome=y)
                for name,e in engines.items():
                    r=e.day(day,[game])[0]
                    if k>=protocol["warmup"]:
                        err=r["difference"]-d
                        values[name].append((err*err,d*d,abs(err)<=1.6448536269514722*math.sqrt(r["difference_variance"]),
                                             -math.log(r[("p_home","p_draw","p_away")[y]])))
            for name,v in values.items():
                a=np.array(v)
                records.append(dict(scenario=scenario,seed=seed,model=name,count=len(v),gap_mse=float(a[:,0].mean()),
                    zero_gap_mse=float(a[:,1].mean()),conditional_90_gap_coverage=float(a[:,2].mean()),log_loss=float(a[:,3].mean())))
    summary=[]
    for scenario in protocol["scenarios"]:
        for model in protocol["models"]:
            selected=[r for r in records if r["scenario"]==scenario and r["model"]==model]
            summary.append(dict(scenario=scenario,model=model,replicates=len(selected),
                **{k:float(np.mean([r[k] for r in selected])) for k in ("gap_mse","zero_gap_mse","conditional_90_gap_coverage","log_loss")}))
    matched=[r for r in summary if (r["scenario"],r["model"]) in (("matched_static","static"),("matched_type_dynamic","type_dynamic"))]
    passed=all(r["gap_mse"]<r["zero_gap_mse"] and r["conditional_90_gap_coverage"]>=.8 for r in matched)
    folder,_=publish("context-simulation",{"protocol":protocol,"runner_sha":file_hash(Path(__file__))},
        csvs={"replicates.csv":records,"summary.csv":summary},jsons={"report.json":dict(protocol=protocol,
        matched_generator_check_passed=passed,real_data_calibration_proven=False,
        abrupt_decline_scenario_is_stress_diagnostic_only=True)})
    print(folder.relative_to(ROOT).as_posix(),json.dumps(summary),flush=True)


if __name__=="__main__":run()
