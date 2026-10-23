"""Stable table contracts, non-interactive figures and failure-safe publishing."""
from __future__ import annotations

import io
import json
from pathlib import Path

from ..data_contract import PrepError, atomic_bytes, csv_bytes, digest, file_hash, project_path, write_json

COUNTS = "n_matches n_home_wins n_draws n_away_wins home_win_rate draw_rate away_win_rate mean_goal_difference status"
UNCERTAINTY = "standard_error ci_lower ci_upper confidence_level method_id method_version uncertainty_status status"
FIELDS = {
    "analysis_membership": "data_version match_id source_record_id date analysis_era_id in_base_venue in_classified_venue primary_exclusion_reason exclusion_reasons",
    "sample_flow": "flow_id stage parent_stage reason n_records basis status",
    "era_summary": "sample_id sample_name period_id start_date end_date n_years " + COUNTS,
    "year_summary": "sample_id sample_name period_id start_date end_date n_years " + COUNTS,
    "era_tournament_summary": "sample_id analysis_era_id tournament_group " + COUNTS,
    "team_schedule": "sample_id analysis_era_id tournament_group team_id n_home n_away n_matches n_distinct_opponents",
    "schedule_diagnostics": "sample_id analysis_era_id tournament_group metric value unit status",
    "reference_weights": "reference_id reference_sample_id scheme tournament_group weight reference_start reference_end n_reference_matches n_reference_years reference_years missing_years status",
    "era_estimates": "estimate_id sample_id analysis_era_id estimand reference_id estimate unit " + UNCERTAINTY,
    "era_contrasts": "contrast_id sample_id earlier_era later_era estimand reference_id estimate unit " + UNCERTAINTY,
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


def sorted_rows(name, rows):
    fields = KEYS[name].split()
    keys = [tuple(row[f] for f in fields) for row in rows]
    if len(set(keys)) != len(keys):
        raise PrepError("OUTPUT_KEY_DUPLICATE", name)
    return sorted(rows, key=lambda row: tuple(row[f] for f in fields))


def field_type(field):
    if field.startswith("n_"):
        return "integer"
    if field.startswith("in_"):
        return "boolean"
    if field in {"exclusion_reasons", "reference_years", "missing_years"}:
        return "JSON array"
    if field in {"estimate", "standard_error", "ci_lower", "ci_upper", "confidence_level", "weight", "value", "weight_friendly", "flip_weight"} or field.endswith(("_rate", "_pp")) or field == "mean_goal_difference":
        return "decimal"
    return "string"


def dictionary(tables):
    lines = ["# Era tables: eras-tables-v1", "", "CSV: UTF-8 BOM, LF, integers, lowercase booleans, decimals fixed to 10 places.",
             "Blank numeric fields mean unavailable/not computed, never zero. Read status and uncertainty_status.",
             "Rates: probability (0–1); contrasts and sensitivity: percentage points. No inferred intervals.",
             "sample_name distinguishes two logical views even when their match sets/sample_id coincide.", ""]
    for name in sorted(tables):
        lines.extend([f"## {name}.csv", "", f"Unique key: {KEYS[name]}. Sort: this same key.", ""])
        for field in FIELDS[name].split():
            unit = "probability" if field.endswith("_rate") or field in {"weight", "weight_friendly", "flip_weight", "confidence_level"} else "goals" if field == "mean_goal_difference" else "percentage_points" if field.endswith("_pp") else "see row unit" if field in {"estimate", "standard_error", "ci_lower", "ci_upper", "value"} else "not applicable"
            meaning = "Blank when not estimated; see status." if field_type(field) == "decimal" else "Required unless no applicable exclusion/period; arrays use JSON."
            lines.append(f"- {field}: {field_type(field)}; unit={unit}. {meaning}")
        lines.append("")
    lines.extend(["## Definitions", "", "pair_coverage: distinct unordered team pairs / [G(G-1)/2] within the era/group.",
                  "top_5_appearance_share: appearances by five most frequent teams / (2 * matches).",
                  "max_pair_repeats: largest count of matches for an unordered team pair.",
                  "sample_flow: upstream raw and downstream processed counts are separate accounting layers.",
                  "reference_years lists observed years; missing_years lists window years without classified matches.",
                  "observed_difference and standardized_difference: later minus earlier, in percentage points.",
                  "composition_adjustment_difference: observed_difference minus standardized_difference; not causal.",
                  "uncertainty_status=not_run: no SE/CI, method fields blank.",
                  "Statuses: ok, empty_group, missing_stratum, empty_reference, not_estimable; sensitivity flip statuses are algebraic only.", ""])
    return "\n".join(lines).encode("utf-8")


def table_artifacts(tables, analysis_id):
    folder = f"outputs/tables/eras/{analysis_id}"
    outputs = {f"{folder}/{name}.csv": csv_bytes(FIELDS[name].split(), sorted_rows(name, rows)) for name, rows in sorted(tables.items())}
    outputs[f"{folder}/data_dictionary.md"] = dictionary(tables)
    return outputs


def figure_artifacts(tables, references, config, analysis_id):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    matplotlib.rcParams["svg.hashsalt"] = "eras-v1"
    outputs = {}
    folder = f"outputs/figures/eras/{analysis_id}"
    labels = [e["label"] for e in config["eras"]]
    era_ids = [e["id"] for e in config["eras"]]

    def save(fig, name):
        fig.text(.02, .01, f"Descriptive; input review status: see manifest. No confidence intervals. {analysis_id}", fontsize=7)
        fig.tight_layout(rect=(0, .055, 1, 1))
        for extension in ("png", "svg"):
            stream = io.BytesIO()
            options = {"metadata": {"Date": None}} if extension == "svg" else {}
            fig.savefig(stream, format=extension, dpi=300, **options)
            outputs[f"{folder}/{name}.{extension}"] = stream.getvalue()
        plt.close(fig)

    def values(estimand):
        rows = [r for r in tables["era_estimates"] if r["reference_id"] == references[0]["reference_id"] and r["estimand"] == estimand]
        lookup = {r["analysis_era_id"]: r["estimate"] for r in rows}
        return [np.nan if lookup[e] is None else lookup[e] * 100 for e in era_ids]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(labels, values("observed_rate"), "o-", label="Observed: classified sample")
    ax.plot(labels, values("standardized_rate"), "o-", label=f"Standardized: fixed {references[0]['scheme']} reference")
    base = {r["period_id"]: r for r in tables["era_summary"] if r["sample_name"] == "base_venue"}
    ax.plot(labels, [np.nan if base[e]["home_win_rate"] is None else 100 * base[e]["home_win_rate"] for e in era_ids], "x--", label="Observed: full venue sample")
    ax.set(ylabel="Home wins (%, zoomed scale)", title="Home performance by era (non-neutral matches)")
    ax.legend(fontsize=8)
    ax.grid(alpha=.2)
    ax.set_xticks(range(len(labels)), [f"{label}\nn(full)={base[eid]['n_matches']}" for label, eid in zip(labels, era_ids)], fontsize=9)
    save(fig, "era_results")

    fig, ax = plt.subplots(figsize=(9, 5))
    proportions = []
    for eid in era_ids:
        cells = [r for r in tables["era_tournament_summary"] if r["analysis_era_id"] == eid]
        total = sum(r["n_matches"] for r in cells)
        proportions.append(100 * next(r["n_matches"] for r in cells if r["tournament_group"] == "friendly") / total if total else np.nan)
    ax.bar(labels, proportions, label="Friendly")
    ax.bar(labels, [100 - p for p in proportions], bottom=proportions, label="Other non-friendly")
    ax.set(ylabel="Share of classified matches (%)", title="Tournament composition", ylim=(0, 100))
    ax.legend(fontsize=8)
    save(fig, "tournament_composition")

    fig, ax = plt.subplots(figsize=(9, 5))
    for contrast in config["primary_contrasts"]:
        records = sorted((r for r in tables["weight_sensitivity"] if r["contrast_id"] == contrast["id"]), key=lambda r: r["weight_friendly"])
        ax.plot([r["weight_friendly"] for r in records], [np.nan if r["difference_pp"] is None else r["difference_pp"] for r in records], label=contrast["id"])
    for reference in references:
        if reference["weight_friendly"] is not None:
            ax.axvline(reference["weight_friendly"], linestyle="--", alpha=.5, label=reference["scheme"])
    ax.axhline(0, color="black", linewidth=.7)
    ax.set(xlabel="Friendly share in common reference", ylabel="Later minus earlier (percentage points)", title="Sensitivity to reference composition")
    if references or config["primary_contrasts"]:
        ax.legend(fontsize=8)
    save(fig, "weight_sensitivity")
    return outputs


def publish_outputs(root, artifacts):
    # Check all destinations before writing any; never overwrite conflicting artifacts.
    for relative, content in artifacts.items():
        path = project_path(root, relative)
        if path.exists() and file_hash(path) != digest(content):
            raise PrepError("REPRODUCIBILITY_MISMATCH", relative)
    for relative, content in sorted(artifacts.items()):
        path = project_path(root, relative)
        if not path.exists():
            atomic_bytes(path, content)
    return {relative: digest(content) for relative, content in sorted(artifacts.items())}


def verify_run(root, relative):
    path = project_path(root, relative)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "completed":
        raise PrepError("RUN_NOT_COMPLETED", "Only completed manifests can be verified")
    for label in ("inputs", "outputs", "code_hashes"):
        for name, expected in manifest[label].items():
            target = project_path(root, name)
            if not target.is_file() or file_hash(target) != expected:
                raise PrepError("RUN_HASH_MISMATCH", f"{label}: {name}")
    return {"passed": True, "analysis_id": manifest["analysis_id"],
            "verified_outputs": len(manifest["outputs"]), "inference": manifest["stages"]["inference"]}
