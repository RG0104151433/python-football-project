"""Develop bounded target-tail adaptation, then require new independent tests."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
from pathlib import Path
import sys
import json
import gzip
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from src.reliability.experiment import actual_design,write_json,write_csv
from src.reliability.models import truth_margin
from src.reliability.joint import finite_calibration_critical
from src.reliability.design import sha


def main(long_memory=False,wide=False):
    parent=ROOT/"outputs/logs/reliability/joint-final-20261028"
    cfg=json.loads((ROOT/"config/reliability_joint_v11.json").read_text(encoding="utf-8-sig"))
    if long_memory:
        cfg["required_scenarios"].append("C13")
        cfg["outside_calibration_stress"].remove("C13")
    choice=json.loads((parent/"model_selection.json").read_text(encoding="utf-8"));name=choice["selected_model"]
    source="outputs/logs/reliability/joint-v10-20261028/development-20261028T045026413031Z"
    with gzip.open(ROOT/source/"replications.jsonl.gz","rt",encoding="utf-8") as stream:records=[json.loads(s) for s in stream]
    d,_=actual_design(ROOT)
    scenarios={s["id"]:s for s in json.loads((ROOT/"config/reliability_validation_v1.json").read_text(encoding="utf-8-sig"))["simulations"]["scenarios"]}
    truths={sid:d.apply(truth_margin(d,sc)) for sid,sc in scenarios.items()}
    tails=[]
    for sid in cfg["required_scenarios"]:
        ratios=[]
        for r in records:
            if r["scenario"]!=sid or r["replication"]>=50:continue
            scale=np.array(r["models"][name]["scale"]);error=np.abs(r["estimate_error"])
            ratios.append(np.divide(error,scale,out=np.zeros(len(scale)),where=scale>0))
        tails.append(np.quantile(ratios,.95,axis=0,method="higher"))
    raw=np.max(tails,axis=0);bounded=np.ones(len(raw))
    for f,ids in d.families.items():
        positive=raw[ids][raw[ids]>1e-10];median=float(np.median(positive)) if len(positive) else 1.
        bounded[ids]=np.clip(raw[ids],(.1 if wide else .5)*median,(10 if wide else 2)*median)
    comparisons=[];allcrit={}
    for gamma in (0,.5,1.):
        factor=bounded**gamma;critical={}
        for f,ids in d.families.items():
            byworld=[]
            for sid in cfg["required_scenarios"]:
                scores=[]
                for r in records:
                    if r["scenario"]!=sid or r["replication"]>=50:continue
                    scale=np.array(r["models"][name]["scale"])*factor
                    scores.append(float(np.max(np.divide(np.abs(np.array(r["estimate_error"])[ids]),scale[ids],out=np.zeros(len(ids)),where=scale[ids]>0))))
                byworld.append(finite_calibration_critical(scores,.025))
            critical[f]=max(byworld)
        allcrit[str(gamma)]=critical;qual=True;width=[]
        for sid in cfg["required_scenarios"]:
            check=[r for r in records if r["scenario"]==sid and r["replication"]>=50]
            for f,ids in d.families.items():
                k=0;ww=[]
                for r in check:
                    scale=np.array(r["models"][name]["scale"])*factor
                    half=critical[f]*scale[ids];err=np.array(r["estimate_error"])[ids]
                    k+=bool(np.all(np.abs(err)<=half+1e-12))
                    est=truths[sid][ids]+err
                    ww.append(float(np.mean(np.minimum(est+half,d.hi[ids])-np.maximum(est-half,d.lo[ids]))))
                qual &= k>=47
                if f=="CORE":width.extend(ww)
                comparisons.append(dict(gamma=gamma,scenario=sid,family=f,R=50,covered=k,mean_width=float(np.mean(ww))))
        if not qual:width_value=float("inf")
        else:width_value=float(np.mean(width))
        allcrit[str(gamma)+"_selection"]=dict(qualified=bool(qual),mean_CORE_width=width_value if np.isfinite(width_value) else None)
    eligible=[g for g in (0,.5,1.) if allcrit[str(g)+"_selection"]["qualified"]]
    gamma=min(eligible,key=lambda g:allcrit[str(g)+"_selection"]["mean_CORE_width"]) if eligible else None
    if gamma is None:raise RuntimeError("No adapted candidate passed development checks")
    root="outputs/logs/reliability/joint-chosen-20261028" if wide else "outputs/logs/reliability/joint-long-20261028" if long_memory else "outputs/logs/reliability/joint-adapted-20261028";folder=ROOT/root
    if folder.exists():raise RuntimeError("Preserve adaptation version")
    folder.mkdir(parents=True)
    weights=bounded**gamma
    write_json(folder/"tail_weights.json",dict(target_ids=d.targets,weights=weights.tolist(),raw_tail=raw.tolist(),
        clipping="within each family0.1..10 times median" if wide else "within each family0.5..2 times median positive development tail",gamma=gamma,
        development_source=source,not_a_standard_error_or_probability=True))
    cfg.update(schema_version="joint-target-adaptive-v14-before-new-independent-tests" if wide else "joint-tail-long-v13-before-new-independent-tests" if long_memory else "joint-tail-adapted-v12-before-new-independent-tests",experiment_root=root,
        random_stream_version="joint-final-v14" if wide else "joint-final-v13" if long_memory else "joint-final-v12",tail_weights=root+"/tail_weights.json",
        holdout_truth_seed=20261107 if wide else 20261105 if long_memory else 20261101,holdout_variation_seed=20261108 if wide else 20261106 if long_memory else 20261102,
        holdout_common_tau_max=2920 if long_memory else 1460,
        selection="After v11 validation revealed inefficient width allocation, fit bounded target-tail factors only on first50 DEVELOPMENT replicates and compare gamma0/.5/1 on latter50. Freeze before NEW independent calibration/validation/parameter holdout. Earlier validation is not reused as new acceptance.")
    if long_memory:
        cfg["scope_reasons"]="Extend required scope to the PREVIOUSLY FAILED C13 tau2920d before new calibration/testing; only permanent global shock and globalt scale remain outside. This expands coverage obligations; old failures are retained."
    write_json(ROOT/("config/reliability_joint_v14.json" if wide else "config/reliability_joint_v13.json" if long_memory else "config/reliability_joint_v12.json"),cfg)
    write_csv(folder/"adaptation_development.csv",comparisons)
    write_json(folder/"model_selection.json",dict(selected_model=name,selected_tail_gamma=gamma,
        parent_selection="outputs/logs/reliability/joint-final-20261028/model_selection.json",
        development_comparison=allcrit,new_calibration_seen=False,new_locked_validation_seen=False,
        earlier_v11_validation_seen=True,production_approved=False,script_sha256=sha(Path(__file__))))
    print(json.dumps(dict(gamma=gamma,comparison={g:allcrit[g+"_selection"] for g in ("0","0.5","1.0")})))


if __name__=="__main__":
    parser=__import__("argparse").ArgumentParser(description=__doc__)
    parser.add_argument("--long-memory",action="store_true")
    parser.add_argument("--wide-target-scales",action="store_true")
    args=parser.parse_args();main(args.long_memory,args.wide_target_scales)
