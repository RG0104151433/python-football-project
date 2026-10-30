"""Rebuild rolling choices and numeric comparisons from saved CSV and outcomes."""
from pathlib import Path
from collections import defaultdict
import argparse
import csv
import hashlib
import json
import math
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from audit_strength_global_outputs import audit


def read(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))


def run(folder):
    total=0;failures=[]
    def check(label,ok):
        nonlocal total
        total+=1
        if not ok:failures.append(label)
    report=json.loads((folder/"report.json").read_text(encoding="utf-8"))
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    for name,digest in manifest["outputs"].items():check("rolling_hash:"+name,hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest)
    source=read(ROOT/report["protocol"]["learning"]/"learning_matches.csv")
    lookup={r["match_id"]:r for r in source}
    study={r["match_id"] for r in source if r["accepted_current_study"]=="true"}
    indexes={};candidate_reviews={}
    for model,path in report["candidate_directories"].items():
        d=ROOT/path
        result=audit(d);candidate_reviews[model]=result
        check("candidate_audit:"+model,result["passed"])
        total+=result["checks"]
        if not result["passed"]:failures.extend(model+":"+f for f in result["failed"])
        check("candidate_manifest_binding:"+model,hashlib.sha256((d/"manifest.json").read_bytes()).hexdigest()==manifest["identity"]["candidate_manifests"][model])
        indexes[model]={r["match_id"]:r for r in read(d/"prematch_features.csv")}
    rolling=read(folder/"prematch_features.csv");rs=read(folder/"study_prematch_features.csv")
    expected={r["match_id"] for r in source if "1980-01-01"<=r["date"]<="2024-12-31"}
    check("all_rolling_ids",len(rolling)==len(expected) and {r["match_id"] for r in rolling}==expected)
    check("study_population",len(rs)==24917 and {r["match_id"] for r in rs}==study)
    check("target_not_in_features",not any(k in rolling[0] for k in ("outcome_index","home_score","away_score","home_win")))
    table=read(folder/"annual_choices.csv")
    chosen={}
    proto=report["protocol"];complexity={c["id"]:c["modules"] for c in proto["candidates"]}
    yearly_losses=defaultdict(dict)
    for year in range(1980,2025):
        ids=[r["match_id"] for r in source if year-10<=int(r["date"][:4])<year]
        losses={model:-sum(math.log(float(index[mid][("p_home","p_draw","p_away")[int(lookup[mid]["outcome_index"])]])) for mid in ids)/len(ids)
                for model,index in indexes.items()}
        best=min(losses.values());limit=best+proto["rolling"]["complexity_loss_margin"]
        winner=sorted([m for m in losses if losses[m]<=limit],key=lambda m:(complexity[m],losses[m],m))[0]
        chosen[year]=winner
        for row in (r for r in table if int(r["year"])==year):
            check("choice_loss:"+str(year)+row["model"],abs(float(row["log_loss"])-losses[row["model"]])<1e-8)
            check("choice_winner:"+str(year)+row["model"],(row["chosen"]=="true")== (row["model"]==winner))
    for r in rolling:
        year=int(r["date"][:4]);model=chosen[year];mid=r["match_id"]
        check("selected_model:"+mid,r["selected_model"]==model)
        check("selector_cutoff:"+mid,r["selector_information_cutoff"]==f"{year-1}-12-31")
        check("selected_values:"+mid,all(r[k]==v for k,v in indexes[model][mid].items()))
    old_to_new={"smooth_static":"ratings-27b4f4352e5aec283bde","robust_static":"ratings-48789d1ab6c8a11da620"}
    equality={}
    ignored={"rating_run_id","rating_rules_version"}
    for model,old in old_to_new.items():
        previous=read(ROOT/"data/processed/strength"/old/"prematch_features.csv")
        count=0
        for r in previous:
            s=indexes[model][r["match_id"]]
            ok=all(v==s[k] for k,v in r.items() if k not in ignored)
            check("checkpoint_fix_did_not_change_continuous_features:"+model+r["match_id"],ok);count+=ok
        equality[model]=dict(rows=len(previous),identical_rows=count,ignored=list(sorted(ignored)))
    # Recompute pooled scoring from the target-free saved features plus raw targets.
    for m in report["external_checks"]:
        p=next(p for p in proto["check_blocks"] if f"reused_{p[0]}_{p[1]}"==m["period"])
        ss=[r for r in rolling if p[0]<=int(r["date"][:4])<=p[1] and (m["scope"]=="all_learning" or r["match_id"] in study)]
        loss=-sum(math.log(float(r[("p_home","p_draw","p_away")[int(lookup[r["match_id"]]["outcome_index"])]])) for r in ss)/len(ss)
        bias=sum(float(r["p_home"])-int(lookup[r["match_id"]]["outcome_index"]=="0") for r in ss)/len(ss)
        check("metric:"+m["period"]+m["scope"],len(ss)==m["count"] and abs(loss-m["log_loss"])<1e-8 and abs(bias-m["home_probability_bias"])<1e-8)
    result=dict(passed=not failures,checks=total,failed=failures,candidate_audits=candidate_reviews,
        fixed_checkpoint_replay_equality=equality,source=folder.relative_to(ROOT).as_posix(),
        human_review="not_performed",scope="saved arithmetic/chronology/source/restart; not latent truth or prospective validation")
    out=ROOT/"outputs/logs/strength/review-20261029"/(folder.name+".json")
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="candidate_audits"}),flush=True)
    if failures:raise SystemExit(1)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("folder");run(ROOT/p.parse_args().folder)
