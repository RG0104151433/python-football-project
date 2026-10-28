"""Independent integer/set/Fraction reconstruction of the applied study.

Never imports application, sensitivity or interpretation calculation helpers.
The immutable original design builder is used only for the original catalogue.
"""
from pathlib import Path
import sys
import json
import csv
import gzip
from fractions import Fraction
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.reliability.design import build_design,sha
from src.reliability.experiment import write_json


def read(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def csvrows(p):
    op=gzip.open if str(p).endswith(".gz") else open
    with op(p,"rt",encoding="utf-8-sig",newline="") as stream:return list(csv.DictReader(stream))


def geo_rows(facts,classification,removed):
    out=[]
    for old in facts:
        r=dict(old)
        for role in ("home","away"):
            region,unit=old["base_"+role+"_region"],old["base_"+role+"_unit"]
            for rule in classification["overrides"]:
                if rule["team_id"] not in removed and rule["team_id"]==old[role+"_team_id"]:
                    if classification["scope"]["start"]<=r["date"]<=classification["scope"]["end"]:
                        if (region,unit)!=(rule["base_region"],rule["base_unit"]):raise AssertionError("Geographic base mismatch")
                        region,unit=rule["region"],rule["unit"]
            for merge in classification["merges"]:
                if region==merge["region"] and unit in merge["base_units"]:unit=merge["unit"]
            r[role+"_region"],r[role+"_unit"]=region,unit
        hr,ar,hu,au=[r[k] for k in ("home_region","away_region","home_unit","away_unit")]
        relation="unknown" if not hr or not ar else "cross_region" if hr!=ar else "unknown" if not hu or not au else "same_unit" if hu==au else "same_region_diff_unit"
        r.update(relation=relation,A_usable="true" if hr else "false",B_usable="true" if relation!="unknown" else "false",C_usable="true" if hu else "false")
        out.append(r)
    return out


def main(run_path,compare=None):
    run=ROOT/run_path;man=read(run/"run_manifest.json");report=run/"independent_audit.json"
    if report.exists():raise RuntimeError("Preserve original audit; use another run")
    counts=Counter()
    def ck(kind,ok):
        counts[kind]+=1
        if not ok:raise AssertionError(kind)
    ck("complete_run",man["status"]=="completed_model_conditional_application")
    for section in ("inputs","source","outputs"):
        for p,h in man[section].items():ck("hash_"+section,sha(ROOT/p)==h)
    for p,h in man["source"].items():ck("source_snapshot",sha(run/"source_snapshot"/p)==h)
    folder=ROOT/man["table_directory"];plan=read(ROOT/"config/reliability_analysis.json")
    ctx=build_design(ROOT);facts=ctx["facts"];allids=set(range(len(facts)))
    wins={i for i,r in enumerate(facts) if r["home_win"]=="1"};lookup={r["match_id"]:i for i,r in enumerate(facts)}
    cat={t["target_id"]:t for t in ctx["catalogue"]};cat_ids=set(cat)
    intervals=csvrows(folder/"interval_results.csv");bounded={r["target_id"]:r for r in csvrows(folder/"bounded_reference.csv")}
    cal=read(ROOT/Path(plan["contract"]).parent/"calibration.json")
    scales={r["target_id"]:r for r in csvrows(ROOT/plan["previous_scales"])}
    family_counts=Counter(t["family"] for t in ctx["catalogue"] if t["target_id"] in ctx["vectors"])
    ck("catalogue_292",len(intervals)==292 and {r["target_id"] for r in intervals}==cat_ids)
    for r in intervals:
        tid=r["target_id"];t=cat[tid];b=bounded[tid]
        ck("original_target_metadata",(r["question"],r["family"],r["kind"])==(t["question"],t["family"],t["kind"]))
        if tid not in ctx["vectors"]:
            ck("unsupported_stays_blank",r["point_probability_scale"]==r["lower_probability_scale"]==r["upper_probability_scale"]=="" and bool(r["unsupported_reason"]))
            continue
        a=ctx["vectors"][tid];point=sum(float(a[i]) for i in wins)
        ck("original_point",abs(float(r["point_probability_scale"])-point)<1e-11)
        lo=sum(min(float(v),0.) for v in a);hi=sum(max(float(v),0.) for v in a)
        s=float(scales[tid]["calibrated_score_scale"]);h=cal["critical"][r["family"]]*s
        ck("scalar_interval",abs(float(r["lower_probability_scale"])-max(lo,point-h))<1e-10 and abs(float(r["upper_probability_scale"])-min(hi,point+h))<1e-10)
        ck("unit_conversion",all(abs(float(r[k+"_display"])-100*float(r[k+"_probability_scale"]))<1e-10 for k in ("point","lower","upper")))
        delta=.05/(2*family_counts[r["family"]])
        ck("bounded_scalar",abs(float(b["lower_probability_scale"])-(lo+delta*(point-lo)))<1e-10 and abs(float(b["upper_probability_scale"])-(hi-delta*(hi-point)))<1e-10)
    specs=read(folder/"sensitivity_scenarios.json");templates=read(folder/"target_templates.json")
    selectors=read(folder/"selector_definitions.json");groups=read(folder/"sensitivity_groups.json")
    region=read(ROOT/ctx["config"]["q3_config"])
    expected_groups=dict(region["groups"])
    expected_groups.update(SUP_NORTH=dict(eligibility="C",home_regions=["002"],home_units=["015"]),
                           SUP_SSA=dict(eligibility="C",home_regions=["002"],home_units=["011","SSA_OTHER"]))
    ck("group_definitions",groups==expected_groups)
    # Templates must preserve every original component selector/sign/fraction.
    original=defaultdict(list)
    for p in ctx["components"]:original[p["target_id"]].append(p)
    for tid,parts in original.items():
        ck("original_template_length",len(parts)==len(templates[tid]))
        for p,t in zip(parts,templates[tid]):
            query={k:p[k] for k in ("scope","period_id","era","year","tournament_group") if p.get(k)}
            if p.get("region_group"):query["group"]=p["region_group"]
            ck("original_template_component",t["query"]==query and (t["multiplier"],t["numerator"],t["denominator"])==(p["multiplier"],p["q_numerator"],p["q_denominator"]))
    year_index={y:{i for i,r in enumerate(facts) if r["year"]==y} for y in sorted({r["year"] for r in facts})}
    era_index={e:{i for i,r in enumerate(facts) if r["era"]==e} for e in sorted({r["era"] for r in facts})}
    type_index={g:{i for i,r in enumerate(facts) if r["tournament_group"]==g} for g in ("friendly","non_friendly")}
    common=set.intersection(*[{facts[i][role] for i in ids for role in ("home_team_id","away_team_id")} for ids in era_index.values()])
    ck("common_team_list",{r["team_id"] for r in csvrows(folder/"common_teams.csv")}==common)
    team_ids={r[role] for r in facts for role in ("home_team_id","away_team_id")}
    ck("complete324_scenarios",len(specs)==324 and len({s["scenario_id"] for s in specs})==324)
    ck("all215_team_cases",{s["selection"]["team"] for s in specs if s["selection"]["kind"]=="without_team"}==team_ids)
    ck("all45_year_cases",{s["selection"]["year"] for s in specs if s["selection"]["kind"]=="without_year"}==set(range(1980,2025)))
    contexts={"original":facts};group_cache={};query_cache={};keeps={};context_of={};ledger_expected=set()
    def group_ids(gid,key):
        tag=(key,gid)
        if tag not in group_cache:
            spec=groups[gid];found=set()
            for i,r in enumerate(contexts[key]):
                if spec.get("eligibility") and r[spec["eligibility"]+"_usable"]!="true":continue
                if all(not spec.get(k) or r[field] in spec[k] for k,field in (("home_regions","home_region"),("away_regions","away_region"),("home_units","home_unit"),("away_units","away_unit"),("relations","relation"))):found.add(i)
            group_cache[tag]=found
        return group_cache[tag]
    def query_ids(q,key):
        tag=(key,json.dumps(q,sort_keys=True))
        if tag not in query_cache:
            sets=[allids]
            if q.get("group"):sets.append(group_ids(q["group"],key))
            if q.get("era"):sets.append(era_index[str(q["era"])])
            if q.get("year"):sets.append(year_index[str(q["year"])])
            if q.get("tournament_group"):sets.append(type_index[q["tournament_group"]])
            if q.get("scope")=="era":sets.append(era_index[q["period_id"]])
            if q.get("scope")=="rolling":
                lo,hi=map(int,q["period_id"].split("_"));sets.append(set().union(*(v for y,v in year_index.items() if lo<=int(y)<=hi)))
            query_cache[tag]=set.intersection(*sets)
        return query_cache[tag]
    for s in specs:
        sid=s["scenario_id"];sel=s["selection"];kind=sel["kind"];key="original"
        if kind=="without_year":keep=allids-year_index[str(sel["year"])]
        elif kind=="without_team":keep={i for i,r in enumerate(facts) if sel["team"] not in (r["home_team_id"],r["away_team_id"])}
        elif kind=="common_teams":
            ck("common_selection_definition",set(sel["teams"])==common)
            keep={i for i,r in enumerate(facts) if r["home_team_id"] in common and r["away_team_id"] in common}
        elif kind=="historical":keep={i for i,r in enumerate(facts) if r["home_team_id"] not in sel["teams"] and r["away_team_id"] not in sel["teams"]}
        elif kind=="known_both":keep={i for i,r in enumerate(facts) if r["home_region"] and r["away_region"]}
        else:keep=allids
        if kind=="relabel":
            key="|".join(sorted(sel["removed"]))
            if key not in contexts:contexts[key]=geo_rows(facts,region["study_classification"],sel["removed"])
            fields=[role+"_"+f for role in ("home","away") for f in ("region","unit")]
            ledger_expected.update((s["selection_id"],facts[i]["match_id"],"relabelled") for i,r in enumerate(contexts[key]) if any(facts[i][f]!=r[f] for f in fields))
        ledger_expected.update((s["selection_id"],facts[i]["match_id"],"excluded") for i in allids-keep)
        keeps[sid]=keep;context_of[sid]=key
    actual_ledger=csvrows(folder/"sensitivity_membership_changes.csv")
    ck("complete_membership_changes",len(actual_ledger)==len({(r["selection_id"],r["match_id"],r["change"]) for r in actual_ledger}) and
        {(r["selection_id"],r["match_id"],r["change"]) for r in actual_ledger}==ledger_expected)
    key_by_selection={s["selection_id"]:context_of[s["scenario_id"]] for s in specs}
    geo_fields=[role+"_"+f for role in ("home","away") for f in ("region","unit")]
    for r in actual_ledger:
        if r["change"]=="relabelled":
            i=lookup[r["match_id"]];new=contexts[key_by_selection[r["selection_id"]]][i]
            ck("relabel_ledger_values",r["old_labels"]=="|".join(facts[i][f] for f in geo_fields) and r["new_labels"]=="|".join(new[f] for f in geo_fields))
    byspec={s["scenario_id"]:s for s in specs};cellmap={}
    for j,r in enumerate(csvrows(folder/"sensitivity_cells.csv.gz")):
        sid,sel=r["scenario_id"],r["selector_id"]
        ids=query_ids(selectors[sel],context_of[sid]) & keeps[sid]
        ck("integer_cell",len(ids)==int(r["n"]) and len(ids&wins)==int(r["wins"]))
        ck("unique_cell",(sid,sel) not in cellmap);cellmap[(sid,sel)]=(len(ids),len(ids&wins),ids)
        if j and j%20000==0:print("Independently recounted cells",j,flush=True)
    refs={};refids={};reference_changed={}
    for r in csvrows(folder/"sensitivity_references.csv"):
        sid,key,st=r["scenario_id"],r["reference_key"],r["stratum"];kind=r["reference_kind"];s=byspec[sid]
        q=selectors[r["selector_id"]]
        expected_query={}
        if kind=="joint":expected_query["group"]=region["analysis_targets"][r["reference_owner"]]["reference_group"]
        if kind=="year":expected_query.update(scope="rolling",period_id=r["reference_owner"])
        ck("reference_selector_contract",q==expected_query)
        ids=query_ids(q,"original") if s["reference_policy"]=="fixed" else query_ids(q,context_of[sid]) & keeps[sid]
        if (sid,key) not in reference_changed:
            reference_changed[(sid,key)]=s["reference_policy"]!="fixed" and ids!=query_ids(q,"original")
        if kind=="type":cell=ids&type_index[st]
        elif kind=="era":cell=ids&era_index[st]
        elif kind=="year":cell=ids&year_index[st]
        else:e,t=st.split("|");cell=ids&era_index[e]&type_index[t]
        ck("reference_integer_counts",len(ids)==int(r["n_reference_total"]) and len(cell)==int(r["n_reference_stratum"]))
        if not r["weight_numerator"]:
            ck("invalid_reference_reason",r["status"]!="ok");w=None
        else:
            w=Fraction(int(r["weight_numerator"]),int(r["weight_denominator"]))
            policy=s["reference_policy"]
            if kind=="type" and policy=="equal_years":
                friendly=sum((Fraction(len(ids&ys&type_index["friendly"]),len(ids&ys)) for ys in year_index.values()),Fraction())/len(year_index)
                expected=friendly if st=="friendly" else 1-friendly
            elif kind=="era" and policy=="equal_eras":expected=Fraction(1,len(era_index))
            elif kind=="year" and policy=="equal_years":
                first,last=map(int,r["reference_owner"].split("_"));expected=Fraction(1,last-first+1)
            elif kind=="joint" and policy=="equal_eras":expected=Fraction(len(cell),len(era_index)*len(ids&era_index[st.split("|")[0]]))
            else:expected=Fraction(len(cell),len(ids))
            ck("exact_reference_fraction",w==expected)
        refs[(sid,key,st)]=w;refids[(sid,key)]=ids
    # Match template queries to persisted selectors without importing their hash helper.
    selector_by_query={json.dumps(q,sort_keys=True):k for k,q in selectors.items()}
    resultrows=csvrows(folder/"sensitivity_results.csv");seen=set();expected_cases={(s["scenario_id"],t) for s in specs for t in s["target_ids"]}
    coarse="Q3:supplement:NorthAfrica_minus_allSSA:adjusted"
    for r in resultrows:
        sid,tid=r["scenario_id"],r["target_id"];ck("unique_variant",(sid,tid) not in seen);seen.add((sid,tid))
        total=Fraction();bad=False;used=set();aff=False;raff=False
        for p in templates[tid]:
            w=Fraction(1)
            if p["reference_kind"]!="unit":
                rk=p["reference_kind"]+":"+p["reference_owner"]
                w=refs[(sid,rk,p["stratum"])]
                if w is None:bad=True;continue
                raff |= reference_changed[(sid,rk)] or w!=Fraction(p["numerator"],p["denominator"])
            if not w:continue
            sk=selector_by_query[json.dumps(p["query"],sort_keys=True)]
            n,k,ids=cellmap[(sid,sk)];used|=ids;aff |= ids!=query_ids(p["query"],"original")
            if n==0:bad=True
            else:total+=p["multiplier"]*w*Fraction(k,n)
        ck("variant_support",(r["estimate_probability"]=="")==bad)
        if not bad:
            ck("variant_exact_point",abs(float(r["estimate_probability"])-float(total))<1e-12)
            ck("variant_display_unit",abs(float(r["estimate_pp"])-100*float(total))<1e-10)
        baseline=cat[tid]["estimate_probability"] if tid in cat else None
        ck("variant_baseline",(r["baseline_probability"]=="")== (baseline is None))
        if baseline is not None and not bad:ck("variant_change_pp",abs(float(r["change_from_baseline_pp"])-100*(float(total)-baseline))<1e-10)
        ck("no_reused_calibration",r["lower_probability_scale"]==r["upper_probability_scale"]=="" and r["uncertainty_status"]=="not_calibrated_for_variant")
        ck("target_membership_count",len(used)==int(r["n_target_union"]))
        ck("affected_flags",(r["affects_target"]=="True")==aff and (r["affects_reference"]=="True")==raff)
        ck("applicable_semantics",(r["applicable"]=="True")==bool(aff or raff or r["check_type"] in ("alternative_reference","coarse_region")))
    ck("complete_variant_targets",seen==expected_cases)
    reviews=csvrows(folder/"conclusion_review.csv");bytarget=defaultdict(list)
    for r in resultrows:
        if r["applicable"]=="True":bytarget[r["target_id"]].append(r)
    for r in reviews:
        vv=bytarget[r["target_id"]];good=[v for v in vv if v["estimate_probability"]!=""]
        ck("review_case_counts",int(r["applicable_variants"])==len(vv) and int(r["computable_variants"])==len(good) and int(r["unsupported_variants"])==len(vv)-len(good))
    same=None
    if compare:
        other=read(ROOT/compare/"run_manifest.json")
        ck("distinct_repeat_run",Path(compare).as_posix()!=Path(run_path).as_posix())
        ck("repeat_same_identity",other["analysis_id"]==man["analysis_id"] and other["source"]==man["source"] and other["inputs"]==man["inputs"])
        ck("repeat_core_bytes",other["recomputed_core_outputs"]==man["recomputed_core_outputs"])
        same=True
    for p,h in man["inputs"].items():ck("inputs_still_unchanged",sha(ROOT/p)==h)
    result=dict(status="passed",decision_log_id="R20261028-05",checks=sum(counts.values()),by_category=dict(counts),
        run=run_path,analysis_id=man["analysis_id"],catalogue=292,supported=198,unsupported=94,
        sensitivity_scenarios=len(specs),sensitivity_rows=len(resultrows),common_teams=len(common),
        independent_set_integer_fraction_reconstruction=True,repeated_core_bytes_identical=same,
        human_review="not_performed",scientific_scope="Model conditional only; arithmetic audit does not certify true football law",
        source_sha256=sha(Path(__file__)),run_manifest_sha256=sha(run/"run_manifest.json"))
    write_json(report,result);print(json.dumps(result),flush=True)


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--run",required=True);p.add_argument("--compare")
    a=p.parse_args();main(a.run,a.compare)
