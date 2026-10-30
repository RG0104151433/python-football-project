"""Full-scope fixed-rule initialization sensitivity; never tune on its results."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.global_run import load,replay
from src.strength.io import publish,read_rows
from src.data_contract import file_hash,write_json


def main():
    cfg,games,inputs=load("config/strength_global_v3.json")
    p=dict(q=.03,jump_rate=0,jump_sd=1.2,delta=.4,alpha=.65,epsilon=0)
    protocol=dict(variants=[dict(id="later_start",start=1960,variance=1),
        dict(id="narrow_prior",start=1950,variance=.5),dict(id="wide_prior",start=1950,variance=2)],
        parameters=p,scope="fixed_rule_full_study_sensitivity_not_parameter_selection",history_threshold=10,
        prior_sd_unit="performance_noise_sd fixed at1; prior variance changes uncertainty not location")
    write_json(ROOT/"config/strength_initialization_sensitivity.json",protocol)
    standard,_,_=replay(games,cfg,p,1950)
    index={r["match_id"]:r for r in standard};study={g["match_id"] for g in games if g["study"]}
    summary=[];cases=[];differences=[]
    for v in protocol["variants"]:
        rows,_,_=replay(games,cfg,p,v["start"],variance=v["variance"])
        selected=[r for r in rows if r["match_id"] in study]
        if len(selected)!=24917:raise ValueError("Sensitivity lost study games")
        diffs=[]
        for r in selected:
            a=index[r["match_id"]]
            d=max(abs(r[k]-a[k]) for k in ("p_home","p_draw","p_away"))
            gap=r["difference"]-a["difference"]
            diffs.append((r,d,gap))
            differences.append(dict(variant=v["id"],match_id=r["match_id"],date=r["date"],
                difference=r["difference"],difference_variance=r["difference_variance"],
                max_probability_difference=d,strength_difference_change=gap))
        for scope in ("all_study","both_have_10_prior_games"):
            ds=[(r,d,gap) for r,d,gap in diffs if scope=="all_study" or min(r["home_history"],r["away_history"])>=10]
            summary.append(dict(variant=v["id"],scope=scope,count=len(ds),
                max_probability_difference=max(d for _,d,_ in ds),mean_probability_difference=float(np.mean([d for _,d,_ in ds])),
                max_absolute_gap_change=max(abs(gap) for _,_,gap in ds)))
        for r,d,gap in sorted(diffs,key=lambda item:-item[1])[:20]:
            cases.append(dict(variant=v["id"],match_id=r["match_id"],date=r["date"],home=r["home"],away=r["away"],
                max_probability_difference=d,gap_change=gap,home_history=r["home_history"],away_history=r["away_history"]))
        print("INITIALIZATION",v["id"],summary[-2:],flush=True)
    folder,_=publish("initialization-sensitivity",{"inputs":inputs,"protocol":protocol,"runner_sha":file_hash(Path(__file__))},
        csvs={"summary.csv":summary,"largest_cases.csv":cases,"study_differences.csv":differences},
        jsons={"report.json":dict(protocol=protocol,study_rows_each=24917,
            uniform_initialization_independence_claim=False,do_not_discard_cold_teams_to_hide_sensitivity=True)})
    print("INITIALIZATION_CHECK",folder.relative_to(ROOT).as_posix(),flush=True)


if __name__=="__main__":main()
