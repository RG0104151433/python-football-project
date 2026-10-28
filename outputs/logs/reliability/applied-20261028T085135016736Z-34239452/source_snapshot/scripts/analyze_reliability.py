"""Fourth-step application. Use module mode from repository root."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
from pathlib import Path
import sys
import argparse
import json
import time
import traceback
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.reliability.application import load_verified, infer_original, read
from src.reliability.sensitivity import run_sensitivity, identity
from src.reliability.interpretation import review_conclusions, sensitivity_summary
from src.reliability.reporting import environment, save_sensitivity, plot_results, publish, data_dictionary
from src.reliability.experiment import write_csv, write_json
from src.reliability.design import sha, require, rows


def source_paths():
    files=list((ROOT/"src/reliability").glob("*.py"))
    files.extend(ROOT/p for p in ("src/regions/io.py","scripts/analyze_reliability.py","scripts/audit_reliability_analysis.py"))
    return sorted({p.relative_to(ROOT).as_posix() for p in files if p.exists()})


def typed_table(path):
    numeric={"point_display","lower_display","upper_display","point_probability_scale","lower_probability_scale",
        "upper_probability_scale","baseline_probability","estimate_probability","estimate_pp","change_from_baseline_pp"}
    out=[]
    for r in rows(path):
        for k,v in r.items():
            if k in numeric:r[k]=float(v) if v!="" else None
            elif k in ("applicable","affects_target","affects_reference"):r[k]=v=="True"
        out.append(r)
    return out


def run(args):
    bundle=load_verified(ROOT,args.config);sources={p:sha(ROOT/p) for p in source_paths()};env=environment()
    aid=identity("applied-",dict(inputs=bundle["inputs"],sources=sources,environment=env))
    if args.run:
        log=(ROOT/args.run).resolve()
        require(log.is_relative_to(ROOT/"outputs/logs/reliability") and log.name.startswith("applied-"),"Invalid resume directory")
        man=read(log/"run_manifest.json")
        require(man["analysis_id"]==aid and man["source"]==sources and man["inputs"]==bundle["inputs"],"Resume identity changed")
        if man["status"]=="completed_model_conditional_application":
            for p,h in man["outputs"].items():require(sha(ROOT/p)==h,"Completed output changed:"+p)
            print(json.dumps(dict(run=log.relative_to(ROOT).as_posix(),analysis_id=aid,status="existing_completed_run_verified")))
            return
    else:
        stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        log=ROOT/"outputs/logs/reliability"/("applied-"+stamp+"-"+aid[-8:]);log.mkdir(parents=True,exist_ok=False)
        work=ROOT/"outputs/test_tmp/reliability"/log.name;work.mkdir(parents=True,exist_ok=False)
        man=dict(analysis_id=aid,status="running",started_utc=datetime.now(timezone.utc).isoformat(),
            inputs=bundle["inputs"],source=sources,environment=env,phases={},work_dir=work.relative_to(ROOT).as_posix(),
            executor="Codex AI; content SHA identifies uncommitted execution",human_review="not_performed")
        for p in sources:
            dest=log/"source_snapshot"/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/p).read_bytes())
    work=ROOT/man["work_dir"];tables=work/"tables";tables.mkdir(parents=True,exist_ok=True)
    def persist():write_json(log/"run_manifest.json",man)
    persist();started=time.monotonic()
    try:
        if args.stage=="check":
            man.update(status="checked_only_no_inference",checked_matches=bundle["design"].n,checked_targets=len(bundle["design"].targets));persist()
        else:
            if args.stage in ("infer","all") and "infer" not in man["phases"]:
                a,b,fit=infer_original(bundle)
                write_csv(tables/"interval_results.csv",a);write_csv(tables/"bounded_reference.csv",b)
                write_json(tables/"model_fit.json",fit)
                man["phases"]["infer"]=dict(rows=len(a),supported=sum(r["status"]=="model_conditional" for r in a));persist()
            if args.stage in ("sensitivity","all") and "sensitivity" not in man["phases"]:
                print("Computing prespecified descriptive sensitivities",flush=True)
                s=run_sensitivity(bundle);require(len(s["scenarios"])==324,"Sensitivity scenario catalogue incomplete")
                save_sensitivity(tables,s)
                man["phases"]["sensitivity"]=dict(scenarios=len(s["scenarios"]),rows=len(s["results"]),
                    common_teams=len(s["common_teams"]),baseline_reconstructed=s["baseline_reconstructed"]);persist()
            if args.stage in ("report","all"):
                require("infer" in man["phases"] and "sensitivity" in man["phases"],"Report needs both phases; resume the same run with missing stage")
                a=typed_table(tables/"interval_results.csv");s=typed_table(tables/"sensitivity_results.csv")
                review=review_conclusions(a,s);summary=sensitivity_summary(s,a)
                write_csv(tables/"conclusion_review.csv",review);write_csv(tables/"sensitivity_summary.csv",summary)
                tablepath="outputs/tables/reliability/"+aid
                scope=dict(analysis_id=aid,method_id=bundle["contract"]["method"],calibration_id=bundle["calibration_id"],
                    scope=bundle["plan"]["scope"],actual_football_model_conditional_intervals_generated=True,
                    real_law_membership_certified=False,variants_calibrated=False,
                    family_counts=bundle["contract"]["families"],catalogue_rows=292,unsupported_rows=94,
                    input_versions={k:bundle["contract"][k] for k in ("data_version","identity_version","sample_version","design_id")},
                    parent_contract=bundle["plan"]["contract"],calibration_alpha=.01,
                    no_global198_coverage_claim=True,no_standard_error_or_p_value=True,
                    source_tables_reference=bundle["context"]["config"]["parent_manifests"],inputs=bundle["inputs"])
                write_json(tables/"method_scope.json",scope)
                family={f:dict(total=sum(r["family"]==f for r in a),supported=sum(r["family"]==f and r["point_probability_scale"] is not None for r in a),
                    positive=sum(r["family"]==f and r["model_conditional_support"]=="positive" for r in review),
                    negative=sum(r["family"]==f and r["model_conditional_support"]=="negative" for r in review)) for f in bundle["contract"]["families"]}
                write_json(tables/"display_data.json",dict(analysis_id=aid,table_directory=tablepath,families=family,
                    main_targets=[r for r in review if r["family"]=="CORE" or r["target_id"]==bundle["plan"]["sensitivity"]["recent_target"]],
                    workflow=["冻结与核验","原目标共同范围","指定描述对照","逐条修订结论","独立复算与复跑"],
                    important_limitations=["真实足球联合分布是否属于参照范围未知","永久全局冲击仍为范围外失败","变体只作描述，不复用原临界值","区间含零不等于无效；未控制赛前实力"],
                    simulated_validation_is_not_forecast_accuracy=True))
                data_dictionary(tables)
                figures=work/"figures"
                plot_results(figures,dict(interval_results=a,conclusion_review=review),aid,env)
                for p,h in man["inputs"].items():require(sha(ROOT/p)==h,"Input changed during run:"+p)
                for p,h in sources.items():require(sha(ROOT/p)==h,"Code changed during run:"+p)
                tabdest=ROOT/tablepath;figdest=ROOT/"outputs/figures/reliability"/aid
                recomputed={prefix+"/"+p.relative_to(src).as_posix():sha(p) for prefix,src in (("tables",tables),("figures",figures)) for p in sorted(src.rglob("*")) if p.is_file()}
                pub=[publish(ROOT,tables,tabdest),publish(ROOT,figures,figdest)]
                outputs={p.relative_to(ROOT).as_posix():sha(p) for dest in (tabdest,figdest) for p in sorted(dest.rglob("*")) if p.is_file()}
                man.update(status="completed_model_conditional_application",outputs=outputs,table_directory=tablepath,
                    figure_directory=figdest.relative_to(ROOT).as_posix(),publication=pub,
                    recomputed_core_outputs=recomputed,
                    independent_audit="pending",conclusions_human_review="not_performed")
            else:man["status"]="partial_not_published"
            man["last_elapsed_wall_seconds"]=time.monotonic()-started
            man["finished_utc"]=datetime.now(timezone.utc).isoformat();persist()
    except Exception as exc:
        man.update(status="failed_not_admitted",error=type(exc).__name__+":"+str(exc));persist()
        write_json(log/"failure.json",dict(error=man["error"],traceback=traceback.format_exc(),published_as_current=False))
        raise
    print(json.dumps(dict(run=log.relative_to(ROOT).as_posix(),analysis_id=aid,status=man["status"],phases=man["phases"])),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",default="config/reliability_analysis.json")
    parser.add_argument("--stage",choices=["check","infer","sensitivity","report","all"],default="all")
    parser.add_argument("--run",help="Resume a partial run with unchanged inputs/code")
    run(parser.parse_args())
