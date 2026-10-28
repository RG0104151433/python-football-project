"""Fixed-design experiments and traceable run evidence for method development."""
from collections import defaultdict
from datetime import datetime,timezone,timedelta,date
import csv
import hashlib
import io
import json
from pathlib import Path
import platform
import time

import numpy as np
import scipy

from .design import build_design,sha
from .models import (FixedDesign,ModelFailure,bootstrap_halfwidth,clipped_intervals,
    exact_mc_limits,fit_association,fit_margin,generate,graph_bounds,keyed_rng,
    select_pairs,truth_margin)


def serial(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,Path):return value.as_posix()
    raise TypeError(type(value).__name__)


def json_text(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False,default=serial)+"\n"


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json_text(value),encoding="utf-8",newline="\n")


def write_csv(path,records):
    records=list(records)
    cols=list(dict.fromkeys(k for r in records for k in r))
    with Path(path).open("w",encoding="utf-8-sig",newline="") as stream:
        w=csv.DictWriter(stream,cols,lineterminator="\n");w.writeheader()
        for r in records:w.writerow({k:format(v,".17g") if isinstance(v,float) else v for k,v in r.items()})


def actual_design(root):
    ctx=build_design(root)
    ts=[t for t in ctx["catalogue"] if t["target_id"] in ctx["vectors"]]
    A=np.stack([ctx["vectors"][t["target_id"]] for t in ts])
    fam={f:[j for j,t in enumerate(ts) if t["family"]==f] for f in sorted({t["family"] for t in ts})}
    design=FixedDesign(ctx["facts"],A,[t["target_id"] for t in ts],fam,
                       [t for t in ctx["catalogue"] if t["target_id"] not in ctx["vectors"]])
    # Labels remain descriptive, not genuine competition editions.
    comp={r["match_id"]:r["tournament_name"] for r in ctx["competition_context"]}
    for r in design.facts:r["tournament_name"]=comp[r["match_id"]]
    old={**ctx["inputs"],**ctx["parent_outputs"]}
    return design,dict(inputs=old,parent_design_id="design-e1ebd48827f8a5ff4be8",catalogue_rows=len(ctx["catalogue"]),
                       unsupported=len(design.unsupported),supported=len(ts),families={f:len(js) for f,js in fam.items()})


