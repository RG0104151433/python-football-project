"""Final interface, source, document and recorded-proof checks for this handoff."""
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.strength.io import read_rows
from src.data_contract import file_hash,write_json


def run():
    total=0;failed=[]
    def check(label,value):
        nonlocal total
        total+=1
        if not value:failed.append(label)
    base=ROOT/"data/processed/strength/joint-input-0812683da0560b0b687b"
    m=json.loads((base/"manifest.json").read_text(encoding="utf-8"))
    for n,d in m["outputs"].items():check("joint_hash:"+n,file_hash(base/n)==d)
    release=json.loads((base/"release.json").read_text(encoding="utf-8"))
    rows=read_rows(base/"analysis_matches.csv")
    facts={r["match_id"]:r for r in read_rows(ROOT/"outputs/tables/regions/regions-0a1c61664a722e6c641f/analysis_matches.csv")}
    check("joint_population",len(rows)==24917 and len({r["match_id"] for r in rows})==24917 and {r["match_id"] for r in rows}==facts.keys())
    check("no_postmatch_predictors",not any(k in rows[0] for k in ("home_score","away_score","p_home","home_term")))
    for r in rows:
        mid=r["match_id"];old=facts[mid]
        check("original_labels:"+mid,all(r[k]==old[k] for k in ("date","home_win","outcome","era","tournament_group","home_unit","away_unit","home_region","away_region")))
        h,a,c,v=map(float,(r["home_variance"],r["away_variance"],r["home_away_covariance"],r["strength_difference_variance"]))
        check("joint_covariance:"+mid,h>0 and a>0 and v>0 and c*c<=h*a+1e-8 and abs(v-(h+a-2*c))<1e-8)
        check("initial_flag:"+mid,(r["initialization_sensitive"]=="true")== (float(r["initialization_max_probability_change"])>.01))
        check("before_date:"+mid,r["prediction_cutoff"]<r["date"] and r["selector_information_cutoff"]<r["date"])
    check("raw_unchanged",file_hash(ROOT/"data/raw/international_results/results.csv")=="5dcefd1aa0483979ea8378cef5be448d2005609d39945ea162378561a30a6767")
    check("clean_unchanged",file_hash(ROOT/"data/processed/prep-3fab808178cf8ad71d88/matches_clean.csv")=="69ba00073970fe011a62f5871c08ace6285d7fe75d5a0d79afdac0ef972de9dc")
    for name in ("analysis_matches.csv","support.csv","full_scale_numeric_comparison.csv"):
        data=(base/name).read_bytes();check("encoding_lf:"+name,data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data)
    docs=["README.md","研究/README.md","研究/05_赛前实力/README.md",
        "研究/05_赛前实力/第二环节_验收与正式交接.md","研究/05_赛前实力/第三环节_联合分析准备与接口.md",
        "文档/05_团队协作/论文与汇报支撑材料索引.md"]
    for name in docs:
        p=ROOT/name;text=p.read_text(encoding="utf-8-sig")
        for link in re.findall(r"\]\(([^)]+)\)",text):
            if "://" in link or link.startswith(("#","mailto:")):continue
            target=link.split("#",1)[0].strip("<>")
            if target:check("link:"+name+":"+target,(p.parent/target).resolve().exists())
    log=(ROOT/"文档/01_项目方案/研究日志与决策记录.md").read_text(encoding="utf-8-sig")
    ids=re.findall(r"^### (R\d{8}-\d+)\b",log,re.M)
    check("unique_log_ids",len(ids)==len(set(ids)))
    state=json.loads((ROOT/"研究/pipeline_state.json").read_text(encoding="utf-8-sig"))["question_5"]
    check("pipeline_release",state["acceptance_handoff"]["joint_input"]==base.relative_to(ROOT).as_posix() and state["acceptance_handoff"]["stage2_completed"])
    check("production_not_misreported",not state["acceptance_handoff"]["unrestricted_forecast_admitted"])
    # Preserve the exact auxiliary runners and tests that supplement core archives.
    files=[*ROOT.glob("scripts/*strength*.py"),*ROOT.glob("tests/test_strength*.py"),
           ROOT/"config/strength_handoff.json",ROOT/"config/strength_context_v4.json",ROOT/"config/strength_context_v4_strict.json"]
    saved={}
    for p in files:
        digest=file_hash(p);destination=ROOT/"outputs/logs/strength/review-20261029/source_snapshots"/digest/p.name
        destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists():shutil.copyfile(p,destination)
        check("aux_source_snapshot:"+p.name,file_hash(destination)==digest)
        saved[p.relative_to(ROOT).as_posix()]=dict(sha256=digest,path=destination.relative_to(ROOT).as_posix())
    out=ROOT/"outputs/logs/strength/review-20261029"
    write_json(out/"auxiliary_sources.json",saved)
    review=dict(passed=not failed,checks=total,failed=failed,study_rows=len(rows),
        cold_start=sum(r["cold_start"]=="true" for r in rows),
        initialization_sensitive=sum(r["initialization_sensitive"]=="true" for r in rows),
        previously_disconnected=sum(r["previously_disconnected"]=="true" for r in rows),
        stage2_acceptance_completed=release["stage2_acceptance_and_handoff_completed"],
        experimental_input_admitted=release["experimental_joint_input_admitted"],
        original_forecast_gates_passed=release["pooled_original_forecast_gates_passed"],
        unrestricted_forecast_admitted=False,human_review="not_performed",joint_fit_performed=False)
    write_json(out/"delivery_review.json",review);print(json.dumps(review,ensure_ascii=False),flush=True)
    if failed:raise SystemExit(1)


if __name__=="__main__":run()
