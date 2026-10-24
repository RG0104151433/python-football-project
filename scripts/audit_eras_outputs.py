"""Independently audit saved era outputs using only stdlib and the clean input.

Does not import analysis functions or edit input/results. Run from repository root.
"""
import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

COUNT_FIELDS = "n_matches n_home_wins n_draws n_away_wins home_win_rate draw_rate away_win_rate mean_goal_difference status"
CI_FIELDS = "standard_error ci_lower ci_upper confidence_level method_id method_version uncertainty_status status"
EXPECTED = {
    "analysis_membership": "data_version match_id source_record_id date analysis_era_id in_base_venue in_classified_venue primary_exclusion_reason exclusion_reasons",
    "sample_flow": "flow_id stage parent_stage reason n_records basis status",
    "era_summary": "sample_id sample_name period_id start_date end_date n_years " + COUNT_FIELDS,
    "year_summary": "sample_id sample_name period_id start_date end_date n_years " + COUNT_FIELDS,
    "era_tournament_summary": "sample_id analysis_era_id tournament_group " + COUNT_FIELDS,
    "team_schedule": "sample_id analysis_era_id tournament_group team_id n_home n_away n_matches n_distinct_opponents",
    "schedule_diagnostics": "sample_id analysis_era_id tournament_group metric value unit status",
    "reference_weights": "reference_id reference_sample_id scheme tournament_group weight reference_start reference_end n_reference_matches n_reference_years reference_years missing_years status",
    "era_estimates": "estimate_id sample_id analysis_era_id estimand reference_id estimate unit " + CI_FIELDS,
    "era_contrasts": "contrast_id sample_id earlier_era later_era estimand reference_id estimate unit " + CI_FIELDS,
    "weight_sensitivity": "contrast_id sample_id weight_friendly difference_pp flip_weight status",
    "sensitivity_results": "variant_id check_type parent_sample_id sample_id reference_id contrast_id n_matches estimate_pp baseline_estimate_pp change_from_baseline_pp status reason",
}
KEYS = {
    "analysis_membership": "match_id", "sample_flow": "flow_id stage reason",
    "era_summary": "sample_name period_id", "year_summary": "sample_name period_id",
    "era_tournament_summary": "sample_id analysis_era_id tournament_group",
    "team_schedule": "sample_id analysis_era_id tournament_group team_id",
    "schedule_diagnostics": "sample_id analysis_era_id tournament_group metric",
    "reference_weights": "reference_id tournament_group", "era_estimates": "estimate_id",
    "era_contrasts": "contrast_id reference_id estimand", "weight_sensitivity": "contrast_id weight_friendly",
    "sensitivity_results": "variant_id contrast_id",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, strict=True))


