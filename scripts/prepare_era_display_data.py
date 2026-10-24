"""Export verified descriptive results for future offline HTML/PPT rendering.

No statistical estimates are recomputed here; all values come from saved tables.
"""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="outputs/logs/eras/eras-20261024T013933600718Z-425e4920/run_manifest.json")
    parser.add_argument("--audit", default="outputs/logs/eras/closeout-20261024/output_audit.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    def inside(relative):
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Paths must stay within repository")
        return path
    manifest_path, audit_path = inside(args.manifest), inside(args.audit)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if manifest["status"] != "completed" or not audit["passed"] or audit["analysis_id"] != manifest["analysis_id"] or audit["run_manifest"] != manifest_path.relative_to(root).as_posix():
        raise ValueError("Audit and completed run do not match")
    if manifest["stages"]["inference"] != "not_run":
        raise ValueError("This export is for the current descriptive protocol only")
    sources = {}
    for name, expected in {**manifest["inputs"], **manifest["outputs"], **manifest["code_hashes"]}.items():
        if sha(inside(name)) != expected:
            raise ValueError(f"Source changed: {name}")
        sources[name] = expected
    folder = root / "outputs/tables/eras" / manifest["analysis_id"]
    summaries = read(folder / "era_summary.csv")
    estimates = read(folder / "era_estimates.csv")
    weights = read(folder / "reference_weights.csv")
    strata = read(folder / "era_tournament_summary.csv")
    primary_ref = next(w["reference_id"] for w in weights if w["scheme"] == manifest["config"]["reference_scheme"])
    series = []
    for era in manifest["config"]["eras"]:
        full = next(r for r in summaries if r["sample_name"] == "base_venue" and r["period_id"] == era["id"])
        classified = next(r for r in summaries if r["sample_name"] == "classified_venue" and r["period_id"] == era["id"])
        adjusted = next(r for r in estimates if r["analysis_era_id"] == era["id"] and r["reference_id"] == primary_ref and r["estimand"] == "standardized_rate")
        cells = {g: next(r for r in strata if r["analysis_era_id"] == era["id"] and r["tournament_group"] == g) for g in ("friendly", "non_friendly")}
        def number(value):
            return float(value) if value else None
        series.append(dict(era_id=era["id"], label=era["label"], start=era["start"], end=era["end"],
                           full_matches=int(full["n_matches"]), classified_matches=int(classified["n_matches"]),
                           home_wins=int(full["n_home_wins"]), observed_full_rate=number(full["home_win_rate"]),
                           observed_classified_rate=number(classified["home_win_rate"]), standardized_rate=number(adjusted["estimate"]),
                           friendly_matches=int(cells["friendly"]["n_matches"]), non_friendly_matches=int(cells["non_friendly"]["n_matches"]),
                           friendly_rate=number(cells["friendly"]["home_win_rate"]), non_friendly_rate=number(cells["non_friendly"]["home_win_rate"])))
    data_manifest = json.loads((root / "data/processed" / manifest["data_version"] / "dataset_manifest.json").read_text(encoding="utf-8"))
    flow = read(folder / "sample_flow.csv")
    exclusion_counts = {r["reason"]: int(r["n_records"]) for r in flow if r["stage"] == "base_excluded"}
    package = dict(schema_version="eras-display-v1", generated_at_utc=datetime.now(timezone.utc).isoformat(),
                   analysis_id=manifest["analysis_id"], data_version=manifest["data_version"], protocol_status=manifest["protocol_status"],
                   source_manifest=args.manifest, source_manifest_sha256=sha(manifest_path),
                   audit_path=args.audit, audit_sha256=sha(audit_path), exporter_sha256=sha(Path(__file__)),
                   units={"rates": "probability", "contrasts": "percentage_points", "counts": "matches"},
                   uncertainty="not_run", human_review="pending", series=series,
                   reference_weights=weights, contrasts=read(folder / "era_contrasts.csv"),
                   sensitivity=read(folder / "sensitivity_results.csv"), weight_sensitivity=read(folder / "weight_sensitivity.csv"),
                   upstream_counts=data_manifest["counts"]["states"], raw_count=data_manifest["counts"]["input"],
                   processed_count=manifest["counts"]["processed_matches"], analysis_exclusions=exclusion_counts,
                   classified_count=manifest["counts"]["classified_venue"], source_hashes=sources,
                   notes=["Not a forecast or causal estimate", "2020–2024 contains five years", "Slider values describe hypothetical reference compositions, not new matches",
                          "Nested source tables retain CSV strings and their declared units; never use JavaScript truthiness for numeric conversion"])
    output = root / "outputs/presentation/eras" / manifest["analysis_id"] / "presentation_data.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"path": output.relative_to(root).as_posix(), "sha256": sha(output), "eras": len(series), "inference": "not_run"}))


if __name__ == "__main__":
    main()
