"""Independently audit Q2 from integer scores; no Q2 calculation functions."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from math import fsum
from pathlib import Path
import re
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0,str(PROJECT))
from src.data_contract import project_path
from src.tournaments.reporting import FIELDS, KEYS, verify_run


def audit(root, run_path, compare_path=None):
    def load(p):
        return json.loads(project_path(root,p).read_text(encoding="utf-8-sig"))
    def read(p):
        with project_path(root,p).open(encoding="utf-8-sig",newline="") as stream:
            reader=csv.DictReader(stream);return reader.fieldnames,list(reader)
    run=load(run_path)
    verification=verify_run(root,run_path)
    cfg=load(run["config_path"])
    qcfg=load(cfg["q1_integration_config"])
    analysis=load(qcfg["analysis_config"])
    identity=load(qcfg["identity_manifest"])
    _,clean=read("data/processed/"+analysis["data_version"]+"/matches_clean.csv")
    _,overlay=read(next(p for p in identity["outputs"] if p.endswith("/match_identity.csv")))
    by_id={r["match_id"]:r for r in overlay}
    checks=[]
    def check(name,condition):
        checks.append(dict(name=name,passed=bool(condition)))
        if not condition:raise ValueError("Q2 independent audit failed: "+name)
    def close(name,actual,expected):
        check(name,actual in ("",None) if expected is None else actual not in ("",None) and abs(float(actual)-expected)<=1e-9)
    check("identity_exact_unique_coverage",len(by_id)==len(overlay)==len(clean)==len({r["match_id"] for r in clean}) and set(by_id)=={r["match_id"] for r in clean})
    selected=[]
    bad_identity, bad_results = [], []
    for r in clean:
        o=by_id[r["match_id"]]
        if not (all(r[k]==o[k] for k in ("date","source_record_id")) and all(r[s+"_team_id"]==o[s+"_source_team_id"] and r[s+"_team"]==o[s+"_source_label"] for s in ("home","away"))):
            bad_identity.append(r["match_id"])
        h,a=int(r["home_score"]),int(r["away_score"])
        if not (r["outcome"]==("home" if h>a else "away" if h<a else "draw") and r["result_basis"]=="after_extra_time_excluding_shootout"):
            bad_results.append(r["match_id"])
        if (cfg["analysis_start"]<=r["date"]<=cfg["analysis_end"] and r["eligible_venue_analysis"]=="true" and r["is_neutral"]=="false"
            and r["eligible_tournament_analysis"]=="true" and r["tournament_group"] in ("friendly","non_friendly") and o["eligible_under_provisional_policy"]=="true"):
            selected.append(r)
    check("source_identity_all_clean:"+str(bad_identity[:10]),not bad_identity)
    check("score_basis_all_clean:"+str(bad_results[:10]),not bad_results)
    selected_ids={r["match_id"] for r in selected}
    td="outputs/tables/tournaments/"+run["analysis_id"]
    tables={}
    csv_paths=[p for p in run["outputs"] if p.startswith(td+"/") and p.endswith(".csv")]
    check("nine_tables",{Path(p).stem for p in csv_paths}==set(FIELDS))
    for p in csv_paths:
        name=Path(p).stem;fields,rows=read(p);data=project_path(root,p).read_bytes()
        check(name+":fields",fields==FIELDS[name].split())
        check(name+":encoding",data.startswith(b"\xef\xbb\xbf") and b"\r" not in data)
        keys=[tuple(r[k] for k in KEYS[name].split()) for r in rows]
        check(name+":keys",len(keys)==len(set(keys)) and keys==sorted(keys))
        for field in fields:
            if field.startswith("n_") or field=="label_year":
                check(name+":integer:"+field,all(re.fullmatch(r"\d+",r[field]) for r in rows))
            if field.endswith("_rate") or field in {"estimate","weight","standard_error","ci_lower","ci_upper","confidence_level"}:
                check(name+":decimal:"+field,all(r[field]=="" or re.fullmatch(r"-?\d+\.\d{10}",r[field]) for r in rows))
        tables[name]=rows
    check("sample_membership",{r["match_id"] for r in tables["analysis_membership"] if r["included"]=="true"}==selected_ids)
    check("membership_covers_clean",{r["match_id"] for r in tables["analysis_membership"]}==set(by_id))
    check("membership_booleans",all(r["included"] in ("true","false") for r in tables["analysis_membership"]))
    check("sample_count",len(selected)==run["summary"]["n_matches"])
    flow=tables["sample_flow"]
    dm=load("data/processed/"+analysis["data_version"]+"/dataset_manifest.json")
    check("raw_flow_accounting",sum(int(r["n_records"]) for r in flow if r["basis"]=="upstream_raw")==dm["counts"]["input"])
    check("processed_flow_accounting",sum(int(r["n_records"]) for r in flow if r["basis"]=="processed_matches")==len(clean))
    check("included_flow",sum(int(r["n_records"]) for r in flow if r["basis"]=="processed_matches" and r["stage"]=="included")==len(selected))
    check("membership_reasons",all((r["primary_exclusion_reason"]=="") == (r["included"]=="true") for r in tables["analysis_membership"]))
    qrun=load(cfg["q1_run_manifest"])
    _,qm=read(next(p for p in qrun["outputs"] if p.endswith("/analysis_membership.csv")))
    check("q1_exact_selected_ids",selected_ids=={r["match_id"] for r in qm if r["in_classified_venue"]=="true"})
    groups=("friendly","non_friendly")
    periods={("overall","all"):(cfg["analysis_start"],cfg["analysis_end"])}
    periods.update({("era",e["id"]):(e["start"],e["end"]) for e in analysis["eras"]})
    first,last=int(cfg["analysis_start"][:4]),int(cfg["analysis_end"][:4])
    periods.update({("year",str(y)):(f"{y}-01-01",f"{y}-12-31") for y in range(first,last+1)})
    expected_windows={f"{y}_{y+9}":(f"{y}-01-01",f"{y+9}-12-31") for y in range(first,last-8)}
    periods.update({("rolling",w):dates for w,dates in expected_windows.items()})
    subsets={(scope,pid,g):[r for r in selected if a<=r["date"]<=b and r["tournament_group"]==g] for (scope,pid),(a,b) in periods.items() for g in groups}
    def count(scope,pid,g):
        rows=subsets[(scope,pid,g)];n=len(rows)
        win=sum(int(r["home_score"])>int(r["away_score"]) for r in rows)
        draw=sum(int(r["home_score"])==int(r["away_score"]) for r in rows)
        return dict(n_matches=n,n_home_wins=win,n_draws=draw,n_away_wins=n-win-draw,
                    home_win_rate=win/n if n else None,draw_rate=draw/n if n else None,away_win_rate=(n-win-draw)/n if n else None)
    recounted={key:count(*key) for key in subsets}
    for name in ("grouped_counts","rolling_counts"):
        expected_keys={key for key in subsets if (key[0]=="rolling")== (name=="rolling_counts")}
        actual_keys={(r.get("scope","rolling"),r.get("period_id",r.get("window_id")),r["tournament_group"]) for r in tables[name]}
        check(name+":all_expected_cells",actual_keys==expected_keys)
        for row in tables[name]:
            key=(row.get("scope","rolling"),row.get("period_id",row.get("window_id")),row["tournament_group"])
            for field,value in recounted[key].items():
                if field.startswith("n_"):check(name+":"+str(key)+field,int(row[field])==value)
                else:close(name+":"+str(key)+field,row[field],value)
            check(name+":status:"+str(key),row["status"]==("ok" if recounted[key]["n_matches"] else "empty_group"))
    actual_windows={r["window_id"]:r for r in tables["rolling_windows"]}
    check("window_keys",set(actual_windows)==set(expected_windows))
    actual_members=defaultdict(set)
    for r in tables["window_membership"]:actual_members[r["window_id"]].add(r["match_id"])
    check("window_member_known_windows",set(actual_members)<=set(expected_windows))
    for wid,(a,b) in expected_windows.items():
        w=actual_windows[wid];rs=subsets[("rolling",wid,"friendly")]+subsets[("rolling",wid,"non_friendly")]
        observed={int(r["date"][:4]) for r in rs};all_years=set(range(int(a[:4]),int(b[:4])+1))
        check("window_definition:"+wid,(w["start_date"],w["end_date"],int(w["label_year"]),int(w["n_calendar_years"]))==(a,b,int(b[:4]),10))
        check("window_counts:"+wid,int(w["n_matches"])==len(rs) and int(w["n_observed_years"])==len(observed) and json.loads(w["missing_years"])==sorted(all_years-observed))
        check("window_members:"+wid,actual_members[wid]=={r["match_id"] for r in rs})
    references={}
    era_ids=[e["id"] for e in analysis["eras"]]
    for scope,pid in [("overall","all")]+[("rolling",w) for w in expected_windows]:
        kind="era" if scope=="overall" else "year"
        strata=era_ids if scope=="overall" else [str(y) for y in range(int(expected_windows[pid][0][:4]),int(expected_windows[pid][1][:4])+1)]
        total=sum(recounted[(kind,s,g)]["n_matches"] for s in strata for g in groups)
        rid=f"{scope}:{pid}:{kind}:pooled_matches"
        for s in strata:
            n=sum(recounted[(kind,s,g)]["n_matches"] for g in groups)
            references[(rid,s)]=dict(scope=scope,period_id=pid,stratum_kind=kind,n=n,total=total,weight=n/total if total else None)
    check("reference_exact_keys",{(w["reference_id"],w["stratum_id"]) for w in tables["reference_weights"]}==set(references))
    for w in tables["reference_weights"]:
        expected=references[(w["reference_id"],w["stratum_id"])]
        check("reference_metadata:"+w["reference_id"]+w["stratum_id"],all(w[k]==expected[k] for k in ("scope","period_id","stratum_kind")) and int(w["n_reference_matches"])==expected["n"] and int(w["n_reference_total"])==expected["total"])
        close("reference_value:"+w["reference_id"]+w["stratum_id"],w["weight"],expected["weight"])
        check("reference_status:"+w["reference_id"]+w["stratum_id"],w["status"]==("empty_reference" if not expected["total"] else "zero_weight" if not expected["n"] else "ok"))
    requests=[("overall","all","raw"),("overall","all","era_standardized")]+[("era",e,"raw") for e in era_ids]
    requests += [("rolling",w,e) for w in expected_windows for e in ("raw","year_standardized")]
    rate_keys={f"rate:{s}:{p}:{e}:{g}" for s,p,e in requests for g in groups}
    diff_keys={f"difference:{s}:{p}:{e}" for s,p,e in requests}
    rates={r["estimate_id"]:r for r in tables["type_estimates"]};diffs={r["contrast_id"]:r for r in tables["type_differences"]}
    check("all_rate_targets",set(rates)==rate_keys);check("all_difference_targets",set(diffs)==diff_keys)
    def rate(scope,pid,estimand,g):
        if estimand=="raw":return recounted[(scope,pid,g)]["home_win_rate"],"ok" if recounted[(scope,pid,g)]["n_matches"] else "empty_group",""
        kind="era" if scope=="overall" else "year"
        rid=f"{scope}:{pid}:{kind}:pooled_matches"
        ws=[(s,w) for (reference_id,s),w in references.items() if reference_id==rid]
        if not ws or ws[0][1]["total"]==0:return None,"empty_reference",rid
        if any(w["weight"]>0 and not recounted[(kind,s,g)]["n_matches"] for s,w in ws):return None,"missing_stratum",rid
        return fsum(w["weight"]*recounted[(kind,s,g)]["home_win_rate"] for s,w in ws if w["weight"]>0),"ok",rid
    for scope,pid,e in requests:
        expected_rates={}
        expected_statuses=[]
        for g in groups:
            key=f"rate:{scope}:{pid}:{e}:{g}";row=rates[key];v,status,rid=rate(scope,pid,e,g);expected_rates[g]=v;expected_statuses.append(status)
            close(key,row["estimate"],v)
            check(key+":metadata",(row["scope"],row["period_id"],row["estimand"],row["tournament_group"],row["reference_id"],row["unit"],row["status"],int(row["n_matches"]))==(scope,pid,e,g,rid,"probability",status,recounted[(scope,pid,g)]["n_matches"]))
        key=f"difference:{scope}:{pid}:{e}";d=diffs[key];f,n=expected_rates.values()
        close(key,d["estimate"],None if f is None or n is None else 100*(f-n))
        dstatus="ok" if f is not None and n is not None else "empty_reference" if "empty_reference" in expected_statuses else "missing_stratum" if e!="raw" else "not_estimable"
        check(key+":metadata",(d["scope"],d["period_id"],d["estimand"],d["reference_id"],d["unit"],d["status"],int(d["n_friendly"]),int(d["n_non_friendly"]))==(scope,pid,e,rid,"percentage_points",dstatus,recounted[(scope,pid,"friendly")]["n_matches"],recounted[(scope,pid,"non_friendly")]["n_matches"]))
    for row in [*rates.values(),*diffs.values()]:
        check("inference_off:"+row.get("estimate_id",row.get("contrast_id")),row["uncertainty_status"]=="not_run" and all(row[k]=="" for k in ("standard_error","ci_lower","ci_upper","confidence_level","method_id","method_version")))
    defs=load(td+"/target_definitions.json")["targets"]
    check("target_definitions",len(defs)==len(rate_keys)+len(diff_keys) and {d["target_id"] for d in defs}==rate_keys|diff_keys)
    for d in defs:
        target=rates.get(d["target_id"],diffs.get(d["target_id"]))
        expected_terms=([dict(tournament_group=target["tournament_group"],multiplier=1)] if "estimate_id" in target else [dict(tournament_group="friendly",multiplier=100),dict(tournament_group="non_friendly",multiplier=-100)])
        check("target_definition:"+d["target_id"],all(d[k]==target[k] for k in ("scope","period_id","estimand","reference_id","unit")) and d["terms"]==expected_terms)
    _,qc=read(next(p for p in qrun["outputs"] if p.endswith("/era_tournament_summary.csv")))
    check("q1_ten_cells",all(all(int(q[k])==recounted[("era",q["analysis_era_id"],q["tournament_group"])][k] for k in ("n_matches","n_home_wins","n_draws","n_away_wins")) for q in qc))
    comparison=None
    if compare_path:
        verify_run(root,compare_path);previous=load(compare_path)
        check("repeat_analysis_id",previous["analysis_id"]==run["analysis_id"])
        check("repeat_core_hashes",previous["core_outputs"]==run["core_outputs"])
        comparison=dict(run_manifest=compare_path,identical_core_artifacts=len(run["core_outputs"]))
    return dict(passed=True,run_manifest=run_path,analysis_id=run["analysis_id"],selected_matches=len(selected),verification=verification,
                n_checks=len(checks),checks=checks,table_rows={k:len(v) for k,v in tables.items()},comparison=comparison,
                audit_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                created_at_utc=datetime.now(timezone.utc).isoformat(),inference="not_run",human_reproduction="not_performed_by_this_audit")


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--run",required=True);parser.add_argument("--output",required=True);parser.add_argument("--compare")
    args=parser.parse_args();path=project_path(PROJECT,args.output)
    if path.exists():raise FileExistsError("Choose a new audit output path")
    report=audit(PROJECT,args.run,args.compare);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8",newline="\n") as stream:json.dump(report,stream,ensure_ascii=False,indent=2);stream.write("\n")
    print(json.dumps(dict(passed=True,n_checks=report["n_checks"],analysis_id=report["analysis_id"],comparison=report["comparison"],output=args.output),ensure_ascii=True))


if __name__=="__main__":main()
