"""Record acceptance scope and prepare (not fit) the strength joint interface."""
from pathlib import Path
from collections import Counter
import argparse
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.io import read_rows,publish
from src.strength.global_run import load,gate
from src.strength.baseline import frequency,fixed_step
from src.data_contract import file_hash,write_json


def run(normal,strict,jump,simulation,initialization):
    report=json.loads((normal/"report.json").read_text(encoding="utf-8"))
    sr=json.loads((strict/"report.json").read_text(encoding="utf-8"))
    review_path=ROOT/"outputs/logs/strength/review-20261029"/(normal.name+".json")
    audit=json.loads(review_path.read_text(encoding="utf-8"))
    diffs=[];indexes={}
    for model,path in report["candidate_directories"].items():
        aa=read_rows(ROOT/path/"prematch_features.csv")
        bb=read_rows(ROOT/sr["candidate_directories"][model]/"prematch_features.csv")
        ai={r["match_id"]:r for r in aa};bi={r["match_id"]:r for r in bb}
        if ai.keys()!=bi.keys():raise ValueError("Strict run changed population")
        error=max(abs(float(ai[mid][k])-float(bi[mid][k])) for mid in ai for k in ("p_home","p_draw","p_away"))
        gap=max(abs(float(ai[mid]["difference"])-float(bi[mid]["difference"])) for mid in ai)
        diffs.append(dict(model=model,matches=len(ai),max_probability_difference=error,max_strength_difference=gap,
            passed=error<=.01));indexes[model]=ai
    normal_choices={r["year"]:r["model"] for r in read_rows(normal/"annual_choices.csv") if r["chosen"]=="true"}
    strict_choices={r["year"]:r["model"] for r in read_rows(strict/"annual_choices.csv") if r["chosen"]=="true"}
    same_choices=normal_choices==strict_choices
    cfg,games,_=load("config/strength_global_v3.json")
    by_id={g["match_id"]:g for g in games}
    rows=[dict(r,**{k:float(r[k]) for k in ("p_home","p_draw","p_away")},outcome_index=by_id[r["match_id"]]["outcome"])
          for r in read_rows(normal/"prematch_features.csv")]
    ids={g["match_id"] for g in games if g["study"]}
    base=frequency(games,1950);elo=fixed_step(games,40,100,.75,1950)
    legacy=[]
    for a,b in [(1980,2009),(2010,2019),(2020,2022),(2023,2024)]:
        legacy.extend(gate(rows,base,elo,dict(id=f"legacy_reused_{a}_{b}",start=f"{a}-01-01",end=f"{b}-12-31"),ids,cfg))
    type_rows=read_rows(normal/"type_metrics.csv")
    max_type_bias=max(abs(float(r["home_bias"])) for r in type_rows)
    simulation_report=json.loads((simulation/"report.json").read_text(encoding="utf-8"))
    jump_report=json.loads((jump/"report.json").read_text(encoding="utf-8"))
    reproduction_path=ROOT/"outputs/logs/strength/review-20261029/reproducibility.json"
    reproduction=json.loads(reproduction_path.read_text(encoding="utf-8"))
    strict_reviews=[]
    for path in sr["candidate_directories"].values():
        review=ROOT/"outputs/logs/strength/review-20261029"/(Path(path).name+".json")
        strict_reviews.append(json.loads(review.read_text(encoding="utf-8")))
    technical=(audit["passed"] and all(r["passed"] for r in strict_reviews) and all(r["passed"] for r in diffs)
               and same_choices and reproduction["passed"] and reproduction["directory"]==normal.relative_to(ROOT).as_posix())
    performance=report["experimental_input_performance_gate_passed"]
    admitted=technical and performance and simulation_report["matched_generator_check_passed"]
    original_gates=report["forecast_engineering_gate_passed"] and all(r["passed"] for r in legacy)
    release=dict(stage2_acceptance_and_handoff_completed=True,
        experimental_joint_input_admitted=admitted,technical_gate_passed=technical,
        pooled_original_forecast_gates_passed=original_gates,
        max_era_type_home_bias=max_type_bias,type_specific_three_pp_screen_passed=max_type_bias<=.03,
        unrestricted_or_prospective_forecast_admitted=False,
        reason="Reused history cannot certify future accuracy; type-specific residual calibration remains; only exploratory joint design/input released",
        complex_jump_admitted=jump_report["global_prediction_admitted"],jump_disposition=jump_report["disposition"],
        strict_annual_choices_identical=same_choices,study_rows=24917,
        accepted_reference=normal.relative_to(ROOT).as_posix(),strict_reference=strict.relative_to(ROOT).as_posix(),
        audit=review_path.relative_to(ROOT).as_posix(),simulation=simulation.relative_to(ROOT).as_posix(),
        jump_followup=jump.relative_to(ROOT).as_posix(),
        initialization_sensitivity=initialization.relative_to(ROOT).as_posix(),
        reproduction=reproduction_path.relative_to(ROOT).as_posix(),
        uncertainty="conditional within-filter covariance only; model alternatives are sensitivity, not confidence bounds",
        conditional_identity_eligibility=True,human_review="not_performed",joint_fit_performed=False)
    if not admitted:raise RuntimeError("Exploratory input gate failed; joint interface not released")
    source=ROOT/"outputs/tables/regions/regions-0a1c61664a722e6c641f/analysis_matches.csv"
    facts=read_rows(source);features={r["match_id"]:r for r in read_rows(normal/"study_prematch_features.csv")}
    if len(features)!=24917 or len(facts)!=24917 or {r["match_id"] for r in facts}!=features.keys():
        raise ValueError("Joint join changed original population")
    retained=("match_id","date","year","era","tournament_group","home_team_id","away_team_id","home_team","away_team",
              "home_region","home_unit","away_region","away_unit","direction","relation","home_win","outcome","result_basis")
    predictor_whitelist=["strength_difference","era","tournament_group","home_region","away_region","home_unit","away_unit","relation"]
    initial_by_id={mid:[] for mid in features}
    for r in read_rows(initialization/"study_differences.csv"):
        initial_by_id[r["match_id"]].append(r)
    if any(len(v)!=3 for v in initial_by_id.values()):raise ValueError("Incomplete initialization sensitivity")
    joined=[]
    for fact in facts:
        r=features[fact["match_id"]]
        if fact["date"]!=r["date"] or r["prediction_cutoff"]>=r["date"] and r["prediction_cutoff"]!="initial_prior":
            raise ValueError("Date mismatch or temporal leak")
        gaps=[float(index[fact["match_id"]]["difference"]) for index in indexes.values()]
        initial=initial_by_id[fact["match_id"]]
        initial_gaps=[float(x["difference"]) for x in initial]+[float(indexes["smooth_static"][fact["match_id"]]["difference"])]
        initial_prob=max(float(x["max_probability_difference"]) for x in initial)
        joined.append(dict(**{k:fact[k] for k in retained},
            strength_difference=float(r["difference"]),strength_difference_variance=float(r["difference_variance"]),
            home_rating_entity=r["home"],away_rating_entity=r["away"],
            home_mean=float(r["home_mean"]),away_mean=float(r["away_mean"]),
            home_variance=float(r["home_variance"]),away_variance=float(r["away_variance"]),
            home_away_covariance=float(r["home_away_covariance"]),
            home_history=int(r["home_history"]),away_history=int(r["away_history"]),
            cold_start=r["cold_start"]=="true",previously_disconnected=r["previously_disconnected"]=="true",
            prediction_cutoff=r["prediction_cutoff"],selector_information_cutoff=r["selector_information_cutoff"],
            selected_model=r["selected_model"],rating_run_id=r["rating_run_id"],rating_rules_version=r["rating_rules_version"],
            selector_version=normal.name,alternative_gap_min=min(gaps),alternative_gap_max=max(gaps),
            initialization_gap_min=min(initial_gaps),initialization_gap_max=max(initial_gaps),
            initialization_max_probability_change=initial_prob,initialization_sensitive=initial_prob>.01))
    support=[]
    for variable in ("era","tournament_group","home_region","home_unit","away_region","relation"):
        counts=Counter(r[variable] for r in joined)
        for level,count in sorted(counts.items()):
            subset=[r for r in joined if r[variable]==level]
            support.append(dict(variable=variable,level=level,matches=count,
                cold_start=sum(r["cold_start"] for r in subset),
                initialization_sensitive=sum(r["initialization_sensitive"] for r in subset),
                strength_difference_min=min(r["strength_difference"] for r in subset),
                strength_difference_max=max(r["strength_difference"] for r in subset),
                mean_difference_variance=float(np.mean([r["strength_difference_variance"] for r in subset]))))
    folder,_=publish("joint-input",{"rating_manifest_sha":file_hash(normal/"manifest.json"),"region_input_sha":file_hash(source),
        "audit_sha":file_hash(review_path),"runner_sha":file_hash(Path(__file__)),"strict_manifest_sha":file_hash(strict/"manifest.json"),
        "initialization_manifest_sha":file_hash(initialization/"manifest.json"),"reproduction_sha":file_hash(reproduction_path)},
        csvs={"analysis_matches.csv":joined,"support.csv":support,"full_scale_numeric_comparison.csv":diffs},
        jsons={"release.json":release,"legacy_period_checks.json":legacy,
            "interface.json":dict(status="design_input_only_no_joint_fit",target="home_win; draws remain in denominator",
                predictor_whitelist=predictor_whitelist,forbidden_predictors=["home_win","outcome","home_score","away_score","p_home","p_draw","p_away","home_term"],
                strength_variance_is_not_case_weight=True,alternative_gap_range_is_not_CI=True,
                geography="unchanged Q3 mappings; nested main effects must not be entered redundantly")},
        texts={"data_dictionary.md":"# 第五问第三环节的准备输入\n\n24917行，一场一行，主结果home_win、平局仍计分母；outcome留作三结果备选。strength_difference为当场双方赛前评分差，variance为同一候选联合协方差推得。home/away_mean和协方差仅作追踪，不把绝对原点当实质水平。home/away_rating_entity区分评分身份与地理球队。alternative_gap_min/max为七候选分差范围，绝非置信区间。initialization_gap_min/max和max_probability_change来自单峰固定规则的起点/方差对照，不是滚动评分的置信区间；initialization_sensitive只标记差异超过1个百分点，不证明该场评分错误。predictor_whitelist只是候选集合，不能把其全部冗余编码同时放进回归。此包没有联合模型拟合、系数或效果结论。\n",
            "runner_snapshot.py":Path(__file__).read_text(encoding="utf-8")},
        base_dir="data/processed/strength")
    print("JOINT_INPUT",folder.relative_to(ROOT).as_posix(),json.dumps(release,ensure_ascii=False),flush=True)
    return folder


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--normal",required=True);p.add_argument("--strict",required=True)
    p.add_argument("--jump",required=True);p.add_argument("--simulation",required=True);p.add_argument("--initialization",required=True);a=p.parse_args()
    run(*(ROOT/getattr(a,k) for k in ("normal","strict","jump","simulation","initialization")))
