"""Metadata-selected descriptive perturbations; never reuse baseline intervals."""
from collections import defaultdict
from fractions import Fraction
import copy
import hashlib
import json
import numpy as np
from .design import require
from ..regions.io import apply_study_labels


def identity(prefix, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return prefix + hashlib.sha256(raw).hexdigest()[:24]


def relabel(facts, classification, removed):
    cfg = copy.deepcopy(classification)
    cfg["overrides"] = [o for o in cfg["overrides"] if o["team_id"] not in removed]
    out = []
    for original in facts:
        r = dict(original)
        for role in ("home", "away"):
            for field in ("region", "unit"):
                r[role+"_"+field] = r["base_"+role+"_"+field]
        r["direction"], r["relation"] = r["base_direction"], r["base_relation"]
        r = apply_study_labels(r, cfg)
        for flag in ("A", "B", "C"):
            r[flag+"_usable"] = "true" if r[flag+"_usable"] else "false"
        out.append(r)
    return out


class Selectors:
    def __init__(self, facts, groups):
        self.facts, self.groups = facts, groups
        self.arrays = {k:np.asarray([r[k] for r in facts]) for k in
            ("era", "year", "tournament_group", "home_region", "away_region", "home_unit", "away_unit", "relation",
             "A_usable", "B_usable", "C_usable")}
        self.cache, self.group_cache = {}, {}

    def group(self, gid):
        if gid not in self.group_cache:
            spec = self.groups[gid];mask = np.ones(len(self.facts), bool)
            if spec.get("eligibility"):
                mask &= self.arrays[spec["eligibility"]+"_usable"] == "true"
            for key, field in (("home_regions", "home_region"), ("away_regions", "away_region"),
                ("home_units", "home_unit"), ("away_units", "away_unit"), ("relations", "relation")):
                if spec.get(key):mask &= np.isin(self.arrays[field], spec[key])
            self.group_cache[gid] = mask
        return self.group_cache[gid]

    def indices(self, query):
        key = identity("selector-", query)
        if key not in self.cache:
            m = np.ones(len(self.facts), bool)
            if query.get("group"):m &= self.group(query["group"])
            for field in ("era", "year", "tournament_group"):
                if query.get(field):m &= self.arrays[field] == str(query[field])
            if query.get("scope") == "era":m &= self.arrays["era"] == query["period_id"]
            if query.get("scope") == "rolling":
                lo,hi = query["period_id"].split("_")
                m &= (self.arrays["year"] >= lo) & (self.arrays["year"] <= hi)
            self.cache[key] = np.flatnonzero(m)
        return key, self.cache[key]


def compile_templates(context):
    templates = defaultdict(list)
    for p in context["components"]:
        tid = p["target_id"];q = {k:p[k] for k in ("scope", "period_id", "era", "year", "tournament_group") if p.get(k)}
        if p.get("region_group"):q["group"] = p["region_group"]
        kind, owner, stratum = "unit", "all", "all"
        if tid.startswith("Q1:") and p.get("tournament_group"):
            kind,owner,stratum = "type","all",p["tournament_group"]
        elif tid.startswith("Q2:") and (p.get("year") or p.get("era")):
            kind = "year" if p.get("year") else "era"
            owner = p["period_id"] if kind == "year" else "all"
            stratum = str(p.get("year") or p["era"])
        elif tid.startswith("Q3:") and p.get("era"):
            kind,owner,stratum = "joint",p["region_target"],p["era"]+"|"+p["tournament_group"]
        templates[tid].append(dict(query=q, reference_kind=kind, reference_owner=owner, stratum=stratum,
            numerator=p["q_numerator"], denominator=p["q_denominator"], multiplier=p["multiplier"]))
    return dict(templates)


class Engine:
    def __init__(self, context, region_config):
        self.context, self.facts, self.cfg = context,context["facts"],region_config
        self.groups = copy.deepcopy(region_config["groups"])
        self.groups["SUP_NORTH"] = dict(eligibility="C",home_regions=["002"],home_units=["015"])
        self.groups["SUP_SSA"] = dict(eligibility="C",home_regions=["002"],home_units=["011","SSA_OTHER"])
        self.templates = compile_templates(context)
        # New coarse contrast uses the original African reference and ten cells.
        self.coarse_id = "Q3:supplement:NorthAfrica_minus_allSSA:adjusted"
        self.templates[self.coarse_id] = []
        eras = sorted({r["era"] for r in self.facts})
        # Recover reference fractions by owner, independent of which African contrast appears first.
        base_joint = {}
        for ps in self.templates.values():
            for p in ps:
                if p["reference_kind"] == "joint" and p["reference_owner"] == "C_AFR":base_joint[p["stratum"]]=(p["numerator"],p["denominator"])
        require(len(base_joint) == 10, "Missing original African ten-cell reference")
        for g,sign in (("SUP_NORTH",1),("SUP_SSA",-1)):
            for e in eras:
                for t in ("friendly","non_friendly"):
                    s=e+"|"+t;n,d=base_joint[s]
                    self.templates[self.coarse_id].append(dict(query=dict(group=g,era=e,tournament_group=t),
                        reference_kind="joint",reference_owner="C_AFR",stratum=s,numerator=n,denominator=d,multiplier=sign))
        self.base = Selectors(self.facts,self.groups);self.current = self.base
        self.y = np.asarray([int(r["home_win"]) for r in self.facts])
        self.catalogue = {t["target_id"]:t for t in context["catalogue"]}
        self.catalogue[self.coarse_id] = dict(question="Q3",family="SUPPLEMENT",kind="difference",label="北非减全部撒哈拉以南",estimate_probability=None)
        self.selector_definitions = {}
        self.baseline_weights = {}
        for ps in self.templates.values():
            for p in ps:
                key=(p["reference_kind"],p["reference_owner"],p["stratum"])
                w=Fraction(p["numerator"],p["denominator"])
                require(key not in self.baseline_weights or self.baseline_weights[key] == w, "Reference fraction collision")
                self.baseline_weights[key]=w

    def query(self, q):
        key,ids=self.current.indices(q)
        self.selector_definitions[key]=q
        return key,ids

    def start(self, scenario, keep, current=None):
        self.scenario=scenario;self.keep=keep;self.current=current or self.base
        self.cell_cache={};self.ref_cache={};self.cells=[];self.references=[]

    def cell(self, query):
        key,allids=self.query(query)
        if key not in self.cell_cache:
            ids=allids[self.keep[allids]]
            self.cell_cache[key]=(len(ids),int(self.y[ids].sum()),ids)
            self.cells.append(dict(scenario_id=self.scenario["scenario_id"],selector_id=key,n=len(ids),wins=int(self.y[ids].sum())))
        return key,self.cell_cache[key]

    def reference(self, p):
        kind,owner=p["reference_kind"],p["reference_owner"]
        key=kind+":"+owner
        if key not in self.ref_cache:
            policy=self.scenario["reference_policy"]
            q={}
            if kind=="joint":q["group"]=self.cfg["analysis_targets"][owner]["reference_group"]
            if kind=="year":q.update(scope="rolling",period_id=owner)
            selector,original_ids=self.base.indices(q)
            sid,current_ids=self.query(q)
            selected_ids=current_ids[self.keep[current_ids]]
            fixed=policy=="fixed"
            ids=original_ids if fixed else selected_ids
            # With fixed q the reference remains the ORIGINAL population.
            changed=not fixed and not np.array_equal(selected_ids,original_ids)
            by=defaultdict(int)
            for i in ids:
                r=self.facts[i]
                s=r["tournament_group"] if kind=="type" else r["era"] if kind=="era" else r["year"] if kind=="year" else r["era"]+"|"+r["tournament_group"]
                by[s]+=1
            needed=sorted(s for k,o,s in self.baseline_weights if (k,o)==(kind,owner))
            weights={};invalid=""
            if fixed:
                weights={s:self.baseline_weights[(kind,owner,s)] for s in needed}
            elif not len(ids):invalid="empty_reference"
            elif kind=="type" and policy=="equal_years":
                years=sorted({r["year"] for r in self.facts})
                counts={yr:(sum(self.facts[i]["tournament_group"]=="friendly" for i in ids if self.facts[i]["year"]==yr),
                            sum(self.facts[i]["year"]==yr for i in ids)) for yr in years}
                if any(n==0 for w,n in counts.values()):invalid="missing_reference_year"
                else:
                    w=sum((Fraction(w,n) for w,n in counts.values()),Fraction(0))/len(years)
                    weights={"friendly":w,"non_friendly":1-w}
            elif kind in ("era","year") and policy in ("equal_eras","equal_years"):
                if any(by[s]==0 for s in needed):invalid="missing_reference_stratum"
                else:weights={s:Fraction(1,len(needed)) for s in needed}
            elif kind=="joint" and policy=="equal_eras":
                eras=sorted({s.split("|")[0] for s in needed})
                totals={e:sum(n for s,n in by.items() if s.startswith(e+"|")) for e in eras}
                if any(n==0 for n in totals.values()):invalid="missing_reference_era"
                else:weights={s:Fraction(by[s],len(eras)*totals[s.split("|")[0]]) for s in needed}
            else:weights={s:Fraction(by[s],len(ids)) for s in needed}
            for s in needed:
                w=weights.get(s)
                self.references.append(dict(scenario_id=self.scenario["scenario_id"],reference_key=key,stratum=s,
                    selector_id=sid,reference_kind=kind,reference_owner=owner,reference_policy=policy,
                    weight_numerator=w.numerator if w is not None else None,weight_denominator=w.denominator if w is not None else None,
                    n_reference_stratum=by[s],n_reference_total=len(ids),status=invalid or "ok"))
            self.ref_cache[key]=(weights,invalid,changed)
        return key,self.ref_cache[key]

    def evaluate(self, tid):
        total=Fraction(0);missing=[];used=[];affected=False;refaffected=False
        for p in self.templates[tid]:
            w=Fraction(1)
            if p["reference_kind"]!="unit":
                rk,(weights,err,refchange)=self.reference(p)
                refaffected |= refchange
                if err:missing.append(err+":"+rk);continue
                w=weights[p["stratum"]]
                if w != Fraction(p["numerator"],p["denominator"]):refaffected=True
            if not w:continue
            sk,(n,wins,ids)=self.cell(p["query"])
            baseids=self.base.indices(p["query"])[1]
            affected |= not np.array_equal(ids,baseids)
            if n==0:missing.append("positive_reference_empty:"+sk);continue
            total+=p["multiplier"]*w*Fraction(wins,n);used.append(ids)
        meta=self.catalogue[tid];baseline=meta["estimate_probability"]
        value=None if missing else float(total)
        n=len(np.unique(np.concatenate(used))) if used else 0
        return dict(scenario_id=self.scenario["scenario_id"],selection_id=self.scenario["selection_id"],
            target_id=tid,sensitivity_target_id=self.scenario["scenario_id"]+"::"+tid,question=meta["question"],family=meta["family"],
            label=meta["label"],check_type=self.scenario["check_type"],reference_policy=self.scenario["reference_policy"],
            subsample_id=self.scenario["subsample_id"],classification_id=self.scenario["classification_id"],
            n_parent_after=int(self.keep.sum()),n_target_union=n,baseline_probability=baseline,estimate_probability=value,
            estimate_pp=None if value is None else 100*value,
            change_from_baseline_pp=None if value is None or baseline is None else 100*(value-baseline),
            status="unsupported" if missing else "ok",missing_reason=";".join(sorted(set(missing))),
            affects_target=bool(affected),affects_reference=bool(refaffected),
            applicable=bool(affected or refaffected or self.scenario["check_type"] in ("alternative_reference","coarse_region")),
            comparison_type="new_target" if tid==self.coarse_id else "newly_estimable_variant" if baseline is None and value is not None else "defined_variant",
            lower_probability_scale=None,upper_probability_scale=None,uncertainty_status="not_calibrated_for_variant")


def run_sensitivity(bundle):
    ctx=bundle["context"];root=bundle["root"]
    from .application import read
    cfg=read(root/ctx["config"]["q3_config"]);eng=Engine(ctx,cfg)
    facts=eng.facts;n=len(facts);allkeep=np.ones(n,bool)
    years=np.asarray([int(r["year"]) for r in facts]);teams=sorted({r[k] for r in facts for k in ("home_team_id","away_team_id")})
    ht=np.asarray([r["home_team_id"] for r in facts]);at=np.asarray([r["away_team_id"] for r in facts])
    core=[t["target_id"] for t in ctx["catalogue"] if t["family"]=="CORE" and t["target_id"] in ctx["vectors"]]
    conditional=[t["target_id"] for t in ctx["catalogue"] if t["family"]=="CONDITIONAL" and t["target_id"] in ctx["vectors"]]
    q3=[t["target_id"] for t in ctx["catalogue"] if t["question"]=="Q3"]
    scenarios=[];results=[];cellrows=[];refrows=[];ledger=[];seen_selection=set();selection_definitions={}
    def execute(selection, policies, ids, check_type, current=None):
        kind=selection["kind"];keep=allkeep.copy();changedfacts=None
        if kind=="without_year":keep &= years!=selection["year"]
        elif kind=="without_team":keep &= (ht!=selection["team"]) & (at!=selection["team"])
        elif kind=="common_teams":keep &= np.isin(ht,selection["teams"]) & np.isin(at,selection["teams"])
        elif kind=="historical":keep &= ~np.isin(ht,selection["teams"]) & ~np.isin(at,selection["teams"])
        elif kind=="known_both":keep &= np.asarray([r["A_usable"]=="true" and bool(r["away_region"]) for r in facts])
        elif kind=="relabel":
            changedfacts=relabel(facts,cfg["study_classification"],selection["removed"])
            current=Selectors(changedfacts,eng.groups)
        selection_id=identity("selection-",selection)
        subset=identity("subset-",[facts[i]["match_id"] for i in np.flatnonzero(keep)])
        classification=identity("classification-",selection["removed"]) if kind=="relabel" else "original-study-v4"
        if selection_id not in seen_selection:
            seen_selection.add(selection_id);selection_definitions[selection_id]=selection
            for i in np.flatnonzero(~keep):ledger.append(dict(selection_id=selection_id,match_id=facts[i]["match_id"],change="excluded",reason=kind))
            if changedfacts:
                fields=[r+"_"+f for r in ("home","away") for f in ("region","unit")]
                for old,new in zip(facts,changedfacts):
                    if any(old[k]!=new[k] for k in fields):
                        ledger.append(dict(selection_id=selection_id,match_id=old["match_id"],change="relabelled",reason=kind,
                            old_labels="|".join(old[k] for k in fields),new_labels="|".join(new[k] for k in fields)))
        for policy in policies:
            sc=dict(selection_id=selection_id,selection=selection,reference_policy=policy,check_type=check_type,
                target_ids=ids,subsample_id=subset,classification_id=classification)
            sc["scenario_id"]=identity("scenario-",dict(selection=selection,policy=policy,check_type=check_type))
            eng.start(sc,keep,current)
            for tid in ids:results.append(eng.evaluate(tid))
            cellrows.extend(eng.cells);refrows.extend(eng.references);scenarios.append(sc)
    # Exact baseline reconstruction independently of the A multiplication.
    baseline=dict(scenario_id="baseline_check",selection_id="baseline",reference_policy="fixed",check_type="baseline",
        subsample_id="original",classification_id="original")
    eng.start(baseline,allkeep)
    for tid,meta in eng.catalogue.items():
        if tid==eng.coarse_id:continue
        r=eng.evaluate(tid);expected=meta["estimate_probability"]
        require((r["estimate_probability"] is None)==(expected is None),"Sensitivity baseline support mismatch:"+tid)
        require(expected is None or abs(r["estimate_probability"]-expected)<1e-12,"Sensitivity baseline point mismatch:"+tid)
    for yr in range(1980,2025):
        targets=core+([bundle["plan"]["sensitivity"]["recent_target"]] if yr>=2020 else [])
        execute(dict(kind="without_year",year=yr),["fixed","recomputed"],targets,"leave_one_year_out")
    era_teams=[{r[k] for r in facts if r["era"]==e for k in ("home_team_id","away_team_id")} for e in sorted({r["era"] for r in facts})]
    common=sorted(set.intersection(*era_teams))
    common_targets=[tid for tid in core if tid.startswith("Q1:") or tid.startswith("Q2:")]+["Q2:difference:overall:all:raw"]
    execute(dict(kind="common_teams",teams=common),["fixed","recomputed"],common_targets,"common_teams")
    for team in teams:execute(dict(kind="without_team",team=team),["fixed"],core+conditional,"leave_one_team_out")
    execute(dict(kind="all",tag="Q1_equal_years"),["equal_years"],[tid for tid in core if tid.startswith("Q1:")],"alternative_reference")
    execute(dict(kind="all",tag="Q2_equal_eras"),["equal_eras"],[tid for tid in core if tid.startswith("Q2:")],"alternative_reference")
    execute(dict(kind="all",tag="Q2_window_equal_years"),["equal_years"],[t["target_id"] for t in ctx["catalogue"] if t["family"]=="ROLLING"],"alternative_reference")
    execute(dict(kind="all",tag="Q3_equal_eras"),["equal_eras"],q3,"alternative_reference")
    for removed in [[t] for t in bundle["plan"]["sensitivity"]["geographic_exception_ids"]]+[bundle["plan"]["sensitivity"]["geographic_exception_ids"]]:
        execute(dict(kind="relabel",removed=removed),["fixed","recomputed"],q3,"geographic_exception")
    execute(dict(kind="historical",teams=bundle["plan"]["sensitivity"]["historical_carrier_ids"]),["fixed","recomputed"],q3,"historical_carriers")
    execute(dict(kind="known_both"),["fixed","recomputed"],q3,"known_geography_subset")
    execute(dict(kind="all",tag="NorthAfrica_allSSA"),["fixed"],[eng.coarse_id],"coarse_region")
    common_rows=[dict(team_id=t,definition="appears in either role in all five original eras; both fixture teams required") for t in common]
    return dict(results=results,cells=cellrows,references=refrows,membership=ledger,common_teams=common_rows,
        scenarios=scenarios,selectors=eng.selector_definitions,templates=eng.templates,groups=eng.groups,
        selection_definitions=selection_definitions,baseline_reconstructed=True)
