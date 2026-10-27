"""Inventory empty and thin Q3 strata; this is not an uncertainty estimator."""
import argparse
from collections import Counter
import csv
import io
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from src.regions.export import scalar, verify_run
from src.regions.io import json_bytes, project_path, read_json, read_rows, require, sha


def inventory(summaries, strata, references, matchups):
    reference = {(r["target_id"], r["era"], r["tournament_group"]): r for r in references}
    layers = {}
    for r in strata:
        layers.setdefault((r["target_id"], r["group_id"]), []).append(r)
    levels = {(r["target_id"], r["group_id"]): r["level"] for r in matchups}
    result = []
    for group in summaries:
        key = group["target_id"], group["group_id"]
        active = [(r, float(reference[r["target_id"], r["era"], r["tournament_group"]]["weight"]))
                  for r in layers[key] if float(reference[r["target_id"], r["era"], r["tournament_group"]]["weight"]) > 0]
        missing = [r["era"] + "/" + r["tournament_group"] for r, q in active if int(r["n_matches"]) == 0]
        counts = [int(r["n_matches"]) for r, q in active if int(r["n_matches"]) > 0]
        adjusted = group["standardized_home_win_rate"]
        require((not missing) == (adjusted != ""), "REG_SUPPORT", "Status/coverage mismatch: " + str(key))
        raw = group["home_win_rate"]
        result.append(dict(target_id=key[0], group_id=key[1], label=group["group_label"],
                           level=levels.get(key, "overall_or_relationship"), n_matches=int(group["n_matches"]),
                           positive_reference_layers=len(active), missing_positive_layers=len(missing),
                           missing_layers=";".join(missing), min_observed_positive_layer_n=min(counts) if counts else None,
                           one_match_layers=counts.count(1), two_match_layers=counts.count(2),
                           largest_defined_layer_q_over_n=max((q / int(r["n_matches"]) for r, q in active if int(r["n_matches"])), default=None),
                           raw_home_win_rate=float(raw) if raw != "" else None,
                           adjusted_home_win_rate=float(adjusted) if adjusted != "" else None,
                           adjusted_minus_raw_pp=100 * (float(adjusted) - float(raw)) if adjusted != "" and raw != "" else None,
                           standardization_status=group["standardization_status"]))
    return sorted(result, key=lambda r: (r["target_id"], r["group_id"]))


def run(root, run_path, output):
    integrity = verify_run(root, run_path)
    manifest = read_json(project_path(root, run_path))
    folder = root / "outputs/tables/regions" / manifest["analysis_id"]
    data = {name: read_rows(folder / (name + ".csv")) for name in
            ("group_summary", "stratum_counts", "reference_weights", "matchup_rates", "contrast_results", "analysis_matches")}
    rows = inventory(data["group_summary"], data["stratum_counts"], data["reference_weights"], data["matchup_rates"])
    matrix = [r for r in rows if r["level"] != "overall_or_relationship"]
    coverage = {level: dict(cells=len(part), observed=sum(r["n_matches"] > 0 for r in part),
                           adjusted=sum(r["adjusted_home_win_rate"] is not None for r in part))
                for level in ("macro_to_macro", "within_partition", "outside_macro")
                for part in [[r for r in matrix if r["level"] == level]]}
    require(len(rows) == 188 and len(matrix) == 155 and len(data["contrast_results"]) == 29,
            "REG_SUPPORT", "Unexpected current catalogue")
    report = dict(schema_version="regions-support-audit-v1", decision_log_id="R20261027-03", status="passed",
                  analysis_id=manifest["analysis_id"], source_run=run_path, source_run_sha256=sha(project_path(root, run_path)),
                  source_tables={name: sha(folder / (name + ".csv")) for name in data},
                  code_sha256=sha(Path(__file__)), integrity=integrity, groups=len(rows), coverage=coverage,
                  no_matches=[r for r in matrix if not r["n_matches"]],
                  unestimable_adjusted_contrasts=[r for r in data["contrast_results"] if r["adjusted_status"] != "ok"],
                  largest_adjustment_examples=sorted((r for r in matrix if r["adjusted_minus_raw_pp"] is not None),
                                                    key=lambda r: abs(r["adjusted_minus_raw_pp"]), reverse=True)[:5],
                  known_home_matches=sum(bool(r["home_region"]) for r in data["analysis_matches"]),
                  unknown_home_matches=sum(not r["home_region"] for r in data["analysis_matches"]),
                  unknown_relation_matches=sum(r["relation"] == "unknown" for r in data["analysis_matches"]),
                  sparse_policy="Counts of one/two and minimum stratum n are diagnostics only, not reliability cutoffs; all groups retained",
                  uncertainty="not_run", sensitivity="not_run", causal_interpretation=False)
    output = project_path(root, output)
    require(not output.exists(), "REG_OUTPUT_COLLISION", "Choose an unused support-audit directory")
    output.mkdir(parents=True)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows({k: scalar(v) for k, v in r.items()} for r in rows)
    (output / "support_inventory.csv").write_bytes(buffer.getvalue().encode("utf-8-sig"))
    report["inventory_sha256"] = sha(output / "support_inventory.csv")
    (output / "support_audit.json").write_bytes(json_bytes(report))
    return dict(status="passed", analysis_id=manifest["analysis_id"], groups=len(rows), coverage=coverage,
                report=(output / "support_audit.json").relative_to(root).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        print(json_bytes(run(PROJECT, args.run, args.output)).decode("utf-8"))
        return 0
    except Exception as exc:
        print(json_bytes(dict(status="failed", code=getattr(exc, "code", type(exc).__name__), message=str(exc))).decode("utf-8"))
        return 2


if __name__ == "__main__":
    sys.exit(main())
