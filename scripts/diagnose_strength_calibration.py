"""Class-bias diagnosis using <=2009 only; do not inspect reserved outcome scores."""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def rows(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))


def summary(rs):
    n=len(rs)
    return dict(count=n,**{name+"_bias":sum(float(r["p_"+name])-int(int(r["outcome_index"])==k)
                         for r in rs)/n for k,name in enumerate(("home","draw","away"))})


def main():
    selection=ROOT/"outputs/logs/strength/global-selection-00297d6d90d6157b72aa"
    grouped=defaultdict(list)
    for r in rows(selection/"validation_predictions.csv"):
        if r["start"]=="1950":grouped[r["model"]].append(r)
    val=[dict(model=k,**summary(v)) for k,v in sorted(grouped.items())]
    source=ROOT/"outputs/logs/strength/learning-b2889411cc93b44f88b6/learning_matches.csv"
    outcomes={r["match_id"]:r for r in rows(source) if r["date"]<="2009-12-31"}
    features=ROOT/"data/processed/strength/ratings-f0cf0ec2131490aeabb8/prematch_features.csv"
    grouped=defaultdict(list)
    for r in rows(features):
        if not "1980"<=r["date"]<="2009-12-31":continue
        truth=outcomes[r["match_id"]]
        item=dict(r,outcome_index=truth["outcome_index"])
        key=(r["date"][:3]+"0s",truth["tournament_group"],truth["is_neutral"])
        grouped[key].append(item)
    actual=[dict(era=e,tournament=t,neutral=n,**summary(v)) for (e,t,n),v in sorted(grouped.items())]
    target=ROOT/"outputs/logs/strength/calibration-diagnosis-20261029/diagnosis.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(dict(validation_candidates=val,early_external=actual,
          diagnostic_scope="pre1980 selection plus1980-2009;2010-2019 acceptance already observed;2020-2024 untouched"),
          ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"validation":val,"early_external":actual},ensure_ascii=False))


if __name__=="__main__":main()
