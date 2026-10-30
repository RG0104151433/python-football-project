"""Larger frozen streaming budgets after the initial failed budget comparison."""
from pathlib import Path
from collections import defaultdict
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.io import config,publish
from src.strength.global_run import load
from src.strength.experiment import params,score
from src.strength.streaming import StreamingStrengthFilter
from src.data_contract import file_hash,write_json


def main():
    protocol={"decision_log_id":"R20261029-10","previous":"outputs/logs/strength/streaming-jump-check-95d0d51d8b19e3705870",
        "budgets":[16,32,64],"partition_orders":[0,1],"global_days":250,"seconds_per_run":600,
        "probability_gate":.01,"scope":"development_only_to1974; no_forecast_or_global_admission_on_local_pass"}
    write_json(ROOT/"config/strength_streaming_followup.json",protocol)
    cfg=config();_,games,inputs=load("config/strength_global_v3.json")
    games=[g for g in games if g["date"]<="1974-12-31"]
    broad=json.loads((ROOT/"config/strength_broad_development.json").read_text(encoding="utf-8"))
    labels=set(broad["teams20"])
    small=[g for g in games if g["home_label"] in labels and g["away_label"] in labels]
    cache={};metrics=[];failures=[];timings=[];diagnostics=[]
    runs=[("twenty",o,b) for o in (0,1) for b in protocol["budgets"]]+[("global_profile",1,b) for b in protocol["budgets"]]
    for scope,order,budget in runs:
        gs=small if scope=="twenty" else games
        groups=defaultdict(list)
        for g in gs:groups[g["date"]].append(g)
        groups=sorted(groups.items())
        if scope=="global_profile":groups=groups[:protocol["global_days"]]
        num={**cfg["numerics"],"event_partition_order":order,"max_components":budget,"max_child_bytes":536870912}
        e=StreamingStrengthFilter({g[k] for g in gs for k in ("home","away")},params(cfg,{"id":"both"}),num)
        rows=[];begin=time.perf_counter()
        try:
            for day,batch in groups:
                rows.extend(e.day(day,batch))
                if time.perf_counter()-begin>protocol["seconds_per_run"]:raise RuntimeError("Prespecified feasibility timeout")
            selected=[r for r in rows if r["date"]>="1970-01-01"] if scope=="twenty" else rows
            cache[(scope,order,budget)]={r["match_id"]:r for r in selected}
            metrics.append(dict(scope=scope,order=order,budget=budget,completed=len(rows),**score(selected)))
            diagnostics.extend(dict(scope=scope,order=order,budget=budget,**d) for d in e.diagnostics)
            print(metrics[-1],flush=True)
        except Exception as err:
            failures.append(dict(scope=scope,order=order,budget=budget,date=day,completed=len(rows),error=str(err)))
            print(failures[-1],flush=True)
        timings.append(dict(scope=scope,order=order,budget=budget,seconds=time.perf_counter()-begin))
    pairs=[(("twenty",o,a),("twenty",o,b)) for o in (0,1) for a,b in ((16,32),(32,64))]
    pairs += [(("twenty",0,b),("twenty",1,b)) for b in protocol["budgets"]]
    pairs += [(("global_profile",1,a),("global_profile",1,b)) for a,b in ((16,32),(32,64))]
    comparisons=[]
    for a,b in pairs:
        error=None
        if a in cache and b in cache:
            if cache[a].keys()!=cache[b].keys():raise ValueError("Changed comparison population")
            error=max(abs(cache[a][mid][k]-cache[b][mid][k]) for mid in cache[a] for k in ("p_home","p_draw","p_away"))
        comparisons.append(dict(first=str(a),second=str(b),max_probability_difference=error,passed=error is not None and error<=.01))
    passed=all(r["passed"] for r in comparisons) and not failures
    csvs={"comparisons.csv":comparisons}
    if metrics:csvs["metrics.csv"]=metrics
    if diagnostics:csvs["diagnostics.csv"]=diagnostics
    folder,_=publish("streaming-followup",{"protocol":protocol,"inputs":inputs,"runner_sha":file_hash(Path(__file__))},
        csvs=csvs,jsons={"report.json":{"local_numerical_pass":passed,"global_prediction_admitted":False,
            "disposition":"further_global_experiment_required" if passed else "reject_for_current_handoff_numerical_failure",
            "not_evidence_of_inferior_true_predictive_performance":True},"failures.json":failures})
    write_json(folder/"execution_timing.json",dict(runs=timings))
    print("FOLLOWUP",folder.relative_to(ROOT).as_posix(),flush=True)


if __name__=="__main__":main()
