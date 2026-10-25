"""Common time references and explicit definitions of every reported target."""
from math import fsum

from .data import GROUPS

UNCERTAINTY = dict(standard_error=None, ci_lower=None, ci_upper=None, confidence_level=None,
                   method_id="", method_version="", uncertainty_status="not_run")


def reference(scope, period, cells, strata, stratum_kind):
    total = sum(cells[(s, g)]["n_matches"] for s in strata for g in GROUPS)
    rid = f"{scope}:{period}:{stratum_kind}:pooled_matches"
    return [dict(reference_id=rid, scope=scope, period_id=period, stratum_kind=stratum_kind, stratum_id=s,
                 n_reference_matches=(n := sum(cells[(s, g)]["n_matches"] for g in GROUPS)), n_reference_total=total,
                 weight=n / total if total else None, status="empty_reference" if not total else "zero_weight" if not n else "ok") for s in strata]


def standardized(cells, weights, group):
    if not weights or weights[0]["n_reference_total"] == 0:
        return None, "empty_reference", [r["stratum_id"] for r in weights]
    missing = [w["stratum_id"] for w in weights if w["weight"] > 0 and cells[(w["stratum_id"], group)]["n_matches"] == 0]
    if missing:
        return None, "missing_stratum", missing
    return fsum(w["weight"] * cells[(w["stratum_id"], group)]["home_win_rate"] for w in weights if w["weight"] > 0), "ok", []


def targets(scope, period, counts, sid, weights=None, cells=None):
    estimand = "raw" if weights is None else "era_standardized" if scope == "overall" else "year_standardized"
    rid = "" if weights is None else weights[0]["reference_id"]
    estimates, definitions = [], []
    for g in GROUPS:
        value, status, missing = ((counts[g]["home_win_rate"], counts[g]["status"], []) if weights is None else standardized(cells, weights, g))
        eid = f"rate:{scope}:{period}:{estimand}:{g}"
        estimates.append(dict(estimate_id=eid, sample_id=sid, scope=scope, period_id=period, tournament_group=g,
                              estimand=estimand, reference_id=rid, n_matches=counts[g]["n_matches"], estimate=value,
                              unit="probability", **UNCERTAINTY, status=status))
        definitions.append(dict(target_id=eid, scope=scope, period_id=period, estimand=estimand, reference_id=rid,
                                unit="probability", formula="sum(weight * wins / count)" if weights is not None else "wins / count",
                                terms=[dict(tournament_group=g, multiplier=1)], missing_strata={g: missing},
                                denominator_source="rolling_counts.csv" if scope == "rolling" and weights is None else "grouped_counts.csv"))
    f, n = estimates
    available = f["estimate"] is not None and n["estimate"] is not None
    cid = f"difference:{scope}:{period}:{estimand}"
    status = "ok" if available else "empty_reference" if "empty_reference" in (f["status"], n["status"]) else "missing_stratum" if weights is not None else "not_estimable"
    difference = dict(contrast_id=cid, sample_id=sid, scope=scope, period_id=period, estimand=estimand, reference_id=rid,
                      n_friendly=counts["friendly"]["n_matches"], n_non_friendly=counts["non_friendly"]["n_matches"],
                      estimate=100 * (f["estimate"] - n["estimate"]) if available else None, unit="percentage_points",
                      **UNCERTAINTY, status=status)
    definitions.append(dict(target_id=cid, scope=scope, period_id=period, estimand=estimand, reference_id=rid,
                            unit="percentage_points", formula="100 * (friendly_rate - non_friendly_rate)",
                            terms=[dict(tournament_group="friendly", multiplier=100), dict(tournament_group="non_friendly", multiplier=-100)],
                            missing_strata={d["terms"][0]["tournament_group"]: d["missing_strata"][d["terms"][0]["tournament_group"]] for d in definitions},
                            denominator_source="rolling_counts.csv" if scope == "rolling" and weights is None else "grouped_counts.csv"))
    return estimates, [difference], definitions


def build_main(counts, analysis, sid):
    by = {(r["scope"], r["period_id"], r["tournament_group"]): r for r in counts}
    cells = {(e["id"], g): by[("era", e["id"], g)] for e in analysis["eras"] for g in GROUPS}
    weights = reference("overall", "all", cells, [e["id"] for e in analysis["eras"]], "era")
    rates, differences, definitions = [], [], []
    requests = [("overall", "all", None)] + [("era", e["id"], None) for e in analysis["eras"]] + [("overall", "all", weights)]
    for scope, period, ref in requests:
        e, d, t = targets(scope, period, {g: by[(scope, period, g)] for g in GROUPS}, sid, ref, cells)
        rates += e; differences += d; definitions += t
    return dict(reference_weights=weights, type_estimates=rates, type_differences=differences), definitions