def audit(root, manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config = manifest["config"]
    table_dir = root / "outputs/tables/eras" / manifest["analysis_id"]
    results = []
    def check(name, condition):
        results.append({"check": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)
    def close(a, b):
        return a == "" if b is None else a != "" and math.isclose(float(a), b, abs_tol=1e-9, rel_tol=0)
    check("completed_run_without_inference", manifest["status"] == "completed" and manifest["stages"]["inference"] == "not_run")
    for kind in ("inputs", "outputs", "code_hashes"):
        check(f"{kind}_hashes", all((root / name).is_file() and sha(root / name) == value for name, value in manifest[kind].items()))
    tables = {}
    for name, fields in EXPECTED.items():
        path = table_dir / f"{name}.csv"
        payload = path.read_bytes()
        check(f"{name}:BOM_LF", payload.startswith(b"\xef\xbb\xbf") and b"\r" not in payload)
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            check(f"{name}:fields", reader.fieldnames == fields.split())
            rows = list(reader)
        keys = [tuple(float(r[f]) if f == "weight_friendly" else r[f] for f in KEYS[name].split()) for r in rows]
        check(f"{name}:unique_sorted_keys", len(keys) == len(set(keys)) and keys == sorted(keys))
        for row in rows:
            check_name = f"{name}:types_and_serialization"
            valid = None not in row and all(v is not None for v in row.values())
            for field, value in row.items():
                if field.startswith("n_"):
                    valid &= bool(re.fullmatch(r"[0-9]+", value))
                elif field.startswith("in_"):
                    valid &= value in {"true", "false"}
                elif field in {"exclusion_reasons", "reference_years", "missing_years"}:
                    valid &= isinstance(json.loads(value), list)
                elif field in {"estimate", "standard_error", "ci_lower", "ci_upper", "confidence_level", "weight", "weight_friendly", "flip_weight", "mean_goal_difference"} or field.endswith(("_rate", "_pp")):
                    valid &= value == "" or bool(re.fullmatch(r"-?[0-9]+\.[0-9]{10}", value)) and math.isfinite(float(value))
                elif field == "value":
                    valid &= value == "" or math.isfinite(float(value))
            if not valid:
                check(check_name, False)
        check(f"{name}:types_and_serialization", True)
        tables[name] = rows
    clean = read(root / f"data/processed/{manifest['data_version']}/matches_clean.csv")
    base = [r for r in clean if config["analysis_start"] <= r["date"] <= config["analysis_end"] and
            r["eligible_venue_analysis"] == "true" and r["is_neutral"] == "false"]
    classified = [r for r in base if r["eligible_tournament_analysis"] == "true" and r["tournament_group"] in {"friendly", "non_friendly"}]
    datasets = {"base_venue": base, "classified_venue": classified}
    membership = tables["analysis_membership"]
    check("membership_covers_clean_once", {r["match_id"] for r in membership} == {r["match_id"] for r in clean} and len(membership) == len(clean))
    for sample, selected in datasets.items():
        field = "in_" + sample
        check(f"{sample}:selected_match_ids", {r["match_id"] for r in membership if r[field] == "true"} == {r["match_id"] for r in selected})
    def in_era(rows, eid):
        era = next(e for e in config["eras"] if e["id"] == eid)
        return [r for r in rows if era["start"] <= r["date"] <= era["end"]]
    def rate(rows):
        return sum(int(r["home_score"]) > int(r["away_score"]) for r in rows) / len(rows) if rows else None
    def summary_ok(result, selected):
        n = len(selected)
        wins = sum(int(r["home_score"]) > int(r["away_score"]) for r in selected)
        draws = sum(int(r["home_score"]) == int(r["away_score"]) for r in selected)
        away = n - wins - draws
        return int(result["n_matches"]) == n and int(result["n_home_wins"]) == wins and int(result["n_draws"]) == draws and int(result["n_away_wins"]) == away and close(result["home_win_rate"], rate(selected)) and close(result["draw_rate"], draws / n if n else None) and close(result["away_win_rate"], away / n if n else None) and close(result["mean_goal_difference"], sum(int(r["home_score"]) - int(r["away_score"]) for r in selected) / n if n else None)
    for table in ("era_summary", "year_summary"):
        check(f"{table}:independent_score_recount", all(summary_ok(r, [m for m in datasets[r["sample_name"]] if r["start_date"] <= m["date"] <= r["end_date"]]) for r in tables[table]))
    check("era_tournament_summary:independent_score_recount", all(summary_ok(r, [m for m in in_era(classified, r["analysis_era_id"]) if m["tournament_group"] == r["tournament_group"]]) for r in tables["era_tournament_summary"]))
    years = sorted({r["date"][:4] for r in classified})
    weights = {"pooled_matches": sum(r["tournament_group"] == "friendly" for r in classified) / len(classified),
               "equal_years": sum(sum(r["tournament_group"] == "friendly" for r in classified if r["date"].startswith(y)) / sum(r["date"].startswith(y) for r in classified) for y in years) / len(years)}
    references = {}
    for row in tables["reference_weights"]:
        weight = weights[row["scheme"]]
        check(f"reference:{row['scheme']}:{row['tournament_group']}", close(row["weight"], weight if row["tournament_group"] == "friendly" else 1 - weight))
        references[row["reference_id"]] = weight
    def standardized(rows, eid, weight):
        cells = in_era(rows, eid)
        f = rate([r for r in cells if r["tournament_group"] == "friendly"])
        n = rate([r for r in cells if r["tournament_group"] == "non_friendly"])
        return None if (weight > 0 and f is None) or (weight < 1 and n is None) else weight * (f or 0) + (1 - weight) * (n or 0)
    check("era_estimates:independent_standardization", all(close(r["estimate"], rate(in_era(classified, r["analysis_era_id"])) if r["estimand"] == "observed_rate" else standardized(classified, r["analysis_era_id"], references[r["reference_id"]])) and r["unit"] == "probability" for r in tables["era_estimates"]))
    for row in tables["era_contrasts"]:
        weight = references[row["reference_id"]]
        a, b = row["earlier_era"], row["later_era"]
        raw = 100 * (rate(in_era(classified, b)) - rate(in_era(classified, a)))
        std = 100 * (standardized(classified, b, weight) - standardized(classified, a, weight))
        expected = {"observed_difference": raw, "standardized_difference": std, "composition_adjustment_difference": raw - std}[row["estimand"]]
        check(f"contrast:{row['contrast_id']}:{row['reference_id']}:{row['estimand']}", close(row["estimate"], expected) and row["unit"] == "percentage_points")
    check("no_false_precision_from_intervals", all(r["uncertainty_status"] == "not_run" and all(r[k] == "" for k in ("standard_error", "ci_lower", "ci_upper", "method_id", "method_version", "confidence_level")) for name in ("era_estimates", "era_contrasts") for r in tables[name]))
    for contrast in config["primary_contrasts"]:
        diffs = {g: 100 * (rate([r for r in in_era(classified, contrast["later"]) if r["tournament_group"] == g]) - rate([r for r in in_era(classified, contrast["earlier"]) if r["tournament_group"] == g])) for g in ("friendly", "non_friendly")}
        df, dn = diffs["friendly"], diffs["non_friendly"]
        flip = dn / (dn - df) if df != dn else None
        check(f"weight_curve:{contrast['id']}", all(close(r["difference_pp"], float(r["weight_friendly"]) * df + (1 - float(r["weight_friendly"])) * dn) and close(r["flip_weight"], flip if flip is not None and 0 <= flip <= 1 else None) for r in tables["weight_sensitivity"] if r["contrast_id"] == contrast["id"]))
    common = set.intersection(*({m[k] for m in in_era(classified, era["id"]) for k in ("home_team_id", "away_team_id")} for era in config["eras"]))
    for row in tables["sensitivity_results"]:
        selected = classified
        if row["check_type"] == "leave_one_year_out":
            year = row["variant_id"].removeprefix("without_year_")
            selected = [r for r in selected if not r["date"].startswith(year)]
        elif row["check_type"] == "common_teams":
            selected = [r for r in selected if r["home_team_id"] in common and r["away_team_id"] in common]
        contrast = next(c for c in config["primary_contrasts"] if c["id"] == row["contrast_id"])
        a, b = (standardized(selected, contrast[key], references[row["reference_id"]]) for key in ("earlier", "later"))
        expected = None if a is None or b is None else 100 * (b - a)
        check(f"sensitivity:{row['variant_id']}:{row['contrast_id']}", int(row["n_matches"]) == len(selected) and close(row["estimate_pp"], expected))
    upstream = [r for r in tables["sample_flow"] if r["basis"] == "upstream_raw"]
    states = Counter()
    for row in upstream:
        states[row["stage"]] += int(row["n_records"])
    check("upstream_flow_counts", dict(states) == {"included": 48102, "outside_window": 1803, "quarantined": 40})
    return {"schema_version": "eras-closeout-audit-v1", "audited_at_utc": datetime.now(timezone.utc).isoformat(),
            "analysis_id": manifest["analysis_id"], "run_manifest": manifest_path.relative_to(root).as_posix(),
            "audit_script_sha256": sha(Path(__file__)), "passed": True, "checks": results,
            "table_rows": {name: len(rows) for name, rows in tables.items()},
            "counts": {"processed": len(clean), "base": len(base), "classified": len(classified)},
            "reference_weights": weights, "inference": "not_run", "human_review": "pending",
            "scope": "Current configured full analysis only; independent saved-output audit, not a general estimator or facts review."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="outputs/logs/eras/eras-20261024T013933600718Z-425e4920/run_manifest.json")
    parser.add_argument("--output", default="outputs/logs/eras/closeout-20261024/output_audit.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = (root / args.output).resolve()
    source = (root / args.manifest).resolve()
    if not target.is_relative_to(root) or not source.is_relative_to(root) or target == source:
        parser.error("Paths must stay inside the repository and output must differ from input")
    result = audit(root, source)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": result["passed"], "checks": len(result["checks"]), "analysis_id": result["analysis_id"], "report": target.relative_to(root).as_posix()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
