"""Read validated, version-bound inputs and reproduce Q1's exact population."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_confirmed_eras import apply_overlay
from scripts.build_team_identity import MATCH_FIELDS, verify_identity
from ..data_contract import PrepError, file_hash, load_config, project_path, read_csv
from ..eras.data import load_analysis_config, load_validated_dataset, sample_id
from ..eras.reporting import verify_run as verify_q1

GROUPS = ("friendly", "non_friendly")


def require(condition, code, message):
    if not condition:
        raise PrepError(code, message)


def load_json(root, relative):
    return json.loads(project_path(root, relative).read_text(encoding="utf-8-sig"))


def load_settings(root, relative):
    try:
        cfg = load_json(root, relative)
        fields = {"schema_version", "prep_config", "q1_integration_config", "q1_run_manifest",
                  "analysis_start", "analysis_end", "groups", "difference_direction",
                  "era_reference_scheme", "rolling", "inference_mode", "protocol_status", "protocol_decision"}
        require(isinstance(cfg, dict) and set(cfg) == fields, "TQ_CONFIG_INVALID", "Unexpected config fields")
        require(cfg["schema_version"] == "tournaments-descriptive-v1" and cfg["groups"] == list(GROUPS)
                and cfg["difference_direction"] == "friendly_minus_non_friendly"
                and cfg["era_reference_scheme"] == "pooled_matches" and cfg["inference_mode"] == "off"
                and cfg["protocol_status"] == "exploratory" and bool(cfg["protocol_decision"]),
                "TQ_CONFIG_INVALID", "Only the approved exploratory descriptive protocol is implemented")
        require(cfg["rolling"] == dict(window_years=10, step_years=1, alignment="trailing_calendar_years",
                                        reference_scheme="pooled_year_counts")
                and type(cfg["rolling"]["window_years"]) is int and type(cfg["rolling"]["step_years"]) is int,
                "TQ_CONFIG_INVALID", "Only complete trailing ten-year windows with a one-year step")
        return cfg
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise PrepError("TQ_CONFIG_INVALID", str(exc)) from exc


def assert_same_sample(selected, reference):
    actual, expected = {r["match_id"] for r in selected}, set(reference)
    require(len(actual) == len(selected) and actual == expected, "TQ_Q1_SAMPLE_MISMATCH",
            f"Q1 sample IDs differ: added={sorted(actual-expected)[:10]}, missing={sorted(expected-actual)[:10]}")


def validate_results(rows):
    for row in rows:
        h, a = row["home_score"], row["away_score"]
        expected = "home" if h > a else "away" if h < a else "draw"
        require(type(h) is int and type(a) is int and h >= 0 and a >= 0
                and row["outcome"] == expected and row["home_win"] == int(h > a)
                and row["result_basis"] == "after_extra_time_excluding_shootout"
                and row["year"] == int(row["date"][:4]), "TQ_RESULT_INVALID", row["match_id"])


def load_inputs(root, relative):
    cfg = load_settings(root, relative)
    qcfg = load_json(root, cfg["q1_integration_config"])
    qrun = load_json(root, cfg["q1_run_manifest"])
    try:
        verify_q1(root, cfg["q1_run_manifest"])
        verify_identity(root, qcfg["identity_manifest"])
    except PrepError as exc:
        raise PrepError("TQ_INPUT_HASH_MISMATCH", str(exc)) from exc
    require(cfg["q1_integration_config"] in qrun["inputs"] and qcfg["analysis_config"] in qrun["inputs"]
            and qcfg["identity_manifest"] in qrun["inputs"] and cfg["prep_config"] == qcfg["prep_config"],
            "TQ_CONFIG_INVALID", "Q1 manifest must bind integration, analysis, identity and cleaning configs")
    _, prep = load_config(project_path(root, cfg["prep_config"]))
    analysis = load_analysis_config(project_path(root, qcfg["analysis_config"]), prep["data"]["cutoff_date"])
    identity = load_json(root, qcfg["identity_manifest"])
    require((cfg["analysis_start"], cfg["analysis_end"]) == (analysis["analysis_start"], analysis["analysis_end"])
            and cfg["analysis_start"].endswith("-01-01") and cfg["analysis_end"].endswith("-12-31")
            and identity["scope"] == dict(start=cfg["analysis_start"], end=cfg["analysis_end"])
            and identity["data_version"] == analysis["data_version"], "TQ_CONFIG_INVALID", "Input scope differs from Q1")
    rows, manifest, validation, _ = load_validated_dataset(root, prep, analysis)
    validate_results(rows)
    op = next(p for p in identity["outputs"] if p.endswith("/match_identity.csv"))
    _, overlay = read_csv(project_path(root, op), MATCH_FIELDS)
    try:
        _, samples, membership = apply_overlay(rows, analysis, overlay)
    except PrepError as exc:
        raise PrepError("TQ_IDENTITY_COVERAGE_INVALID", str(exc)) from exc
    qp = next(p for p in qrun["outputs"] if p.endswith("/analysis_membership.csv"))
    _, qmembers = read_csv(project_path(root, qp))
    require(len(qmembers) == len({x["match_id"] for x in qmembers}), "TQ_Q1_SAMPLE_MISMATCH", "Duplicate Q1 member ID")
    selected = sorted(samples["classified_venue"], key=lambda x: x["match_id"])
    assert_same_sample(selected, [x["match_id"] for x in qmembers if x["in_classified_venue"] == "true"])
    sid = sample_id(selected, analysis["data_version"])
    groups = {x["match_id"]: x["tournament_group"] for x in rows}
    normalized = [dict(data_version=analysis["data_version"], identity_version=identity["identity_version"], sample_id=sid,
                       **{k: m[k] for k in ("match_id", "source_record_id", "date", "analysis_era_id", "primary_exclusion_reason", "exclusion_reasons")},
                       tournament_group=groups[m["match_id"]], included=m["in_classified_venue"]) for m in membership]
    # Bind the full reference chain, not mutable navigation documents.
    inputs = dict(qrun["inputs"])
    inputs.update({p: file_hash(project_path(root, p)) for p in [relative, cfg["q1_run_manifest"], *qrun["outputs"]]})
    return dict(config=cfg, analysis=analysis, identity=identity, data_manifest=manifest, validation=validation,
                all_rows=rows, selected=selected, membership=normalized, sample_id=sid,
                inputs=inputs, inherited_code=qrun["code_hashes"], q1_run=qrun)
