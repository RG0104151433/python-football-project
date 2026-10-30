"""Frozen event-partition / branch-budget / global-cost jump-route checks."""
from collections import defaultdict
import json
import time
import numpy as np
from .io import ROOT,config,publish
from .global_run import load
from .experiment import params,score
from .streaming import StreamingStrengthFilter
from ..data_contract import file_hash,write_json


def run():
    protocol=json.loads((ROOT/"config/strength_handoff.json").read_text(encoding="utf-8-sig"))
    cfg=config();_,games,inputs=load(protocol["base_protocol"])
    broad=json.loads((ROOT/"config/strength_broad_development.json").read_text(encoding="utf-8"))
    games=[g for g in games if g["date"]<="1974-12-31"]
    labels=set(broad["teams20"])
    small=[g for g in games if g["home_label"] in labels and g["away_label"] in labels]
    jc=protocol["complex_jump"];cache={};metrics=[];failures=[];diagnostics=[];times=[]
    for scope,order,budget in [("twenty",o,b) for o in jc["transition_partitions"] for b in jc["component_budgets"]]+[
            ("global_profile",1,jc["component_budgets"][0]),("global_profile",1,jc["component_budgets"][-1])]:
        gs=small if scope=="twenty" else games
        grouped=defaultdict(list)
        for g in gs:grouped[g["date"]].append(g)
        batches=sorted(grouped.items())
        if scope=="global_profile":batches=batches[:jc["global_profile_days"]]
        num={**cfg["numerics"],"max_components":budget,"event_partition_order":order,
             "max_child_bytes":jc["covariance_buffer_bytes"]}
        e=StreamingStrengthFilter({g[k] for g in gs for k in ("home","away")},params(cfg,{"id":"both"}),num)
        rows=[];begin=time.perf_counter()
        try:
            for day,batch in batches:
                rows.extend(e.day(day,batch))
                if time.perf_counter()-begin>jc["per_profile_seconds"]:raise RuntimeError("Prespecified cost timeout")
            selected=[r for r in rows if r["date"]>="1970-01-01"] if scope=="twenty" else rows
            current={r["match_id"]:r for r in selected}
            cache[(scope,order,budget)]=current
            metrics.append(dict(scope=scope,partition_order=order,budget=budget,completed_matches=len(rows),**score(selected)))
            diagnostics.extend(dict(scope=scope,partition_order=order,budget=budget,**r) for r in e.diagnostics)
            print("JUMP",metrics[-1],flush=True)
        except Exception as err:
            failures.append(dict(scope=scope,partition_order=order,budget=budget,date=day,
                completed_matches=len(rows),error=type(err).__name__+": "+str(err)))
            print("JUMP_FAILURE",failures[-1],flush=True)
        times.append(dict(scope=scope,partition_order=order,budget=budget,seconds=time.perf_counter()-begin))
    comparisons=[]
    pairs=[]
    for o in jc["transition_partitions"]:
        for a,b in zip(jc["component_budgets"],jc["component_budgets"][1:]):pairs.append((("twenty",o,a),("twenty",o,b)))
    for b in jc["component_budgets"]:pairs.append((("twenty",0,b),("twenty",1,b)))
    pairs.append((("global_profile",1,jc["component_budgets"][0]),("global_profile",1,jc["component_budgets"][-1])))
    for a,b in pairs:
        if a not in cache or b not in cache:
            comparisons.append(dict(first=str(a),second=str(b),count=0,max_probability_difference=None,passed=False));continue
        aa,bb=cache[a],cache[b]
        if aa.keys()!=bb.keys():raise ValueError("Numerical comparison changed population")
        error=max(abs(aa[mid][k]-bb[mid][k]) for mid in aa for k in ("p_home","p_draw","p_away"))
        comparisons.append(dict(first=str(a),second=str(b),count=len(aa),max_probability_difference=error,
            passed=error<=jc["probability_difference_gate"]))
    numerical=all(r["passed"] for r in comparisons) and not failures
    report=dict(protocol=protocol,comparison_passed=numerical,cost_and_local_checks_only=True,
        covariance_growth_fixed_by_streaming=True,full_global_prediction_admitted=False,
        full_global_replay_required_if_promoted=True,
        disposition="eligible_for_further_global_experiment" if numerical else "not_admitted_due_numerical_or_cost_failure",
        all_event_mass_retained=True,conditional_event_count_gaussianization=True,
        no_exact_posterior_jump_date_claim=True,means_and_covariances_preserved_by_each_merge=True,
        omitted_uncertainty="conditional count higher moments, online merge/EP/time accumulated error")
    csvs={"comparisons.csv":comparisons}
    if metrics:csvs["metrics.csv"]=metrics
    if diagnostics:csvs["diagnostics.csv"]=diagnostics
    folder,_=publish("streaming-jump-check",{"protocol_sha":file_hash(ROOT/"config/strength_handoff.json"),"inputs":inputs,
        "broad_protocol_sha":file_hash(ROOT/"config/strength_broad_development.json")},csvs=csvs,
        jsons={"report.json":report,"failures.json":failures})
    write_json(folder/"execution_timing.json",dict(runs=times))
    print("JUMP_CHECK",folder.relative_to(ROOT).as_posix(),flush=True)
    return folder


if __name__=="__main__":run()
