"""Use-specific acceptance, frozen candidate replay and past-only annual choice.

Historical rolling checks are reused diagnostics, never new independent tests.
Every candidate filter continues learning complete prior-day batches. Annual
model choice uses only the previous ten years, including eligible neutral games.
"""
from collections import defaultdict
from pathlib import Path
import argparse
import json
import numpy as np
from .io import ROOT,read_rows,publish
from .global_run import load,replay,rate,gate
from .baseline import frequency,fixed_step
from .experiment import score
from ..data_contract import file_hash,write_json


def choose_past(candidates,losses,margin):
    best=min(losses.values())
    return min((c for c in candidates if losses[c["id"]]<=best+margin),
               key=lambda c:(c["modules"],losses[c["id"]],c["id"]))["id"]


def run(strict=False):
    protocol_path=ROOT/"config/strength_handoff.json"
    protocol=json.loads(protocol_path.read_text(encoding="utf-8-sig"))
    cfg,games,inputs=load(protocol["base_protocol"])
    cfg["protocol_version"]="strength-context-rolling-reused-v4"
    if strict:cfg["numerics"].update(ep_tolerance=1e-8,ep_max_iter=300)
    cfg["decision_log_id"]=protocol["decision_log_id"]
    cfg["external_checks"]=[dict(id=f"reused_{a}_{b}",start=f"{a}-01-01",end=f"{b}-12-31",
        role="reused_history_not_independent") for a,b in protocol["check_blocks"]]
    cfg["limits"]=["conditional_identity","conditional_covariance_not_selection_error","reused_history"]
    cfg["starts"]=[1950]
    cfg["candidates"]=[dict(id=c["id"],modules=c["modules"],parameters={**protocol["parameters"],
        **{k:v for k,v in c.items() if k not in {"id","modules"}}}) for c in protocol["candidates"]]
    # Config exists before any new candidate outcome is read.
    config_path="config/strength_context_v4_strict.json" if strict else "config/strength_context_v4.json"
    write_json(ROOT/config_path,cfg)
    original=json.loads((ROOT/"outputs/logs/strength/final-reference-selection-201f706b72b45175119d/selection.json").read_text(encoding="utf-8"))
    baseline=original["fixed_step_baseline"]
    candidates=cfg["candidates"]
    candidate_folders={};pool={};metrics=[]
    for order,candidate in enumerate(candidates):
        selection=dict(protocol=cfg,parameters=candidate["parameters"],
            fixed_step_baseline=baseline,winner=dict(model=candidate["id"],start=1950,
                modules=candidate["modules"],candidate_order=order),
            selection_role="prespecified_candidate_not_future_selected",
            caveat="candidate replay on reused history; not independently confirmed")
        sf,_=publish("context-candidate-selection",{"protocol":protocol,"candidate":candidate,"strict":strict,
            "candidate_config_sha":file_hash(ROOT/config_path),
            "baseline_source_sha":file_hash(ROOT/"outputs/logs/strength/final-reference-selection-201f706b72b45175119d/selection.json")},
            jsons={"selection.json":selection})
        folder=rate(sf,config_path)
        candidate_folders[candidate["id"]]=folder.relative_to(ROOT).as_posix()
        by_game={g["match_id"]:g for g in games}
        rows=[]
        for r in read_rows(folder/"prematch_features.csv"):
            numeric=("p_home","p_draw","p_away","home_mean","away_mean","home_variance","away_variance",
                     "home_away_covariance","difference","difference_variance","home_term","home_term_variance")
            row=dict(r,**{k:float(r[k]) for k in numeric},outcome_index=by_game[r["match_id"]]["outcome"])
            rows.append(row)
        pool[candidate["id"]]=rows
        for a,b in [(1970,1979),*protocol["check_blocks"]]:
            for scope in ("all_learning","accepted_study"):
                selected=[r for r in rows if a<=int(r["date"][:4])<=b and (scope=="all_learning" or by_game[r["match_id"]]["study"])]
                if selected:
                    metrics.append(dict(model=candidate["id"],start=a,end=b,scope=scope,**score(selected),
                        home_bias=float(np.mean([r["p_home"]-int(r["outcome_index"]==0) for r in selected]))))
        print("CONTEXT_DONE",candidate["id"],folder.name,flush=True)
    choices=[];rolling=[]
    for year in range(1980,2025):
        losses={c["id"]:score([r for r in pool[c["id"]] if year-10<=int(r["date"][:4])<year])["log_loss"] for c in candidates}
        chosen=choose_past(candidates,losses,protocol["rolling"]["complexity_loss_margin"])
        choices.extend(dict(year=year,model=c["id"],chosen=c["id"]==chosen,
            selection_start=year-10,selection_end=year-1,log_loss=losses[c["id"]]) for c in candidates)
        rolling.extend(dict(r,rolling_year=year,selected_model=chosen,
            selector_information_cutoff=f"{year-1}-12-31") for r in pool[chosen] if r["date"].startswith(str(year)))
    rolling.sort(key=lambda r:(r["date"],r["match_id"]))
    study_ids={g["match_id"] for g in games if g["study"]}
    base=frequency(games,1950);elo=fixed_step(games,baseline["K"],baseline["H"],baseline["draw"],1950)
    checks=[]
    for p in cfg["external_checks"]:checks.extend(gate(rolling,base,elo,p,study_ids,cfg))
    yearly=[];types=[]
    for y in range(1980,2025):
        rs=[r for r in rolling if r["date"].startswith(str(y)) and r["match_id"] in study_ids]
        yearly.append(dict(year=y,**score(rs),home_bias=float(np.mean([r["p_home"]-int(r["outcome_index"]==0) for r in rs]))))
    for p in cfg["external_checks"]:
        for friendly in (False,True):
            rs=[r for r in rolling if p["start"]<=r["date"]<=p["end"] and r["match_id"] in study_ids and by_game[r["match_id"]]["friendly"]==friendly]
            types.append(dict(period=p["id"],friendly=friendly,**score(rs),home_bias=float(np.mean([r["p_home"]-int(r["outcome_index"]==0) for r in rs]))))
    # These are application eligibility checks, not evidence that latent strength is truth.
    exploratory=all(r["tests"]["log_loss_gain_over_frequency"] and r["tests"]["fixed_step_noninferiority"] for r in checks)
    forecast=all(r["passed"] for r in checks)
    report=dict(candidate_directories=candidate_folders,protocol=protocol,strict_numerical_replay=strict,
        external_checks=checks,forecast_engineering_gate_passed=forecast,
        experimental_input_performance_gate_passed=exploratory,
        technical_audit_required_before_input_release=True,
        prospective_validation_completed=False,independent_historical_test_remaining=False,
        model_optimality_proven=False,complex_jump_admission=False,
        rows=len(rolling),study_rows=sum(r["match_id"] in study_ids for r in rolling),
        uncertainty="conditional rating covariance; does not include model selection/parameter/identity errors",
        use="exploratory_joint_design_only_until_separate_joint_model_validation")
    features=[{k:v for k,v in r.items() if k!="outcome_index"} for r in rolling]
    sf=[r for r in features if r["match_id"] in study_ids]
    folder,_=publish("rolling-handoff",{"protocol_sha":file_hash(protocol_path),"strict":strict,"candidate_manifests":{
        k:file_hash(ROOT/v/"manifest.json") for k,v in candidate_folders.items()}},
        csvs={"candidate_metrics.csv":metrics,"annual_choices.csv":choices,"yearly_metrics.csv":yearly,
              "type_metrics.csv":types,"prematch_features.csv":features,"study_prematch_features.csv":sf},
        jsons={"report.json":report},texts={"data_dictionary.md":"# 滚动研究输入\n\n赛前字段同全局评分器。每年仅按此前十年选择候选，当年内继续逐日学习。rating_run_id绑定各行实际候选；selected_model和selector_information_cutoff记录年度选择。候选检查点在各candidate_directories，不能只恢复一个候选就当作完整滚动选择器。outcome_index不进入特征表。全部历史为复用诊断，不是新独立盲测。\n"})
    print("HANDOFF",folder.relative_to(ROOT).as_posix(),flush=True)
    return folder


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--strict",action="store_true")
    run(parser.parse_args().strict)
