"""Deterministic accounting and coefficient reconstruction, not inference."""
from collections import Counter, defaultdict
from math import fsum, isfinite

from .data import GROUPS, require


def validate_tables(rows, analysis, tables, definitions, sid):
    checks = []
    def check(name, value):
        require(value, "TQ_RECONCILIATION_FAILED", name)
        checks.append(dict(name=name, passed=True))
    def near(name, actual, expected):
        check(name, actual is None if expected is None else actual is not None and isfinite(actual) and abs(actual-expected) <= 1e-12)
    ids = {r["match_id"] for r in rows}
    check("selected_unique", len(ids) == len(rows))
    members = tables["analysis_membership"]
    check("membership_unique", len(members) == len({r["match_id"] for r in members}))
    check("membership_exact_selection", {r["match_id"] for r in members if r["included"]} == ids)
    check("membership_sample_id", all(r["sample_id"] == sid for r in members))
    era_by_id = {e["id"]: e for e in analysis["eras"]}
    windows = {w["window_id"]: w for w in tables["rolling_windows"]}
    sets = {("overall", "all"): rows}
    for e in analysis["eras"]:
        sets[("era", e["id"])] = [r for r in rows if e["start"] <= r["date"] <= e["end"]]
    for year in range(int(analysis["analysis_start"][:4]), int(analysis["analysis_end"][:4])+1):
        sets[("year", str(year))] = [r for r in rows if r["year"] == year]
    window_members = tables["window_membership"]
    keys = [(r["window_id"], r["match_id"]) for r in window_members]
    require(len(keys) == len(set(keys)), "TQ_WINDOW_DUPLICATE", "Repeated window/match key")
    check("window_members_known", all(w in windows and m in ids for w, m in keys))
    actual_members = defaultdict(set)
    for w, mid in keys:
        actual_members[w].add(mid)
    for wid, w in windows.items():
        group = [r for r in rows if w["start_date"] <= r["date"] <= w["end_date"]]
        sets[("rolling", wid)] = group
        check("window_exact_members:"+wid, actual_members[wid] == {r["match_id"] for r in group})
        check("window_count:"+wid, len(group) == w["n_matches"] and w["n_calendar_years"] == 10)
        years = {r["year"] for r in group}
        check("window_years:"+wid, len(years) == w["n_observed_years"] and w["missing_years"] ==
              sorted(set(range(int(w["start_date"][:4]), int(w["end_date"][:4])+1))-years))
    counts = {(r["scope"], r["period_id"], r["tournament_group"]): r for r in tables["grouped_counts"]}
    counts.update({("rolling", r["window_id"], r["tournament_group"]): r for r in tables["rolling_counts"]})
    for key, c in counts.items():
        scope, period, g = key
        group = [r for r in sets[(scope, period)] if r["tournament_group"] == g]
        n = len(group)
        wins = sum(r["home_score"] > r["away_score"] for r in group)
        draws = sum(r["home_score"] == r["away_score"] for r in group)
        check("counts:"+str(key), (c["n_matches"], c["n_home_wins"], c["n_draws"], c["n_away_wins"]) == (n, wins, draws, n-wins-draws))
        for field, value in (("home_win_rate", wins), ("draw_rate", draws), ("away_win_rate", n-wins-draws)):
            near(field+":"+str(key), c[field], value/n if n else None)
    for scope in ("overall", "era", "year"):
        check("partition:"+scope, sum(c["n_matches"] for (s,p,g),c in counts.items() if s == scope) == len(rows))
    refs = defaultdict(list)
    for w in tables["reference_weights"]:
        refs[w["reference_id"]].append(w)
    for rid, weights in refs.items():
        check("reference_keys:"+rid, len({w["stratum_id"] for w in weights}) == len(weights))
        expected_scope = "era" if weights[0]["stratum_kind"] == "era" else "year"
        total = sum(sum(counts[(expected_scope,w["stratum_id"],g)]["n_matches"] for g in GROUPS) for w in weights)
        check("reference_total:"+rid, all(w["n_reference_total"] == total for w in weights))
        for w in weights:
            n = sum(counts[(expected_scope,w["stratum_id"],g)]["n_matches"] for g in GROUPS)
            check("reference_count:"+rid+w["stratum_id"], n == w["n_reference_matches"])
            near("reference_weight:"+rid+w["stratum_id"], w["weight"], n/total if total else None)
        if total:
            check("reference_normalized:"+rid, all(w["weight"] >= 0 for w in weights) and abs(fsum(w["weight"] for w in weights)-1) < 1e-12)
    result_by_id = {r["estimate_id"]: r for r in tables["type_estimates"]}
    result_by_id.update({r["contrast_id"]: r for r in tables["type_differences"]})
    check("target_definition_keys", len(definitions) == len({d["target_id"] for d in definitions}) and {d["target_id"] for d in definitions} == set(result_by_id))
    for d in definitions:
        target = result_by_id[d["target_id"]]
        weights = refs[d["reference_id"]] if d["reference_id"] else None
        values = []
        missing = False
        for term in d["terms"]:
            g, multiplier = term["tournament_group"], term["multiplier"]
            strata = weights if weights is not None else [dict(stratum_id=d["period_id"], weight=1.0)]
            cscope = weights[0]["stratum_kind"] if weights is not None else d["scope"]
            for w in strata:
                if w["weight"] is None:
                    missing = True; continue
                if w["weight"] == 0:
                    continue
                support = [r for r in sets[(cscope, w["stratum_id"])] if r["tournament_group"] == g]
                if not support:
                    missing = True; continue
                coefficient = multiplier*w["weight"]/len(support)
                values.append(fsum(coefficient*r["home_win"] for r in support))
        near("coefficient_reconstruction:"+d["target_id"], target["estimate"], None if missing else fsum(values))
        check("result_status:"+d["target_id"], (target["status"] == "ok") == (target["estimate"] is not None))
        check("no_inference:"+d["target_id"], target["uncertainty_status"] == "not_run" and all(target[k] is None for k in ("standard_error", "ci_lower", "ci_upper", "confidence_level")) and target["method_id"] == target["method_version"] == "")
    for row in tables["type_differences"]:
        prefix = f"rate:{row['scope']}:{row['period_id']}:{row['estimand']}:"
        f, n = (result_by_id[prefix+g] for g in GROUPS)
        near("rate_difference:"+row["contrast_id"], row["estimate"], None if f["estimate"] is None or n["estimate"] is None else 100*(f["estimate"]-n["estimate"]))
        check("difference_unit:"+row["contrast_id"], row["unit"] == "percentage_points")
        if row["reference_id"] and row["estimate"] is not None:
            weights = refs[row["reference_id"]]
            cscope = weights[0]["stratum_kind"]
            value = 100*fsum(w["weight"]*(counts[(cscope,w["stratum_id"],"friendly")]["home_win_rate"]-counts[(cscope,w["stratum_id"],"non_friendly")]["home_win_rate"]) for w in weights if w["weight"] > 0)
            near("weighted_cell_difference:"+row["contrast_id"], row["estimate"], value)
    for row in tables["type_estimates"]:
        check("rate_range:"+row["estimate_id"], row["unit"] == "probability" and (row["estimate"] is None or 0 <= row["estimate"] <= 1))
    return dict(passed=True, checks=checks, n_checks=len(checks), inference="not_run")
