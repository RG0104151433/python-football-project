"""Independent artifact/count/formula audit. Does not fit an interval method."""
from collections import Counter,defaultdict
import csv
import hashlib
import json
import math
from datetime import datetime,timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def load(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def readcsv(path):return list(csv.DictReader(Path(path).open(encoding="utf-8-sig",newline="")))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    checks=[]
    def check(ok,label):
        if not ok:raise AssertionError(label)
        checks.append(label)
    logs=ROOT/"outputs/logs/reliability"
    archive=load(logs/"implementation-20261028/source_archive/index.json")
    archive_lookup={(a["original"],a["sha256"]):a["archive"] for a in archive}
    runs=[]
    registry=load(logs/"implementation-20261028/current_runs.json")
    for manifest_path in registry["runs"]:
        folder=(ROOT/manifest_path).parent
        man=load(folder/"run_manifest.json")
        check(man["status"]!="running","finished run:"+folder.name)
        for path,expected in man["outputs"].items():check(sha(ROOT/path)==expected,"output hash:"+path)
        for path,expected in man["code_and_config"].items():
            snapshot=man.get("source_snapshot",{}).get(path) or archive_lookup.get((path,expected))
            check(snapshot is not None and sha(ROOT/snapshot)==expected,"executed source recoverable:"+folder.name+":"+path)
        check(man.get("production_estimator") is None,"no unapproved production estimator:"+folder.name)
        runs.append(dict(run=folder.relative_to(ROOT).as_posix(),status=man["status"],summary=man["summary"]))
    old=load(logs/"design-20261027T131754720415Z-c2a82843/run_manifest.json")
    bindings={**old["inputs"],**old["code"],**old["outputs"],**old["parent_outputs_unchanged"]}
    for p,h in bindings.items():check(sha(ROOT/p)==h,"parent untouched:"+p)
    fullG=next(r for r in runs if "/refined-graph-" in r["run"])
    table=readcsv(ROOT/fullG["run"]/"graph_refinement.csv")
    check(len(table)==990,"198 targets times5 graph ranges")
    cfg=load(ROOT/"config/reliability_validation_v1.json")
    cat=readcsv(logs.parent.parent/"tables/reliability/design-e1ebd48827f8a5ff4be8/target_catalogue.csv")
    family={r["target_id"]:r["family"] for r in cat if r["status"]=="supported_point_target"}
    check(len(cat)==292 and len(family)==198,"292 catalogue198 supported94 retained")
    check(Counter(family.values())==Counter(cfg["scope"]["families"]),"family sizes unchanged")
    for r in table:
        j=r["target_id"];m=cfg["scope"]["families"][family[j]]
        C=float(r["G2_C"]);previous=float(r["G1_C"]);half=float(r["halfwidth"]);span=float(r["logical_span"])
        check(C<=previous+1e-12,"weighted constant no worse:"+j+":"+r["L_days"])
        check(abs(half-math.sqrt(C/2*math.log(2*m/.05)))<1e-12,"finite bound formula:"+j+":"+r["L_days"])
        delta=.05/(2*m)
        selected=2*half>=(1-delta)*span
        check(selected==(r["G3_markov_selected"]=="True"),"outcome-free bound choice:"+j+":"+r["L_days"])
        expected=(1-delta)*span if selected else min(2*half,span)
        check(abs(expected-float(r["G3_maximum_width"]))<1e-12,"maximum width:"+j+":"+r["L_days"])
    # Rebuild intervals using the already independently checked old coefficient
    # interface, then use plain scalar inequalities, not new interval helpers.
    sys.path.insert(0,str(ROOT))
    from src.reliability.design import build_design
    context=build_design(ROOT)
    target_ids=[t["target_id"] for t in context["catalogue"] if t["target_id"] in context["vectors"]]
    logical_low=[];logical_high=[]
    for tid in target_ids:
        a=context["vectors"][tid]
        logical_low.append(math.fsum(float(v) for v in a if v<0))
        logical_high.append(math.fsum(float(v) for v in a if v>0))
    fids={f:[j for j,tid in enumerate(target_ids) if family[tid]==f] for f in cfg["scope"]["families"]}
    agg=[]
    for run in runs:
        folder=ROOT/run["run"]
        if not (folder/"replications.jsonl").exists():continue
        actual=defaultdict(lambda:[0,0,0])
        for line in (folder/"replications.jsonl").read_text(encoding="utf-8").splitlines():
            rep=json.loads(line)
            if "halfwidth" in rep:
                for method,c in (("P2-fast-same-law",1),("P3-trained-inflation",2)):
                    for f,ids in fids.items():
                        covered=all(max(rep["estimate"][j]-c*rep["halfwidth"][j],logical_low[j])<=rep["truth"][j]+1e-12
                            and min(rep["estimate"][j]+c*rep["halfwidth"][j],logical_high[j])>=rep["truth"][j]-1e-12 for j in ids)
                        check(covered==rep["methods"][method][f]["covered"],"independent scalar interval coverage:"+str((rep["scenario"],rep["replication"],method,f)))
            for name,result in rep["methods"].items():
                # Original runs store {ok,metrics}; refined runs use family map.
                metrics=result.get("metrics",{}) if "ok" in result else result
                families=list(cfg["scope"]["families"]) if run["summary"]["n"]==24917 else ["CORE","CONDITIONAL","AUX"]
                for f in families:
                    ok=result.get("ok",rep.get("ok",True));value=metrics.get(f,{})
                    a=actual[(rep["scenario"],name,f)];a[0]+=1;a[1]+=bool(ok and value.get("covered",False));a[2]+=not ok
        if (folder/"metrics.csv").exists():
            for row in readcsv(folder/"metrics.csv"):
                key=(row["scenario"],row["method"],row["family"])
                check(key in actual,"every reported metric has replicate evidence:"+folder.name+":"+str(key))
                R,k,fail=actual[key]
                check(R==int(row["R"]) and k==int(row["covered"]) and fail==int(row["failures"]),"independent replicate totals:"+folder.name+":"+str(key))
        agg.append(dict(run=run["run"],group_count=len(actual)))
    train=load(logs/"iteration-20261028/calibration_training.json")
    hold=load(logs/"iteration-20261028/calibration_holdout.json")
    check(train["selected_multiplier"]==hold["selected_multiplier"]==2,"locked multiplier retained in holdout")
    check(train["replications"]=="0..49" and hold["replications"]=="50..99","disjoint calibration splits")
    check(not train["formal_acceptance"] and not hold["formal_acceptance"],"small holdout not formal acceptance")
    for doc in (train,hold):
        original=archive_lookup.get(("scripts/calibrate_reliability.py",doc["script_sha256"]))
        check(original is not None and sha(ROOT/original)==doc["script_sha256"],"original calibration script preserved:"+doc["stage"])
    localization=load(logs/"iteration-20261028/failure_localization.json")
    pv=sum(math.comb(10,k)*.94**k*.06**(10-k) for k in range(6))
    check(abs(pv-localization["supplemental_negative_result"]["one_sided_exact_binomial_tail"])<1e-15,"exact binomial negative-result check")
    check(abs(144*pv-localization["supplemental_negative_result"]["Bonferroni144"])<1e-15,"144-cell multiplicity counted")
    for r in runs:
        if "/refined-full-graph-oracle-" not in r["run"]:continue
        folder=ROOT/r["run"];ref=load(folder/"oracle_reference.json")
        check(len(ref)==18,"18 known-generator references separated from fitted model")
        for entry in ref:check(entry["not_fitted_MP_validation"] and entry["calibration"]["B"]==9999,"oracle labelling:"+entry["scenario"])
        for sc in cfg["simulations"]["scenarios"]:
            states=load(folder/(sc["id"]+"_random_states.json"))
            check(sum(x["B"] for x in states)==5000,"fixed full-scale graph repetitions:"+sc["id"])
            check(len({x["offset"] for x in states})==len(states),"unique batch keys:"+sc["id"])
        for row in readcsv(folder/"metrics.csv"):
            check(int(row["R"])==5000 and int(row["failures"])==0,"complete graph/oracle metric:"+str((row["scenario"],row["method"],row["family"])))
    result=dict(status="passed_artifact_and_count_audit_not_statistical_model_approval",checks=len(checks),
        original_bindings_unchanged=len(bindings),runs=runs,replication_totals=agg,check_labels=checks,
        human_review="not_performed",production_estimator=None,audit_script_sha256=sha(Path(__file__)))
    path=logs/"implementation-20261028/independent_audit.json"
    if path.exists():
        stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path=logs/"implementation-20261028"/("independent_recheck-"+stamp+".json")
    path.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(dict(checks=len(checks),runs=len(runs),old_bindings_unchanged=len(bindings),output=path.relative_to(ROOT).as_posix())))


if __name__=="__main__":main()
