"""Independent arithmetic/input/time/checkpoint audit of completed ratings."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse
import csv
import hashlib
import json
import math
import sys
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.gaussian import GaussianStrengthFilter


def read(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def canonical(v):
    return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def audit(folder):
    results=[]
    def check(label,value):results.append((label,bool(value)))
    m=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    for n,s in m["outputs"].items():check("hash:"+n,sha(folder/n)==s)
    with zipfile.ZipFile(folder/"source_snapshot.zip") as z:
        for n,s in m["identity"]["code"].items():
            check("snapshot:"+n,canonical(z.read(n).decode("utf-8").replace("\r\n","\n"))==s)
    inputs=m["identity"]["inputs"]
    for n,s in inputs.items():check("input:"+n,sha(ROOT/n)==s)
    source_path=next(ROOT/n for n in inputs if n.endswith("learning_matches.csv"))
    source=read(source_path)
    lookup={r["match_id"]:r for r in source}
    features=read(folder/"prematch_features.csv")
    study=read(folder/"study_prematch_features.csv")
    ids={r["match_id"] for r in features}
    expected_study={r["match_id"] for r in source if r["accepted_current_study"]=="true"}
    check("unique_feature_ids",len(ids)==len(features))
    check("study_population",len(study)==24917 and {r["match_id"] for r in study}==expected_study)
    check("target_columns_absent",not any(k in features[0] for k in ("outcome_index","home_score","away_score","home_win")))
    counts=Counter()
    days=defaultdict(list)
    for r in features:days[r["date"]].append(r)
    for day,batch in sorted(days.items()):
        for r in batch:
            mid=r["match_id"];raw=lookup[mid]
            check("date:"+mid,r["date"]==raw["date"])
            check("entity:"+mid,r["home"].split("@")[0]==raw["home_entity_id"].split("@")[0] and r["away"].split("@")[0]==raw["away_entity_id"].split("@")[0])
            check("cutoff:"+mid,r["prediction_cutoff"]=="initial_prior" or r["prediction_cutoff"]<day)
            probs=[float(r[k]) for k in ("p_home","p_draw","p_away")]
            check("prob:"+mid,all(math.isfinite(p) and 0<=p<=1 for p in probs) and abs(sum(probs)-1)<3e-9)
            vh,va,c=[float(r[k]) for k in ("home_variance","away_variance","home_away_covariance")]
            check("cov:"+mid,vh>0 and va>0 and c*c<=vh*va+2e-9 and abs(float(r["difference_variance"])-(vh+va-2*c))<6e-9)
            check("mean:"+mid,abs(float(r["difference"])-(float(r["home_mean"])-float(r["away_mean"])))<3e-9)
            check("history:"+mid,int(r["home_history"])==counts[r["home"]] and int(r["away_history"])==counts[r["away"]])
        for r in batch:counts[r["home"]]+=1;counts[r["away"]]+=1
    report=json.loads((folder/"rating_report.json").read_text(encoding="utf-8"))
    for metric in report["external_checks"]:
        period=next(p for p in report["holdout_roles"] if p["id"]==metric["period"])
        selected=[r for r in features if period["start"]<=r["date"]<=period["end"] and
                  (metric["scope"]=="all_learning" or r["match_id"] in expected_study)]
        n=len(selected)
        loss=brier=bias=0.
        correct_min=correct_max=0
        for r in selected:
            p=[float(r[k]) for k in ("p_home","p_draw","p_away")]
            y=int(lookup[r["match_id"]]["outcome_index"])
            loss-=math.log(p[y])
            brier+=sum((v-int(k==y))**2 for k,v in enumerate(p))
            bias+=p[0]-int(y==0)
            tied=[k for k,v in enumerate(p) if max(p)-v<2e-10]
            correct_max+=y in tied
            correct_min+=tied==[y]
        check("metric:"+metric["period"]+metric["scope"],n==metric["count"] and
              abs(loss/n-metric["log_loss"])<4e-9 and abs(brier/n-metric["brier"])<4e-9 and
              abs(bias/n-metric["home_probability_bias"])<4e-9 and
              correct_min/n-1e-12<=metric["accuracy"]<=correct_max/n+1e-12)
    checkpoints=json.loads((folder/"checkpoints.json").read_text(encoding="utf-8"))
    for key,s in checkpoints.items():
        st=s["state"]
        check("checkpoint_cutoff:"+key,st["last_day"]<=key and all(day<=key for day in st["last"].values()))
        check("checkpoint_psd:"+key,np.linalg.eigvalsh(np.array(st["cov"])).min()>=-1e-8)
    first=checkpoints["1979-12-31"]["state"]
    future_day=min(r["date"] for r in features if r["date"]>"1979-12-31")
    gs=[dict(match_id=r["match_id"],date=r["date"],home=r["home_entity_id"],away=r["away_entity_id"],
             venue=0 if r["is_neutral"]=="true" else 1,friendly=r["tournament_group"]=="friendly",outcome=int(r["outcome_index"]))
        for r in source if r["date"]==future_day]
    if all(day<future_day for day in first["last"].values()):
        restored=GaussianStrengthFilter.restore(first)
        forecast=restored.day(future_day,gs)
        expected={r["match_id"]:r for r in features if r["date"]==future_day}
        check("checkpoint1980_predictions",all(max(abs(r[k]-float(expected[r["match_id"]][k])) for k in
            ("p_home","p_draw","p_away","difference","difference_variance"))<2e-9 for r in forecast))
    else:
        check("checkpoint1980_predictions_not_restorable_due_future_dates",False)
    return dict(passed=all(ok for _,ok in results),checks=len(results),failed=[label for label,ok in results if not ok],
        source=folder.relative_to(ROOT).as_posix(),rows=len(features),study_rows=len(study),
        model_admission=report["external_prediction_gate_passed"],
        scope="independent arithmetic/input/chronology/restart only, not model validity or human review")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("directories",nargs="+")
    args=parser.parse_args()
    output=ROOT/"outputs/logs/strength/review-20261029"
    output.mkdir(parents=True,exist_ok=True)
    for value in args.directories:
        folder=(ROOT/value).resolve()
        if not folder.is_relative_to(ROOT):raise ValueError("Outside workspace")
        result=audit(folder)
        (output/(folder.name+".json")).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False),flush=True)
        if not result["passed"]:raise SystemExit(1)


if __name__=="__main__":main()
