"""Independently recount a provisional Q1 run without changing its outputs."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_team_identity import verify_identity
from src.eras.reporting import FIELDS, KEYS, verify_run


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def audit(root, run_path, compare_path, config_path="config/confirmed_eras_v2.json"):
    manifest = json.loads((root / run_path).read_text(encoding="utf-8"))
    previous = json.loads((root / compare_path).read_text(encoding="utf-8"))
    verified = verify_run(root, run_path)
    verify_run(root, compare_path)
    cfg = json.loads((root / config_path).read_text(encoding="utf-8"))
    if cfg["identity_manifest"] not in manifest["inputs"] or cfg["analysis_config"] not in manifest["inputs"]:
        raise ValueError("Run does not bind the current configured identity and analysis inputs")
    identity_check = verify_identity(root, cfg["identity_manifest"])
    config = json.loads((root / cfg["analysis_config"]).read_text(encoding="utf-8"))
    identity = json.loads((root / cfg["identity_manifest"]).read_text(encoding="utf-8"))
    _, clean = read_csv(root / "data/processed" / config["data_version"] / "matches_clean.csv")
    _, overlay = read_csv(root / next(p for p in identity["outputs"] if p.endswith("/match_identity.csv")))
    by_id = {r["match_id"]: r for r in overlay}
    checks = []

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})
        if not passed:
            raise ValueError("Independent audit failed: " + name)

    def close(name, actual, expected):
        check(name, abs(float(actual) - float(expected)) <= 1e-9)

    check("complete_unique_overlay", len(by_id) == len(overlay) == len(clean)
          and set(by_id) == {r["match_id"] for r in clean})
    check("same_analysis_identity", manifest["analysis_id"] == previous["analysis_id"])
    core = {p: h for p, h in manifest["outputs"].items() if p.startswith(("outputs/tables/", "outputs/figures/"))}
    prior_core = {p: h for p, h in previous["outputs"].items() if p.startswith(("outputs/tables/", "outputs/figures/"))}
    check("all_core_artifact_hashes_identical", core == prior_core)
    table_dir = root / "outputs/tables/eras" / manifest["analysis_id"]
    tables = {}
    for path in sorted(table_dir.glob("*.csv")):
        fields, rows = read_csv(path)
        raw = path.read_bytes()
        check(path.stem + "_encoding", raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw)
        if path.stem in FIELDS:
            check(path.stem + "_fields", fields == FIELDS[path.stem].split())
            keys = [tuple(row[f] for f in KEYS[path.stem].split()) for row in rows]
            check(path.stem + "_unique_sorted_keys", len(set(keys)) == len(keys) and keys == sorted(keys))
        else:
            check("before_after_fields", fields == ["era", "old_n", "new_n", "removed_n",
                  "old_home_win_rate", "new_home_win_rate", "raw_change_pp",
                  "old_standardized_rate", "new_standardized_rate"])
            check("before_after_unique_eras", len(rows) == len({r["era"] for r in rows}))
        tables[path.stem] = rows

    baseline, selected, base_selected = [], [], []
    for row in clean:
        base = (config["analysis_start"] <= row["date"] <= config["analysis_end"]
                and row["eligible_venue_analysis"] == "true" and row["is_neutral"] == "false")
        classified = base and row["eligible_tournament_analysis"] == "true" and row["tournament_group"] in {"friendly", "non_friendly"}
        allowed = by_id[row["match_id"]]["eligible_under_provisional_policy"] == "true"
        if classified:
            baseline.append(row)
        if base and allowed:
            base_selected.append(row)
        if classified and allowed:
            selected.append(row)
    check("summary_sample_counts", len(baseline) == manifest["summary"]["baseline_matches"]
          and len(selected) == manifest["summary"]["new_matches"])
    for name, rows in [("base_venue", base_selected), ("classified_venue", selected)]:
        actual = {r["match_id"] for r in rows}
        reported = {r["match_id"] for r in tables["analysis_membership"] if r["in_" + name] == "true"}
        check(name + "_exact_member_set", actual == reported)

    def recount(label, reported, rows):
        n = len(rows)
        wins = sum(int(r["home_score"]) > int(r["away_score"]) for r in rows)
        draws = sum(int(r["home_score"]) == int(r["away_score"]) for r in rows)
        losses = n - wins - draws
        check(label + "_counts", (n, wins, draws, losses) == tuple(int(reported[k]) for k in
              ("n_matches", "n_home_wins", "n_draws", "n_away_wins")))
        for field, count in [("home_win_rate", wins), ("draw_rate", draws), ("away_win_rate", losses)]:
            close(label + "_" + field, reported[field], count / n)
        close(label + "_mean_goal_difference", reported["mean_goal_difference"],
              sum(int(r["home_score"]) - int(r["away_score"]) for r in rows) / n)

    era_rows = {e["id"]: [r for r in selected if e["start"] <= r["date"] <= e["end"]] for e in config["eras"]}
    for r in tables["era_summary"]:
        group = base_selected if r["sample_name"] == "base_venue" else selected
        recount("era_" + r["sample_name"] + r["period_id"], r,
                [x for x in group if r["start_date"] <= x["date"] <= r["end_date"]])
    for r in tables["year_summary"]:
        group = base_selected if r["sample_name"] == "base_venue" else selected
        recount("year_" + r["sample_name"] + r["period_id"], r,
                [x for x in group if r["start_date"] <= x["date"] <= r["end_date"]])
    subgroup_rates = {}
    for r in tables["era_tournament_summary"]:
        group = [x for x in era_rows[r["analysis_era_id"]] if x["tournament_group"] == r["tournament_group"]]
        recount("type_" + r["analysis_era_id"] + r["tournament_group"], r, group)
        subgroup_rates[(r["analysis_era_id"], r["tournament_group"])] = sum(int(x["home_score"]) > int(x["away_score"]) for x in group) / len(group)
    years = sorted({r["date"][:4] for r in selected})
    year_rows = {y: [r for r in selected if r["date"].startswith(y)] for y in years}
    weights = {}
    for r in tables["reference_weights"]:
        g = r["tournament_group"]
        if r["scheme"] == "pooled_matches":
            value = sum(x["tournament_group"] == g for x in selected) / len(selected)
        else:
            value = sum(sum(x["tournament_group"] == g for x in group) / len(group) for group in year_rows.values()) / len(years)
        close("reference_" + r["reference_id"] + g, r["weight"], value)
        weights[(r["reference_id"], g)] = value
    estimates = {}
    for r in tables["era_estimates"]:
        era = r["analysis_era_id"]
        value = (sum(int(x["home_score"]) > int(x["away_score"]) for x in era_rows[era]) / len(era_rows[era])
                 if r["estimand"] == "observed_rate" else sum(weights[(r["reference_id"], g)] * subgroup_rates[(era, g)] for g in ("friendly", "non_friendly")))
        close("estimate_" + r["estimate_id"], r["estimate"], value)
        estimates[(era, r["reference_id"], r["estimand"])] = value
    for r in tables["era_contrasts"]:
        def difference(estimand):
            return 100 * (estimates[(r["later_era"], r["reference_id"], estimand)] - estimates[(r["earlier_era"], r["reference_id"], estimand)])
        observed, adjusted = difference("observed_rate"), difference("standardized_rate")
        value = {"observed_difference": observed, "standardized_difference": adjusted,
                 "composition_adjustment_difference": observed - adjusted}[r["estimand"]]
        close("contrast_" + r["contrast_id"] + r["reference_id"] + r["estimand"], r["estimate"], value)
    for name in ("era_estimates", "era_contrasts"):
        check(name + "_no_unimplemented_inference", all(r["uncertainty_status"] == "not_run"
              and all(r[k] == "" for k in ("standard_error", "ci_lower", "ci_upper", "confidence_level")) for r in tables[name]))

    report = dict(passed=True, created_at_utc=datetime.now(timezone.utc).isoformat(),
                  analysis_id=manifest["analysis_id"], identity_version=identity["identity_version"],
                  run_manifest=run_path, comparison_run=compare_path, verification=verified,
                  identity_verification=identity_check, core_artifacts_identical=len(core),
                  baseline_matches=len(baseline), selected_matches=len(selected), checks=checks,
                  checked_tables={name: len(rows) for name, rows in tables.items()},
                  audit_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  inference="not_run", full_history_verified=False)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--compare", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", default="config/confirmed_eras_v2.json")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("Output must be inside repository")
    if output.exists():
        raise FileExistsError("Choose a new output file to preserve audit history")
    report = audit(ROOT, args.run, args.compare, args.config)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"passed": True, "checks": len(report["checks"]),
                      "core_artifacts_identical": report["core_artifacts_identical"], "output": args.output}))


if __name__ == "__main__":
    main()