def small_design():
    """80 synthetic fixtures: both roles, 10 cells, ties in date, repeated pairs.

    An implementation/development design, not a reduced football analysis.
    """
    facts=[]
    eras=["1980s","1990s","2000s","2010s","2020s"]
    for e,era in enumerate(eras):
        for kind in ("friendly","non_friendly"):
            for k in range(8):
                home=(k+e)%6;away=(home+1+(k//6))%6
                day=date(int(era[:4])+k%min(5,2025-int(era[:4])),1,1)+timedelta(days=(k//2)*17)
                facts.append(dict(match_id=f"toy:{len(facts):03}",date=day.isoformat(),year=str(day.year),era=era,
                    tournament_group=kind,home_team_id=f"toy-team:{home}",away_team_id=f"toy-team:{away}",tournament_name=kind))
    n=len(facts);A=[];names=[]
    def mean(ids):
        x=np.zeros(n);x[ids]=1/len(ids);return x
    for e in (3,4):
        A.append(mean(list(range(e*16,(e+1)*16)))-mean(list(range(16))));names.append(f"toy:era{e}-era0")
    A.append(mean([i for i,r in enumerate(facts) if r["tournament_group"]=="friendly"])-mean([i for i,r in enumerate(facts) if r["tournament_group"]!="friendly"]));names.append("toy:friendly-other")
    A.extend([mean(list(range(8))),mean([0]),np.zeros(n)])
    names.extend(["toy:cell-rate","toy:single-match-rate","toy:zero-cancellation"])
    return FixedDesign(facts,A,names,{"CORE":[0,1,2],"CONDITIONAL":[3,4],"AUX":[5]},[])


def new_run(root,stage,config):
    root=Path(root)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out=root/"outputs/logs/reliability"/("methods-"+stage+"-"+stamp)
    out.mkdir(parents=True,exist_ok=False)
    files=["src/reliability/models.py","src/reliability/experiment.py","scripts/validate_reliability.py",config,
           "config/reliability_validation_v1.json"]
    manifest=dict(schema_version="reliability-method-run-v1",stage=stage,started_utc=datetime.now(timezone.utc).isoformat(),
                  environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform()),
                  code_and_config={f:sha(root/f) for f in files},formal_football_inference=False,
                  actual_model_fit=False,production_estimator=None,code_state="uncommitted content hashes; no commit created",
                  human_review="not_performed",status="running")
    write_json(out/"run_manifest.json",manifest)
    return out,manifest


def finish_run(root,out,manifest,summary):
    manifest.update(summary=summary,status="completed_development_not_acceptance",finished_utc=datetime.now(timezone.utc).isoformat())
    manifest["outputs"]={p.relative_to(root).as_posix():sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!="run_manifest.json"}
    for f,expected in manifest["code_and_config"].items():
        if sha(Path(root)/f)!=expected:raise ModelFailure("Execution source changed during run:"+f)
    write_json(out/"run_manifest.json",manifest)
    print(json_text(dict(run=out.relative_to(root).as_posix(),summary=summary)),flush=True)


def graph_experiment(root,config,actual=False):
    out,manifest=new_run(root,"full-graph" if actual else "small-graph",config)
    design,binding=actual_design(root) if actual else (small_design(),dict(synthetic=True))
    write_json(out/"design_binding.json",binding)
    rows=[];raw={}
    for L in (90,365,730,1460,"all_dependent"):
        for version in ("G0-global","G1-target-coloring"):
            g=graph_bounds(design,L,version.startswith("G1"));raw[f"{L}:{version}"]=g
            for j,tid in enumerate(design.targets):
                # Width is assessed at every possible center via maximum bound
                # span; midpoint is deterministic, does not inspect real Y.
                midpoint=(design.lo+design.hi)/2
                lo,hi=clipped_intervals(design,midpoint,g["half"])
                rows.append(dict(method=version,L_days=L,target_id=tid,C=float(g["C"][j]),
                    baseline_C=float(g["C_baseline"][j]),halfwidth=float(g["half"][j]),
                    logical_span=float(design.span[j]),midpoint_width=float(hi[j]-lo[j]),
                    maximum_possible_width=float(min(2*g["half"][j],design.span[j])),
                    full_range_for_every_possible_outcome=bool(g["half"][j]>=design.span[j]-1e-12),
                    coloring=g["schemes"][j],global_n_colors=g["colors"],cpu_seconds=g["cpu_seconds"]))
            print(f"graph {L} {version}: {g['cpu_seconds']:.3f} CPU seconds",flush=True)
    write_csv(out/"graph_widths.csv",rows);write_json(out/"graph_constants.json",raw)
    summary=dict(n=design.n,targets=len(design.targets),unsupported=len(design.unsupported),rows=len(rows),
                 outcome_input_used=False,graph_independence_factually_certified=False,
                 conditional_theory_only=True)
    finish_run(root,out,manifest,summary)
    return out


def collect_metric(design,estimate,truth,half):
    lo,hi=clipped_intervals(design,estimate,half)
    result={}
    for f,js in design.families.items():
        span=design.span[js];width=hi[js]-lo[js]
        ratios=np.divide(width,span,out=np.zeros(len(js)),where=span>0)
        result[f]=dict(covered=bool(np.all((lo[js]<=truth[js]+1e-12)&(hi[js]>=truth[js]-1e-12))),
                       mean_width=float(np.mean(width)),mean_span_fraction=float(np.mean(ratios)),
                       full_span_fraction=float(np.mean((span>0)&(width>=span-1e-12))))
    return result


def simulation(root,config,actual=False,baseline=False):
    cfg=json.loads((Path(root)/config).read_text(encoding="utf-8-sig"))
    protocol=json.loads((Path(root)/"config/reliability_validation_v1.json").read_text(encoding="utf-8-sig"))
    stage=("full" if actual else "small")+("-baseline" if baseline else "-development")
    out,manifest=new_run(root,stage,config)
    design,binding=actual_design(root) if actual else (small_design(),dict(synthetic=True))
    write_json(out/"design_binding.json",binding)
    pair_start=time.process_time();pairs=select_pairs(design)
    pair_cpu=time.process_time()-pair_start
    write_csv(out/"association_pair_indices.csv",[dict(i=int(i),j=int(j)) for i,j in zip(pairs["i"],pairs["j"])])
    write_json(out/"pair_selection.json",dict(sha256=pairs["sha256"],counts=pairs["counts"],cpu_seconds=pair_cpu,n_pairs=len(pairs["i"]),outcomes_used=False))
    g0=graph_bounds(design,730,False);g1=graph_bounds(design,730,True)
    graph_all=graph_bounds(design,"all_dependent",True)
    limit=cfg["full_pilot_reps_per_scenario"] if actual else cfg["baseline_reps_per_scenario"] if baseline else cfg["small_reps_per_scenario"]
    inner=cfg["inner_B"]
    ridge=0. if baseline else cfg["optimized_margin_cell_ridge"]
    seed=cfg["master_seed"];stage_key=stage+":"+cfg["schema_version"]
    scenarios=protocol["simulations"]["scenarios"]
    totals=defaultdict(list);reps=[];cpu0=time.process_time(); stopped=False
    mp_cpu=[];mp_stopped=False
    statepath=out/"replications.jsonl"
    with statepath.open("w",encoding="utf-8",newline="\n") as stream:
        for rep in range(limit):
            for sc in scenarios:
                if time.process_time()-cpu0>cfg["pilot_total_CPU_seconds_cap"]:
                    stopped=True;break
                rng=keyed_rng(seed,stage_key,sc["id"],rep,"outer")
                before=rng.bit_generator.state
                p=truth_margin(design,sc,seed);truth=design.apply(p)
                y=generate(design,p,sc,1,rng)[0];est=design.apply(y)
                record=dict(scenario=sc["id"],replication=rep,stage=stage,outer_state_before=before,
                            outer_state_after=rng.bit_generator.state,bias_vector=(est-truth).tolist(),methods={})
                for name,g in (("G0-global",g0),("G1-target-coloring",g1),("G-all-dependent",graph_all)):
                    met=collect_metric(design,est,truth,g["half"])
                    record["methods"][name]=dict(ok=True,metrics=met,graph_L=730 if name!="G-all-dependent" else "all_dependent")
                    for f,v in met.items():totals[(sc["id"],name,f)].append(dict(ok=True,**v))
                start=time.process_time();mp=dict(ok=False,status="not_attempted_budget")
                if not mp_stopped:
                    try:
                        margin=fit_margin(design,y,ridge);mp["margin"]=margin["diagnostic"]
                        if not margin["ok"]:
                            mp["status"]=margin["status"]
                        else:
                            fit=fit_association(design,pairs,margin["p"],y,starts=cfg["association_starts"])
                            mp["association"]=fit.get("diagnostic",{})
                            if not fit["ok"]:
                                mp["status"]=fit["status"]
                            else:
                                inner_rng=keyed_rng(seed,stage_key,sc["id"],rep,"inner")
                                mp["inner_state_before"]=inner_rng.bit_generator.state
                                half,cal=bootstrap_halfwidth(design,margin["p"],fit["par"],inner,inner_rng)
                                mp.update(ok=True,status="development_interval_only",parameters=fit["par"].tolist(),
                                    bootstrap=cal,inner_state_after=inner_rng.bit_generator.state,
                                    metrics=collect_metric(design,est,truth,half))
                    except (ModelFailure,ValueError,FloatingPointError) as exc:
                        mp["status"]=type(exc).__name__+":"+str(exc)
                    mp["cpu_seconds"]=time.process_time()-start;mp_cpu.append(mp["cpu_seconds"])
                    if sum(mp_cpu)>cfg["MP_CPU_seconds_cap"]:mp_stopped=True
                    if actual and len(mp_cpu)>=cfg["full_cost_gate_min_fits"]:
                        projected=float(np.mean(mp_cpu))*cfg["formal_MP_outer_replications"]
                        if projected>protocol["engineering_gate"]["estimated_formal_CPU_hours_per_route_cap"]*3600:
                            mp_stopped=True
                            record["cost_gate"]=dict(projected_lower_bound_CPU_hours=projected/3600,
                                formal_B_cost_not_included=True,decision="formal_MP_computationally_not_admitted_v1")
                name="P0-unpenalized-cells" if baseline else "P1-cell-ridge"
                record["methods"][name]=mp
                for f in design.families:
                    val=mp.get("metrics",{}).get(f,{})
                    totals[(sc["id"],name,f)].append(dict(ok=mp["ok"],covered=bool(mp["ok"] and val.get("covered")),**{k:v for k,v in val.items() if k!="covered"}))
                stream.write(json.dumps(record,ensure_ascii=False,sort_keys=True,allow_nan=False,default=serial)+"\n");stream.flush()
                reps.append(dict(scenario=sc["id"],replication=rep,mp_ok=mp["ok"],mp_status=mp["status"],mp_cpu=mp.get("cpu_seconds",0)))
                print(f"{stage} {sc['id']} r{rep}: {mp['status']}, {mp.get('cpu_seconds',0):.3f}s",flush=True)
            if stopped:break
    aggregate=[]
    for (sid,method,f),vals in sorted(totals.items()):
        R=len(vals);success=sum(v["ok"] for v in vals);cover=sum(v["covered"] for v in vals)
        row=dict(scenario=sid,method=method,family=f,R=R,successes=success,failures=R-success,covered=cover,
                 **{"coverage_"+k:v for k,v in exact_mc_limits(cover,R).items()},
                 **{"failure_"+k:v for k,v in exact_mc_limits(R-success,R).items()},
                 success_conditional_coverage=cover/success if success else None,
                 stage="development_not_formal_acceptance")
        for field in ("mean_width","mean_span_fraction","full_span_fraction"):
            vv=[v[field] for v in vals if field in v];row[field]=float(np.mean(vv)) if vv else None
        aggregate.append(row)
    write_csv(out/"metrics.csv",aggregate);write_csv(out/"replication_status.csv",reps)
    summary=dict(n=design.n,targets=len(design.targets),unsupported=len(design.unsupported),attempted_outer=len(reps),
                 nominal_outer_per_scenario=limit,scenarios=len(scenarios),inner_B=inner,margin_cell_ridge=ridge,
                 stopped_total_budget=stopped,MP_stopped_budget_or_projection=mp_stopped,
                 cpu_seconds=time.process_time()-cpu0,MP_CPU_seconds=sum(mp_cpu),MP_attempted=len(mp_cpu),
                 MP_mean_CPU_seconds=float(np.mean(mp_cpu)) if mp_cpu else None,
                 empirical_acceptance=False,formal_replication_counts_completed=False,real_outcomes_fitted=False,
                 pair_selection_CPU_seconds=pair_cpu)
    finish_run(root,out,manifest,summary)
    return out
