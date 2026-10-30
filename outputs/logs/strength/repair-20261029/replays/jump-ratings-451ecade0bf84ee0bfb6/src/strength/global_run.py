"""Select on pre1980 history, then replay locked global ratings and holdout checks.

Candidate pool and limitations are explicit: this is a usable-model selection,
not a proof of global algorithmic optimality. Final2020-2024 scores stay unopened.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import date
import itertools
import json
import time
from pathlib import Path

import numpy as np

from .io import ROOT, read_rows, publish, identify
from .gaussian import GaussianStrengthFilter
from .experiment import score, calibration
from .baseline import fixed_step, frequency
from ..data_contract import file_hash, fingerprint, write_json


def load(config_path="config/strength_global.json"):
    path=ROOT/config_path
    cfg=json.loads(path.read_text(encoding="utf-8"))
    learning=ROOT/cfg["learning"]
    manifest=json.loads((learning/"manifest.json").read_text(encoding="utf-8"))
    source=learning/"learning_matches.csv"
    if file_hash(source)!=manifest["outputs"]["learning_matches.csv"]:
        raise ValueError("Learning source changed")
    raw=read_rows(source)
    games=[dict(match_id=r["match_id"],date=r["date"],home=r["home_entity_id"],away=r["away_entity_id"],
        home_label=r["home_team"],away_label=r["away_team"],
        venue=0 if r["is_neutral"]=="true" else 1,friendly=r["tournament_group"]=="friendly",
        outcome=int(r["outcome_index"]),study=r["accepted_current_study"]=="true") for r in raw]
    return cfg,games,{config_path:file_hash(path),
          (cfg["learning"]+"/learning_matches.csv"):file_hash(source),
          (cfg["learning"]+"/manifest.json"):file_hash(learning/"manifest.json")}


def replay(games,cfg,parameters,start,strict=False,snapshot=False,variance=None):
    games=[g for g in games if int(g["date"][:4])>=start]
    numerical={**cfg["numerics"],**({"ep_tolerance":1e-8,"ep_max_iter":300} if strict else {})}
    engine=GaussianStrengthFilter({g[k] for g in games for k in ("home","away")},parameters,numerical,
                                 variance or cfg["initial_team_variance"],cfg["initial_home_variance"])
    grouped=defaultdict(list)
    for g in games: grouped[g["date"]].append(g)
    rows,states=[],{}
    remaining=list(cfg["snapshots"]) if snapshot else []
    for day,batch in sorted(grouped.items()):
        while remaining and remaining[0]<day:
            boundary=remaining.pop(0)
            state=engine.state()
            states[boundary]={"asof":boundary,"representation":"lazy_calendar_variances; last[t] required for query",
                              "state":state}
        rows.extend(engine.day(day,batch))
    for boundary in remaining:
        states[boundary]={"asof":boundary,"representation":"lazy_calendar_variances; last[t] required for query",
                          "state":engine.state()}
    return rows,engine,states


def choose(metrics,cfg):
    good=[r for r in metrics if r["period"]=="selection_validation"]
    if "max_absolute_class_bias" in cfg["selection"]:
        good=[r for r in good if r["max_absolute_class_bias"]<=cfg["selection"]["max_absolute_class_bias"]]
    if not good: raise RuntimeError("No admissible candidate")
    best=min(r["log_loss"] for r in good)
    if cfg["selection"].get("policy")=="structural_family_then_minimum_loss":
        family_min={m:min(r["log_loss"] for r in good if r["modules"]==m) for m in {r["modules"] for r in good}}
        family=min(m for m,v in family_min.items() if v<=best+cfg["selection"]["tie_margin"])
        winner=min((r for r in good if r["modules"]==family),
                   key=lambda r:(r["log_loss"],r["start"],r["candidate_order"]))
        return winner,best
    tied=[r for r in good if r["log_loss"]<=best+cfg["selection"]["tie_margin"]]
    winner=min(tied,key=lambda r:(r["modules"],r["candidate_order"],r["start"]))
    return winner,best


def select(config_path="config/strength_global.json"):
    cfg,games,inputs=load(config_path)
    games=[g for g in games if g["date"]<="1979-12-31"]
    metrics,predictions,failures=[],[],[]
    begin=time.perf_counter()
    for order,candidate in enumerate(cfg["candidates"]):
        for start in cfg["starts"]:
            try:
                rows,engine,_=replay(games,cfg,candidate["parameters"],start)
                for name,period in (("development",cfg["development"]),("selection_validation",cfg["selection_validation"])):
                    selected=[r for r in rows if period[0]<=r["date"]<=period[1]]
                    bias=[sum(r["p_"+label]-int(r["outcome_index"]==k) for r in selected)/len(selected)
                          for k,label in enumerate(("home","draw","away"))]
                    metrics.append(dict(model=candidate["id"],start=start,period=name,
                        modules=candidate["modules"],candidate_order=order,**score(selected),
                        max_absolute_class_bias=max(abs(b) for b in bias),
                        home_bias=bias[0],draw_bias=bias[1],away_bias=bias[2]))
                    if name=="selection_validation":
                        predictions.extend(dict(model=candidate["id"],start=start,**{k:r[k] for k in
                              ("match_id","date","p_home","p_draw","p_away","outcome_index")}) for r in selected)
                print("selected-evaluation",candidate["id"],start,metrics[-1]["log_loss"],flush=True)
            except Exception as e:
                failures.append(dict(model=candidate["id"],start=start,error=type(e).__name__+": "+str(e)))
                print(failures[-1],flush=True)
    baseline_metrics=[]
    for k,h,d in itertools.product(cfg["baselines"]["fixed_step"]["K"],cfg["baselines"]["fixed_step"]["H"],
                                  cfg["baselines"]["fixed_step"]["draw"]):
        rows=fixed_step(games,k,h,d)
        chosen=[r for r in rows if cfg["selection_validation"][0]<=r["date"]<=cfg["selection_validation"][1]]
        baseline_metrics.append(dict(K=k,H=h,draw=d,**score(chosen)))
    baseline_winner=min(baseline_metrics,key=lambda r:(r["log_loss"],r["K"],r["H"],r["draw"]))
    winner,best=choose(metrics,cfg)
    selected_candidate=cfg["candidates"][winner["candidate_order"]]
    selection=dict(status="locked_pre1980_selection_not_yet_external_acceptance",winner=winner,
         minimum_validation_log_loss=best,parameters=selected_candidate["parameters"],
         fixed_step_baseline=baseline_winner,failures=len(failures),protocol=cfg,
         caveat="Only numerically admitted candidate pool; no globally optimal model claim; complex jump route remains under development")
    folder,manifest=publish("global-selection",{"inputs":inputs,"protocol":cfg},
        csvs={"candidate_metrics.csv":metrics,"validation_predictions.csv":predictions,
              "fixed_step_baseline_metrics.csv":baseline_metrics},
        jsons={"selection.json":selection,"failures.json":failures})
    write_json(folder/"execution_timing.json",{"seconds":time.perf_counter()-begin,"nondeterministic":True})
    print("SELECTION",folder.relative_to(ROOT).as_posix(),json.dumps(winner),flush=True)
    return folder


def gate(rows,baseline_rows,elo_rows,period,study_ids,cfg):
    output=[]
    baseline_index={r["match_id"]:r for r in baseline_rows}
    elo_index={r["match_id"]:r for r in elo_rows}
    for scope in ("all_learning","accepted_study"):
        selected=[r for r in rows if period["start"]<=r["date"]<=period["end"] and
                  (scope=="all_learning" or r["match_id"] in study_ids)]
        a,b,c=score(selected),score([baseline_index[r["match_id"]] for r in selected]),score([elo_index[r["match_id"]] for r in selected])
        cal=calibration(selected,"chosen")
        eligible=[r for r in cal if r["count"]>=cfg["acceptance"]["calibration_min_bin_count"]]
        cal_error=max((abs(r["mean_probability"]-r["observed_frequency"]) for r in eligible),default=0)
        bias=sum(r["p_home"]-int(r["outcome_index"]==0) for r in selected)/len(selected)
        tests=dict(
            log_loss_gain_over_frequency=b["log_loss"]-a["log_loss"]>=cfg["acceptance"]["log_loss_gain_over_frequency_at_least"],
            accuracy_not_worse_than_frequency=a["accuracy"]>=b["accuracy"]-cfg["acceptance"]["accuracy_noninferiority_margin"],
            calibration=cal_error<=cfg["acceptance"]["calibration_max_bin_error"],
            home_probability_bias=abs(bias)<=cfg["acceptance"]["home_probability_mean_bias_max"],
            fixed_step_noninferiority=a["log_loss"]<=c["log_loss"]+cfg["acceptance"]["fixed_step_log_loss_noninferiority_margin"])
        output.append(dict(period=period["id"],scope=scope,**a,frequency_log_loss=b["log_loss"],
             frequency_accuracy=b["accuracy"],fixed_step_log_loss=c["log_loss"],fixed_step_accuracy=c["accuracy"],
             max_calibration_bin_error=cal_error,home_probability_bias=bias,passed=all(tests.values()),tests=tests))
    return output


def rate(selection_path,config_path="config/strength_global.json"):
    cfg,games,inputs=load(config_path)
    selection_path=(ROOT/selection_path).resolve()
    manifest=json.loads((selection_path/"manifest.json").read_text(encoding="utf-8"))
    if file_hash(selection_path/"selection.json")!=manifest["outputs"]["selection.json"]:
        raise ValueError("Selection binding changed")
    selection=json.loads((selection_path/"selection.json").read_text(encoding="utf-8"))
    if selection["protocol"]!=cfg: raise ValueError("Locked protocol changed")
    p,start=selection["parameters"],selection["winner"]["start"]
    # Numerical tightening and prior sensitivity use only pre1975 development.
    dev=[g for g in games if g["date"]<="1974-12-31"]
    original,_,_=replay(dev,cfg,p,start)
    tighter,_,_=replay(dev,cfg,p,start,strict=True)
    diff=max(max(abs(a[k]-b[k]) for k in ("p_home","p_draw","p_away")) for a,b in zip(original,tighter))
    if diff>cfg["acceptance"]["numeric_probability_tolerance"]:
        raise RuntimeError("Tighter EP changes development probabilities beyond gate")
    begin=time.perf_counter()
    rows,engine,states=replay(games,cfg,p,start,snapshot=True)
    by_id={g["match_id"]:g for g in games}
    study_ids={g["match_id"] for g in games if g["study"]}
    if len(study_ids)!=24917: raise ValueError("Study population changed")
    base=frequency(games,start)
    elo=selection["fixed_step_baseline"]
    elo_rows=fixed_step(games,elo["K"],elo["H"],elo["draw"],cfg["baselines"]["fixed_step"]["start"])
    checks=[]
    for period in cfg["external_checks"]: checks.extend(gate(rows,base,elo_rows,period,study_ids,cfg))
    reserve_count=sum(cfg["reserve"][0]<=r["date"]<=cfg["reserve"][1] for r in rows) if cfg["reserve"] else 0
    features=[]
    rule_id="rating-rules-"+fingerprint({"selection":selection["winner"],"parameters":p,"protocol":cfg})[:20]
    identity={"inputs":inputs,"selection_manifest":file_hash(selection_path/"manifest.json"),
              "selection_json":file_hash(selection_path/"selection.json"),"rules_id":rule_id,"protocol":cfg}
    prepared=identify("ratings",identity,"data/processed/strength")
    for r in rows:
        item={k:v for k,v in r.items() if k!="outcome_index"}
        item.update(rating_run_id=prepared[0],rating_rules_version=rule_id,
                    accepted_study=r["match_id"] in study_ids,
                    input_learning_version=Path(cfg["learning"]).name)
        features.append(item)
    study_features=[r for r in features if r["accepted_study"]]
    if len(study_features)!=24917: raise ValueError("Study features incomplete")
    scores=[dict(period=r["period"],scope=r["scope"],**{k:v for k,v in r.items() if k not in {"period","scope","tests"}})
            for r in checks]
    yearly=[]
    # Reserve years intentionally excluded from scoring, even though causal states advance.
    for y in range(1980,int(cfg["reserve"][0][:4]) if cfg["reserve"] else 2025):
        chosen=[r for r in rows if r["date"].startswith(str(y))]
        yearly.append(dict(year=y,**score(chosen)))
    coverage=[]
    for y in range(start,2025):
        subset=[r for r in rows if r["date"].startswith(str(y))]
        coverage.append(dict(year=y,matches=len(subset),accepted_study=sum(r["match_id"] in study_ids for r in subset),
             cold_start=sum(r["cold_start"] for r in subset),previously_disconnected=sum(r["previously_disconnected"] for r in subset)))
    accepted=all(r["passed"] for r in checks)
    report=dict(status="global_reference_accepted" if accepted else "global_reference_prediction_gate_failed",
        numerical_gate_passed=True,tighter_EP_max_probability_difference=diff,
        external_checks=checks,all_prediction_and_feature_rows=len(rows),study_rows=len(study_features),
        reserve_rows_generated_but_scores_unopened=reserve_count,external_prediction_gate_passed=accepted,
        production_model_optimality_proven=False,complex_jump_route_accepted=False,
        uncertainty_basis="conditional joint Gaussian covariance, not model/hyperparameter selection error",
        rule_id=rule_id,selection_path=selection_path.relative_to(ROOT).as_posix(),
        holdout_roles=cfg["external_checks"],reserve_period=cfg["reserve"],
        old_holdout_not_independent_after_revision=any("reused" in p.get("role","") for p in cfg["external_checks"]),
        unopened_in_scope_holdout_remains=bool(cfg["reserve"]),
        reserve_scores_opened=False,causal_claim=False,heldout_predictions_issued_historically=False)
    folder,man=publish("ratings",identity,csvs={"prematch_features.csv":features,"study_prematch_features.csv":study_features,
            "external_metrics.csv":scores,"yearly_metrics_before_reserve.csv":yearly,"coverage.csv":coverage,
            "solver_diagnostics.csv":engine.diagnostics},
        jsons={"rating_report.json":report,"checkpoints.json":states},
        texts={"data_dictionary.md":"# 赛前实力特征（全局参考模型）\n\n每行一场，UTF8 BOM/LF/浮点10位。"
          "所有值由此前日期赛果生成；outcome_index不进入特征表。home/away是历史评分实体，不等于地理载体。"
          "中立场venue=0，第一方不视为实际主场。home_term是共享场地状态，实际预期应用venue*home_term。"
          "双方方差及协方差给出difference_variance；它们条件于选定模型/超参数，不包含全部选择和模型误差。"
          "cold_start表示任一方此前少于5场，仅为诊断，不证明5场后可靠；previously_disconnected只检查此前累计对阵图。"
          "预测概率已积分评分未知并含场地与背景；不是后续联合研究的结果。rating_run_id/规则/输入版本均固定。"
          "检查点采用延迟日历传播表示，查询某日应按state.last[t]补q*间隔，未出场占位先验不能展示为球队历史实力。\n"},
        base_dir="data/processed/strength",prepared=prepared)
    pointer=ROOT/"outputs/logs/strength"/("global-application-"+prepared[0])
    pointer.mkdir(parents=True,exist_ok=True)
    write_json(pointer/"run_manifest.json",dict(rating_directory=folder.relative_to(ROOT).as_posix(),
         rating_manifest_sha256=file_hash(folder/"manifest.json"),report_sha256=file_hash(folder/"rating_report.json"),
         elapsed_seconds=time.perf_counter()-begin,status=report["status"]))
    print("RATINGS",folder.relative_to(ROOT).as_posix(),json.dumps(report,ensure_ascii=False),flush=True)
    return folder


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=["select","rate"])
    parser.add_argument("--selection")
    parser.add_argument("--config",default="config/strength_global.json")
    args=parser.parse_args()
    try:
        if args.stage=="select": select(args.config)
        else:
            if not args.selection: parser.error("--selection required")
            rate(args.selection,args.config)
    except Exception as e:
        folder,_=publish("global-failure",{"stage":args.stage,"selection":args.selection,
                  "protocol_sha":file_hash(ROOT/args.config),
                  "error":type(e).__name__+": "+str(e)},
                 jsons={"failure.json":{"stage":args.stage,"error":type(e).__name__+": "+str(e),
                                       "production_accepted":False}})
        print("FAILURE",folder.relative_to(ROOT).as_posix(),flush=True)
        raise


if __name__=="__main__": main()
