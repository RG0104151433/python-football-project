"""Iteration runner: all refinements remain separately identifiable."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from src.reliability.design import sha
from src.reliability.experiment import actual_design,write_json,write_csv,collect_metric
from src.reliability.models import (keyed_rng,truth_margin,generate,fit_margin,
    fit_association,scenario_from_fit,exact_mc_limits)
from src.reliability.refinements import refine_graph,refined_intervals,generate_fast,bootstrap_fast


def load(path):return json.loads((ROOT/path).read_text(encoding="utf-8-sig"))


def start(stage,config):
    out=ROOT/"outputs/logs/reliability"/("refined-"+stage+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    out.mkdir(parents=True,exist_ok=False)
    paths=[config,"config/reliability_iteration_v4.json","config/reliability_validation_v1.json",
           "src/reliability/models.py","src/reliability/refinements.py","src/reliability/experiment.py","scripts/refine_reliability.py"]
    bindings={p:sha(ROOT/p) for p in paths}
    archive={}
    for p,h in bindings.items():
        dest=out/"source_snapshot"/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/p).read_bytes())
        archive[p]=dest.relative_to(ROOT).as_posix()
    manifest=dict(status="running",stage=stage,code_and_config=bindings,source_snapshot=archive,
        environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=sys.platform),
        actual_football_outcomes_used=False,formal_football_intervals_published=False,production_estimator=None,
        execution="Codex AI, uncommitted source hashes, no human review/commit/push")
    write_json(out/"run_manifest.json",manifest)
    return out,manifest


def end(out,manifest,summary):
    for p,h in manifest["code_and_config"].items():
        if sha(ROOT/p)!=h:raise RuntimeError("Source changed mid-run:"+p)
    manifest.update(status="completed_experiment_not_production_inference",summary=summary,finished_utc=datetime.now(timezone.utc).isoformat())
    manifest["outputs"]={p.relative_to(ROOT).as_posix():sha(p) for p in out.rglob("*") if p.is_file() and p.name!="run_manifest.json"}
    write_json(out/"run_manifest.json",manifest)
    print(json.dumps(dict(run=out.relative_to(ROOT).as_posix(),summary=summary),ensure_ascii=False),flush=True)


def graph_run(config):
    cfg=load(config);out,man=start("graph",config);d,binding=actual_design(ROOT)
    write_json(out/"design_binding.json",binding)
    base=load(cfg["G1_constants"]);allg={};rows=[];cpu0=time.process_time()
    for L in (90,365,730,1460,"all_dependent"):
        g=refine_graph(d,L,base[f"{L}:G1-target-coloring"]);allg[str(L)]=g
        for j,tid in enumerate(d.targets):
            rows.append(dict(target_id=tid,L_days=L,G1_C=base[f"{L}:G1-target-coloring"]["C"][j],
                G2_C=float(g["C"][j]),halfwidth=float(g["half"][j]),scheme=g["schemes"][j],
                G3_markov_selected=bool(g["markov_choice"][j]),logical_span=float(d.span[j]),
                G2_maximum_width=float(min(2*g["half"][j],d.span[j])),
                G3_maximum_width=float(g["markov_width"][j] if g["markov_choice"][j] else min(2*g["half"][j],d.span[j]))))
        print("refined graph",L,"CPU",time.process_time()-cpu0,flush=True)
    write_json(out/"graph_constants.json",allg);write_csv(out/"graph_refinement.csv",rows)
    end(out,man,dict(n=d.n,targets=len(d.targets),unsupported=len(d.unsupported),cpu_seconds=time.process_time()-cpu0,
                    no_outcome_selection=True,Markov_guarantee_requires_only_boundedness=True,
                    graph_guarantee_requires_declared_set_independence=True))
    return out


def stat_metrics(d,est,truth,lo,hi):
    result={}
    for f,js in d.families.items():
        spans=d.span[js];width=hi[js]-lo[js]
        ratio=np.divide(width,spans,out=np.zeros(len(js)),where=spans>0)
        result[f]=dict(covered=bool(np.all((lo[js]<=truth[js]+1e-12)&(hi[js]>=truth[js]-1e-12))),
                       mean_span_fraction=float(ratio.mean()),near_full_fraction=float(np.mean((spans>0)&(ratio>=.95))))
    return result


def summarize(values):
    rows=[]
    for (sc,method,f),vs in sorted(values.items()):
        R=len(vs);k=sum(v["covered"] for v in vs);failed=sum(not v.get("ok",True) for v in vs)
        row=dict(scenario=sc,method=method,family=f,R=R,covered=k,failures=failed,
                 **{"coverage_"+a:b for a,b in exact_mc_limits(k,R).items()},
                 **{"failure_"+a:b for a,b in exact_mc_limits(failed,R).items()})
        for key in ("mean_span_fraction","near_full_fraction"):
            vals=[v[key] for v in vs if key in v];row[key]=float(np.mean(vals)) if vals else None
        row["coverage_numeric_gate"]=row["coverage_lower99"]>=.94 and row["failure_upper99"]<=.01
        rows.append(row)
    return rows


def full_pilot(config):
    cfg=load(config);out,man=start("full-pilot",config);d,binding=actual_design(ROOT)
    write_json(out/"design_binding.json",binding)
    source=ROOT/cfg["previous_full_pilot"]
    pairrows=list(__import__("csv").DictReader((source/"association_pair_indices.csv").open(encoding="utf-8-sig")))
    from src.reliability.models import pair_metadata
    pairs=pair_metadata(d,np.array([int(r["i"]) for r in pairrows]),np.array([int(r["j"]) for r in pairrows]))
    man["parent_pair_sha256"]=sha(source/"association_pair_indices.csv")
    scenarios=load("config/reliability_validation_v1.json")["simulations"]["scenarios"]
    c=load("outputs/logs/reliability/iteration-20261028/calibration_training.json")["selected_multiplier"]
    if c is None:raise RuntimeError("No selected training calibration")
    man["locked_small_training_multiplier"]=c
    totals=defaultdict(list);costs=[];records=[];cpu0=time.process_time();stopped=False
    with (out/"replications.jsonl").open("w",encoding="utf-8",newline="\n") as stream:
        for rep in range(cfg["full_refined_R"]):
            for sc in scenarios:
                if time.process_time()-cpu0>1200:stopped=True;break
                rng=keyed_rng(20261028,"refined-full-pilot-v5",sc["id"],rep,"outer")
                before=rng.bit_generator.state;p=truth_margin(d,sc);truth=d.apply(p)
                y=generate_fast(d,p,sc,1,rng)[0];est=d.apply(y)
                r=dict(scenario=sc["id"],replication=rep,outer_state_before=before,outer_state_after=rng.bit_generator.state,
                       estimate=est.tolist(),truth=truth.tolist(),outcome_sha256=__import__("hashlib").sha256(y.astype("u1").tobytes()).hexdigest(),methods={})
                startcpu=time.process_time();ok=False
                try:
                    margin=fit_margin(d,y,.5);r["margin"]=margin["diagnostic"]
                    if not margin["ok"]:raise RuntimeError("margin:"+margin["status"])
                    fit=fit_association(d,pairs,margin["p"],y,starts=9)
                    if not fit["ok"]:raise RuntimeError("association:"+fit["status"])
                    r["association"]=fit["diagnostic"];r["parameters"]=fit["par"].tolist()
                    r["fitted_margin_sha256"]=__import__("hashlib").sha256(margin["p"].astype("<f8").tobytes()).hexdigest()
                    fit_cpu=time.process_time()-startcpu
                    inner=keyed_rng(20261028,"refined-full-pilot-v5",sc["id"],rep,"inner")
                    r["inner_state_before"]=inner.bit_generator.state
                    bt=time.process_time();half,cal=bootstrap_fast(d,margin["p"],scenario_from_fit(fit["par"]),199,inner)
                    inner_cpu=time.process_time()-bt;r["bootstrap"]=cal;r["inner_state_after"]=inner.bit_generator.state
                    r["halfwidth"]=half.tolist();r["fit_cpu"]=fit_cpu;r["inner_B199_cpu"]=inner_cpu
                    if rep==0:
                        bt=time.process_time();_,cal999=bootstrap_fast(d,margin["p"],scenario_from_fit(fit["par"]),999,
                            keyed_rng(20261028,"refined-full-pilot-v5",sc["id"],rep,"cost-B999"))
                        r["inner_B999_cpu"]=time.process_time()-bt;costs.append(fit_cpu+r["inner_B999_cpu"])
                    for name,mult in (("P2-fast-same-law",1),("P3-trained-inflation",c)):
                        lo=np.maximum(est-mult*half,d.lo);hi=np.minimum(est+mult*half,d.hi)
                        met=stat_metrics(d,est,truth,lo,hi);r["methods"][name]=met
                        for f,v in met.items():totals[(sc["id"],name,f)].append(dict(ok=True,**v))
                    ok=True
                except (ValueError,RuntimeError,FloatingPointError) as exc:
                    r["failure"]=type(exc).__name__+":"+str(exc)
                    for name in ("P2-fast-same-law","P3-trained-inflation"):
                        for f in d.families:totals[(sc["id"],name,f)].append(dict(ok=False,covered=False))
                r["ok"]=ok;r["cpu_seconds"]=time.process_time()-startcpu
                stream.write(json.dumps(r,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n");stream.flush();records.append(r)
                print(f"refined full {sc['id']} r{rep}:ok={ok},CPU={r['cpu_seconds']:.3f}",flush=True)
            if stopped:break
    write_csv(out/"metrics.csv",summarize(totals))
    projected=np.mean(costs)*58000/3600 if costs else None
    summary=dict(n=d.n,targets=len(d.targets),unsupported=len(d.unsupported),attempted=len(records),
        requested_per_scenario=cfg["full_refined_R"],stopped_budget=stopped,cpu_seconds=time.process_time()-cpu0,
        B999_benchmark_fits=len(costs),mean_fit_plus_B999_CPU_seconds=float(np.mean(costs)) if costs else None,
        projected_formal_58000_CPU_hours=float(projected) if projected is not None else None,
        computational_admission=bool(projected is not None and projected<=24),
        multiplier=c,formal_validation=False,real_football_intervals=False)
    end(out,man,summary)
    return out


def graph_oracle(config):
    cfg=load(config);out,man=start("full-graph-oracle",config);d,binding=actual_design(ROOT)
    write_json(out/"design_binding.json",binding)
    gs=load(cfg["refined_graph_constants"])
    for g in gs.values():
        for k in ("C","half","delta","markov_choice","markov_width"):g[k]=np.array(g[k])
    scenarios=load("config/reliability_validation_v1.json")["simulations"]["scenarios"]
    totals=defaultdict(list);references=[];diagnostics=[];cpu0=time.process_time()
    for sc in scenarios:
        p=truth_margin(d,sc);truth=d.apply(p)
        ref_rng=keyed_rng(20261028,"graph-oracle-v5",sc["id"],"reference")
        ref_state=ref_rng.bit_generator.state
        oracle_half,oracle_cal=bootstrap_fast(d,p,sc,9999,ref_rng)
        references.append(dict(scenario=sc["id"],generator_known_parameter_oracle_only=True,
            reference_before=ref_state,reference_after=ref_rng.bit_generator.state,calibration=oracle_cal,
            not_fitted_MP_validation=True))
        sumv=np.zeros(len(truth));sumsq=np.zeros(len(truth));R=cfg["graph_formal_R"]
        states=[]
        for offset in range(0,R,128):
            B=min(128,R-offset)
            # Batch-keyed disjoint streams; saved before/after for exact replay.
            rng=keyed_rng(20261028,"graph-oracle-v5",sc["id"],"validation",offset)
            before=rng.bit_generator.state;ys=generate_fast(d,p,sc,B,rng);values=d.apply(ys)
            states.append(dict(offset=offset,B=B,before=before,after=rng.bit_generator.state))
            sumv+=values.sum(axis=0);sumsq+=(values**2).sum(axis=0)
            for est in values:
                for L,g in gs.items():
                    for method,fallback in (("G2-weighted",False),("G3-Markov-choice",True)):
                        lo,hi=refined_intervals(d,est,g,fallback)
                        met=stat_metrics(d,est,truth,lo,hi)
                        for f,v in met.items():totals[(sc["id"],method+":L="+L,f)].append(v)
                lo=np.maximum(est-oracle_half,d.lo);hi=np.minimum(est+oracle_half,d.hi)
                for f,v in stat_metrics(d,est,truth,lo,hi).items():totals[(sc["id"],"generator-oracle-not-fitted-MP",f)].append(v)
        write_json(out/(sc["id"]+"_random_states.json"),states)
        for j,tid in enumerate(d.targets):
            mean=sumv[j]/R;var=(sumsq[j]-sumv[j]**2/R)/(R-1)
            diagnostics.append(dict(scenario=sc["id"],target_id=tid,R=R,truth=float(truth[j]),
                bias=float(mean-truth[j]),empirical_variance=float(max(0,var)),bias_MC_SE=float(np.sqrt(max(0,var)/R))))
        print(f"full graph/oracle {sc['id']}:R={R},CPUtotal={time.process_time()-cpu0:.2f}",flush=True)
        write_csv(out/"metrics.csv",summarize(totals));write_json(out/"oracle_reference.json",references)
        write_csv(out/"target_diagnostics.csv",diagnostics)
        write_json(out/"progress.json",dict(completed_scenarios=len(references),total_scenarios=18,cpu_seconds=time.process_time()-cpu0))
    summary=dict(n=d.n,targets=len(d.targets),unsupported=len(d.unsupported),scenarios=18,R_per_scenario=cfg["graph_formal_R"],
        known_generator_reference_B=9999,cpu_seconds=time.process_time()-cpu0,
        M_G_fixed_count_checks_completed=True,fitted_MP_formal_validation=False,
        oracle_does_not_replace_fitted_validation=True,actual_football_assumptions_certified=False)
    end(out,man,summary)
    return out


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["graph","full-pilot","graph-oracle"],required=True)
    parser.add_argument("--config",default="config/reliability_refinement_v5.json")
    args=parser.parse_args()
    {"graph":graph_run,"full-pilot":full_pilot,"graph-oracle":graph_oracle}[args.stage](args.config)
