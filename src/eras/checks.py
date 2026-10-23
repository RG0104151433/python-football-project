"""Numerical invariants and predeclared point-estimate sensitivity checks."""
from collections import Counter
from math import isclose, isfinite

from ..data_contract import PrepError
from .data import era_for, sample_id
from .standardize import contrasts_for, era_rates
from .statistics import team_set


def run_sensitivity(rows, config, references):
    if not references:
        return []
    primary = references[0]
    weight = primary["weight_friendly"]
    baseline = {r["contrast_id"]: r["estimate"] for r in contrasts_for(era_rates(rows, config, weight), config)
                if r["estimand"] == "standardized_difference"}
    parent = sample_id(rows, config["data_version"])
    variants = []
    if config["sensitivity"]["leave_one_year_out"]:
        for year in sorted({r["year"] for r in rows}):
            affected = {era_for(r["date"], config) for r in rows if r["year"] == year} - {""}
            variants.append((f"without_year_{year}", "leave_one_year_out", [r for r in rows if r["year"] != year], primary, affected))
    if config["sensitivity"]["common_teams"]:
        populations = [team_set([r for r in rows if era_for(r["date"], config) == e["id"]]) for e in config["eras"]]
        common = set.intersection(*populations)
        variants.append(("common_teams", "common_teams", [r for r in rows if r["home_team_id"] in common and r["away_team_id"] in common], primary, None))
    for ref in references[1:]:
        variants.append((f"reference_{ref['scheme']}", "alternative_reference", rows, ref, None))
    results = []
    contrast_config = {c["id"]: c for c in config["primary_contrasts"]}
    for vid, kind, selected, ref, affected in variants:
        rates = era_rates(selected, config, ref["weight_friendly"])
        for result in contrasts_for(rates, config):
            if result["estimand"] != "standardized_difference":
                continue
            contrast = contrast_config[result["contrast_id"]]
            if affected is not None and not affected.intersection({contrast["earlier"], contrast["later"]}):
                continue
            base, estimate = baseline[result["contrast_id"]], result["estimate"]
            results.append(dict(variant_id=vid, check_type=kind, parent_sample_id=parent,
                sample_id=sample_id(selected, config["data_version"]), reference_id=ref["reference_id"],
                contrast_id=result["contrast_id"], n_matches=len(selected), estimate_pp=estimate,
                baseline_estimate_pp=base, change_from_baseline_pp=None if base is None or estimate is None else estimate - base,
                status=result["status"], reason="fixed_reference; both teams required for common_teams"))
    return results


def validate_tables(tables, samples, membership, config):
    checks = {}
    checks["membership_unique"] = len({r["match_id"] for r in membership}) == len(membership)
    base = {r["match_id"] for r in samples["base_venue"]}
    classified = {r["match_id"] for r in samples["classified_venue"]}
    checks["nested_samples"] = classified <= base
    checks["membership_counts"] = (sum(r["in_base_venue"] for r in membership) == len(base) and
                                    sum(r["in_classified_venue"] for r in membership) == len(classified))
    checks["non_neutral_only"] = all(r["is_neutral"] is False for r in samples["base_venue"])
    checks["finite_numbers"] = all(isfinite(value) for rows in tables.values() for row in rows
                                    for value in row.values() if isinstance(value, float))
    summaries = [r for name in ("era_summary", "year_summary", "era_tournament_summary") for r in tables.get(name, [])]
    checks["outcome_counts"] = all(r["n_matches"] == r["n_home_wins"] + r["n_draws"] + r["n_away_wins"] for r in summaries)
    checks["outcome_rates"] = all(
        (r["home_win_rate"] is None and r["draw_rate"] is None and r["away_win_rate"] is None) if not r["n_matches"] else
        (all(0 <= r[f] <= 1 for f in ("home_win_rate", "draw_rate", "away_win_rate")) and
         isclose(r["home_win_rate"] + r["draw_rate"] + r["away_win_rate"], 1, abs_tol=1e-12)) for r in summaries)
    if "era_summary" in tables:
        checks["era_totals"] = all(sum(r["n_matches"] for r in tables["era_summary"] if r["sample_name"] == name) == len(rows)
                                   for name, rows in samples.items())
    if "reference_weights" in tables:
        by_reference = {}
        for row in tables["reference_weights"]:
            by_reference.setdefault(row["reference_id"], []).append(row)
        checks["reference_weights_sum"] = all(
            all(r["weight"] is None for r in rows) or
            (all(r["weight"] is not None and 0 <= r["weight"] <= 1 for r in rows) and isclose(sum(r["weight"] for r in rows), 1, abs_tol=1e-12))
            for rows in by_reference.values())
        direct = {r["period_id"]: r["home_win_rate"] for r in tables["era_summary"] if r["sample_name"] == "classified_venue"}
        checks["same_sample_observed_rate"] = all(
            (r["estimate"] is None and direct[r["analysis_era_id"]] is None) or
            (r["estimate"] is not None and direct[r["analysis_era_id"]] is not None and
             isclose(r["estimate"], direct[r["analysis_era_id"]], abs_tol=1e-12))
            for r in tables["era_estimates"] if r["estimand"] == "observed_rate")
        cells = {(r["analysis_era_id"], r["tournament_group"]): r for r in tables["era_tournament_summary"]}
        checks["strata_counts"] = all(sum(cells[(e["id"], g)]["n_matches"] for g in ("friendly", "non_friendly")) ==
            sum(era_for(r["date"], config) == e["id"] for r in samples["classified_venue"]) for e in config["eras"])
        composition_ok = True
        for estimate in tables["era_estimates"]:
            if estimate["estimand"] != "standardized_rate" or estimate["estimate"] is None:
                continue
            components = by_reference[estimate["reference_id"]]
            expected = sum(w["weight"] * cells[(estimate["analysis_era_id"], w["tournament_group"])]["home_win_rate"]
                           for w in components if w["weight"] > 0)
            composition_ok &= isclose(estimate["estimate"], expected, abs_tol=1e-12)
        checks["standardization_formula"] = composition_ok
    # No table produced by this implementation may claim an inferential result.
    checks["no_unapproved_intervals"] = all(r.get("uncertainty_status", "not_run") == "not_run" and
        all(r.get(k) is None for k in ("standard_error", "ci_lower", "ci_upper"))
        for name in ("era_estimates", "era_contrasts") for r in tables.get(name, []))
    if not all(checks.values()):
        raise PrepError("ANALYSIS_CHECK_FAILED", str({k: v for k, v in checks.items() if not v}))
    return {"passed": True, "checks": checks}


def collect_issues(manifest, config, tables):
    issues = []
    if manifest.get("human_review_pending") or not manifest.get("frozen"):
        issues.append(("warning", "HUMAN_REVIEW_PENDING", "Input is not frozen; outputs are preliminary"))
    if config["protocol_status"] == "draft":
        issues.append(("warning", "EXPLORATORY_PROTOCOL", "Draft protocol: descriptive exploration, no confirmatory tests"))
    issues.append(("warning", "INFERENCE_NOT_RUN", "No confidence intervals or significance tests were computed"))
    missing = Counter((name, row.get("status")) for name, rows in tables.items() for row in rows
                      if row.get("status") in {"empty_group", "missing_stratum", "empty_reference", "not_estimable"})
    for (name, status), count in sorted(missing.items()):
        issues.append(("review", "NOT_ESTIMABLE", f"{name}: {count} rows have status={status}"))
    return issues
