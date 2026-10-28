"""Versioned restricted joint-score experiments; never silently approve a model."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import sys
import time
import copy
import gzip

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from src.reliability.design import sha
from src.reliability.experiment import actual_design,write_json,write_csv
from src.reliability.models import keyed_rng,truth_margin,pair_metadata,exact_mc_limits
from src.reliability.refinements import generate_fast
from src.reliability.joint import RestrictedMoments,family_scores,finite_calibration_critical,calibrated_halfwidth
from src.reliability.guard import protect_scale

BASE=ROOT/"outputs/logs/reliability/joint-20261028"
CFG="config/reliability_joint_v8.json"
WORK={}


def read(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def begin(stage):
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out=BASE/(stage+"-"+stamp);out.mkdir(parents=True,exist_ok=False)
    paths=[CFG,"src/reliability/joint.py","src/reliability/guard.py","src/reliability/models.py","src/reliability/refinements.py",
           "src/reliability/experiment.py","scripts/develop_reliability_joint.py"]
    man=dict(stage=stage,status="running",source={p:sha(ROOT/p) for p in paths},real_football_intervals=False,
             production_method=None,human_review="not_performed",executor="Codex AI; uncommitted source hashes; no commit/push")
    run_cfg=read(ROOT/CFG)
    man["input_artifacts"]={}
    for field in ("cache_pointer","guard_cache"):
        if run_cfg.get(field):man["input_artifacts"][run_cfg[field]]=sha(ROOT/run_cfg[field])
    for p in paths:
        dest=out/"source_snapshot"/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/p).read_bytes())
    write_json(out/"manifest.json",man)
    return out,man


def finish(out,man,summary):
    for p,h in man["source"].items():
        if sha(ROOT/p)!=h:raise RuntimeError("Source changed during experiment:"+p)
    for p,h in man["input_artifacts"].items():
        if sha(ROOT/p)!=h:raise RuntimeError("Cache pointer/guard changed during experiment:"+p)
    man.update(status="completed_experiment_not_automatic_model_approval",summary=summary)
    man["outputs"]={p.relative_to(ROOT).as_posix():sha(p) for p in out.rglob("*") if p.is_file() and p.name!="manifest.json"}
    write_json(out/"manifest.json",man)
    print(json.dumps(dict(run=out.relative_to(ROOT).as_posix(),summary=summary)),flush=True)


def prepare():
    out,man=begin("prepare");cpu=time.process_time();d,binding=actual_design(ROOT)
    import csv
    source=ROOT/"outputs/logs/reliability/methods-full-development-20261028T005622778442Z/association_pair_indices.csv"
    raw=list(csv.DictReader(source.open(encoding="utf-8-sig")))
    pairs=pair_metadata(d,np.array([int(r["i"]) for r in raw]),np.array([int(r["j"]) for r in raw]))
    model=RestrictedMoments(d,pairs,progress=lambda label:print("prepared",label,"CPU",time.process_time()-cpu,flush=True))
    model.save(out/"cache.npz");write_json(out/"design_binding.json",binding)
    summary=dict(n=d.n,targets=len(d.targets),unsupported=len(d.unsupported),mean_rank=model.rank,
        kernel_labels=model.labels,singular_values=model.singular_values.tolist(),cache_sha256=sha(out/"cache.npz"),
        pair_source_sha256=sha(source),cpu_seconds=time.process_time()-cpu)
    finish(out,man,summary)
    write_json(BASE/"active_cache.json",dict(directory=out.relative_to(ROOT).as_posix(),cache_sha256=summary["cache_sha256"],
               joint_source_sha256=sha(ROOT/"src/reliability/joint.py"),manifest_sha256=sha(out/"manifest.json")))


def initialize(config_path=CFG):
    global WORK
    cfg=read(ROOT/config_path);pointer=read(ROOT/cfg["cache_pointer"]) if cfg.get("cache_pointer") else read(BASE/"active_cache.json");cache=ROOT/pointer["directory"]/"cache.npz"
    if sha(cache)!=pointer["cache_sha256"]:raise RuntimeError("Cache bytes changed")
    if sha(ROOT/"src/reliability/joint.py")!=pointer["joint_source_sha256"]:raise RuntimeError("Rebuild cache after source change")
    d,binding=actual_design(ROOT);model=RestrictedMoments.load(d,cache)
    protocol=read(ROOT/"config/reliability_validation_v1.json")
    WORK=dict(d=d,model=model,cfg=cfg,scenarios={s["id"]:s for s in protocol["simulations"]["scenarios"]},binding=binding)
    if cfg.get("guard_cache"):
        guard_meta=read((ROOT/cfg["guard_cache"]).parent/"guard_manifest.json")
        if sha(ROOT/cfg["guard_cache"])!=guard_meta["guard_sha256"]:raise RuntimeError("Guard bytes changed")
        with np.load(ROOT/cfg["guard_cache"],allow_pickle=False) as src:WORK["guard"]=src["guard"]


def perturbed(scenario):
    sc=copy.deepcopy(scenario);rng=keyed_rng(20261028,"joint-parameter-holdout",sc["id"])
    vals=sc["latent"]
    for k in vals:
        if k!="e" and vals[k]>0:vals[k]*=rng.uniform(.8,1.2)
    mass=sum(v for k,v in vals.items() if k!="e")
    if mass>.9:
        for k in vals:
            if k!="e":vals[k]*=.9/mass
    vals["e"]=1-sum(v for k,v in vals.items() if k!="e")
    if "team_tau_days" in sc:sc["team_tau_days"]=float(np.clip(sc["team_tau_days"]*rng.uniform(.8,1.2),7,3650))
    if sc.get("time_kernel")=="OU":sc["time_tau_days"]=float(np.clip(sc["time_tau_days"]*rng.uniform(.8,1.2),1,1460))
    return sc


def batch_job(job):
    stage,sid,start,B,models,crit=job
    d=WORK["d"];model=WORK["model"];cfg=WORK["cfg"]
    sc=WORK["scenarios"][sid]
    if stage=="holdout":sc=perturbed(sc)
    p=truth_margin(d,sc,seed=20261031 if stage=="holdout" else cfg["master_seed"])
    truth=d.apply(p);rng=keyed_rng(cfg["master_seed"],cfg.get("random_stream_version","joint-v8"),stage,sid,start)
    before=rng.bit_generator.state;cpu=time.process_time();Y=generate_fast(d,p,sc,B,rng);est=d.apply(Y)
    records=[]
    for offset,y in enumerate(Y):
        r=dict(scenario=sid,replication=start+offset,models={})
        if stage in ("probe","development"):r["estimate_error"]=(est[offset]-truth).tolist()
        for name in models:
            try:
                label=name.split("@")[0]
                fit=model.fit(y,corrected=label!="J0_naive",coarse=label=="J1_restricted_coarse")
                if "@" in name:fit=protect_scale(fit,WORK["guard"],float(name.split("@")[1]))
                scores={f:0. for f in d.families} if fit["all_constant"] else family_scores(d,est[offset],truth,fit["scale"])
                detail=dict(ok=True,scores=scores,mean_outside=fit["mean_fit_outside_unit_interval"],all_constant=fit["all_constant"])
                if stage in ("probe","development"):
                    detail.update(theta=fit["theta"].tolist(),scale=fit["scale"].tolist())
                if crit is not None:
                    half=calibrated_halfwidth(d,fit,crit)
                    lo=np.maximum(est[offset]-half,d.lo);hi=np.minimum(est[offset]+half,d.hi)
                    detail["family"]={}
                    for f,js in d.families.items():
                        width=hi[js]-lo[js];span=d.span[js]
                        ratio=np.divide(width,span,out=np.zeros(len(js)),where=span>0)
                        detail["family"][f]=dict(covered=bool(np.all((lo[js]<=truth[js]+1e-12)&(hi[js]>=truth[js]-1e-12))),
                            mean_width=float(width.mean()),span_fraction=float(ratio.mean()),near_full_fraction=float(np.mean(ratio>=.95)))
                r["models"][name]=detail
            except (ValueError,RuntimeError,FloatingPointError) as exc:
                r["models"][name]=dict(ok=False,error=type(exc).__name__+":"+str(exc))
        records.append(r)
    errors=est-truth
    return dict(stage=stage,scenario=sid,start=start,B=B,before=before,after=rng.bit_generator.state,
                cpu_seconds=time.process_time()-cpu,records=records,
                target_moments=dict(sum=errors.sum(axis=0),sumsq=(errors**2).sum(axis=0)))


def metrics(records,model_name):
    agg={}
    for r in records:
        m=r["models"][model_name]
        for f in ("CORE","AUX","ROLLING","CONDITIONAL"):
            key=(r["scenario"],f);agg.setdefault(key,[]).append((m["ok"],m.get("family",{}).get(f,{})))
    result=[]
    for (sid,f),vals in sorted(agg.items()):
        R=len(vals);k=sum(ok and v.get("covered",False) for ok,v in vals);fail=sum(not ok for ok,v in vals)
        row=dict(scenario=sid,family=f,R=R,covered=k,failures=fail,
            **{"coverage_"+a:b for a,b in exact_mc_limits(k,R).items()},
            **{"failure_"+a:b for a,b in exact_mc_limits(fail,R).items()})
        for field in ("mean_width","span_fraction","near_full_fraction"):
            vv=[v[field] for ok,v in vals if field in v];row[field]=float(np.mean(vv)) if vv else None
        row["passed"]=row["coverage_lower99"]>=.94 and row["failure_upper99"]<=.01
        result.append(row)
    return result


def run_stage(stage,workers=4):
    cfg=read(ROOT/CFG);out,man=begin(stage)
    protocol=read(ROOT/"config/reliability_validation_v1.json");scenarios=[s["id"] for s in protocol["simulations"]["scenarios"]]
    crit=None
    if stage=="probe":counts={"C09":20};names=cfg["models"]
    elif stage=="development":counts={s:cfg["development_R_each"] for s in scenarios};names=cfg["models"]
    else:
        decision=read(BASE/"model_selection.json");names=[decision["selected_model"]]
        if stage=="calibration":counts={s:cfg["calibration_B_each_required_scenario"] for s in cfg["required_scenarios"]}
        else:
            calibration=read(BASE/"calibration.json");crit=calibration["critical"]
            if stage=="validation":counts={s:cfg["formal_R_each_required_scenario"] if s in cfg["required_scenarios"] else cfg["formal_R_each_stress"] for s in scenarios}
            else:counts={s:cfg["fresh_parameter_holdout_R_each_required"] for s in cfg["required_scenarios"]}
    jobs=[(stage,s,start,min(32,R-start),names,crit) for s,R in counts.items() for start in range(0,R,32)]
    allrecords=[];states=[];totalcpu=0;started=time.monotonic();target_moments={}
    compact=cfg.get("compact_all_logs",False) or stage not in ("probe","development")
    logpath=out/("replications.jsonl.gz" if compact else "replications.jsonl")
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize,initargs=(CFG,)) as pool:
        opener=gzip.open if compact else open
        with opener(logpath,"wt",encoding="utf-8",newline="\n") as stream:
            for k,result in enumerate(pool.map(batch_job,jobs)):
                batch=result.pop("records");tm=result.pop("target_moments");sid=result["scenario"]
                if sid not in target_moments:target_moments[sid]=dict(sum=np.zeros(len(tm["sum"])),sumsq=np.zeros(len(tm["sum"])))
                for field in tm:target_moments[sid][field]+=tm[field]
                totalcpu+=result["cpu_seconds"];states.append(result);allrecords.extend(batch)
                for r in batch:stream.write(json.dumps(r,sort_keys=True,allow_nan=False)+"\n")
                stream.flush()
                if k%20==0:print(stage,"completed",k+1,"/",len(jobs),"CPU",totalcpu,flush=True)
    write_json(out/"random_states.json",states)
    write_json(out/"target_error_moments.json",target_moments)
    if crit is not None:write_csv(out/"metrics.csv",metrics(allrecords,names[0]))
    if stage=="calibration":
        critical={};perworld={}
        for f in ("CORE","AUX","ROLLING","CONDITIONAL"):
            perworld[f]={}
            for s in counts:
                vals=[r["models"][names[0]]["scores"][f] for r in allrecords if r["scenario"]==s and r["models"][names[0]]["ok"]]
                if len(vals)!=counts[s]:raise RuntimeError("Calibration fit failure; cannot drop scores")
                perworld[f][s]=finite_calibration_critical(vals,cfg["calibration_alpha"])
            critical[f]=max(perworld[f].values())
        target=BASE/"calibration.json"
        if target.exists():raise RuntimeError("Preserve prior calibration; new version required")
        write_json(target,dict(source=out.relative_to(ROOT).as_posix(),selected_model=names[0],critical=critical,perworld=perworld,
            alpha=.025,finite_world_only=True,unknown_real_law_not_certified=True,formal_validation_completed=False))
    summary=dict(stage=stage,model_names=names,counts=counts,outer_records=len(allrecords),cpu_seconds_workers=totalcpu,
                 wall_seconds=time.monotonic()-started,real_football_intervals=False)
    finish(out,man,summary)
    write_json(BASE/(stage+"_latest.json"),dict(directory=out.relative_to(ROOT).as_posix(),manifest_sha256=sha(out/"manifest.json")))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["prepare","probe","development","calibration","validation","holdout"],required=True)
    parser.add_argument("--workers",type=int,default=4)
    parser.add_argument("--config",default=CFG)
    args=parser.parse_args()
    CFG=args.config
    parsed=read(ROOT/CFG)
    if parsed.get("experiment_root"):BASE=ROOT/parsed["experiment_root"]
    if args.stage=="prepare":prepare()
    else:run_stage(args.stage,args.workers)
