"""Validate the existing cleaning contract and select traceable analysis samples."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

from ..data_contract import (CLEAN_FIELDS, PrepError, file_hash, fingerprint,
                             parse_date, project_path, read_csv)
from ..validate import validate_dataset

GROUPS = ("friendly", "non_friendly")


def fail(code, message):
    raise PrepError(code, message)


def boolean(value):
    if value == "true":
        return True
    if value == "false":
        return False
    fail("ANALYSIS_BOOLEAN_INVALID", f"Expected lowercase true/false, got {value!r}")


def load_analysis_config(path: Path, cutoff: str):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    fields = {"schema_version", "data_version", "analysis_start", "analysis_end", "eras",
              "primary_contrasts", "reference_scheme", "alternative_reference_schemes",
              "inference", "sensitivity", "random_seed", "protocol_status", "protocol_decision"}
    if not isinstance(config, dict) or set(config) != fields:
        fail("ANALYSIS_CONFIG_INVALID", "Analysis config fields do not match eras-config-v1")
    if config["schema_version"] != "eras-config-v1":
        fail("ANALYSIS_CONFIG_INVALID", "Unknown schema version")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", str(config["data_version"])):
        fail("INVALID_DATA_VERSION", "data_version must be a directory name")
    start, end = parse_date(config["analysis_start"]), parse_date(config["analysis_end"])
    if not start <= end <= cutoff:
        fail("ANALYSIS_CONFIG_INVALID", "Window must be ordered and within data cutoff")
    if config["protocol_status"] not in {"draft", "confirmed"} or not config["protocol_decision"]:
        fail("ANALYSIS_CONFIG_INVALID", "Protocol status and decision reference required")
    if type(config["random_seed"]) is not int:
        fail("ANALYSIS_CONFIG_INVALID", "random_seed must be an integer")
    schemes = [config["reference_scheme"], *config["alternative_reference_schemes"]]
    if any(s not in {"pooled_matches", "equal_years"} for s in schemes) or len(set(schemes)) != len(schemes):
        fail("ANALYSIS_CONFIG_INVALID", "Unknown/duplicate reference schemes")
    if config["inference"] != {"mode": "off", "validation_status": "pending"}:
        fail("INFERENCE_NOT_IMPLEMENTED", "Only inference=off/pending is supported; no approved estimator exists")
    if set(config["sensitivity"]) != {"leave_one_year_out", "common_teams"} or any(
            type(v) is not bool for v in config["sensitivity"].values()):
        fail("ANALYSIS_CONFIG_INVALID", "Sensitivity options must be explicit booleans")
    previous, ids = None, set()
    if not config["eras"]:
        fail("ANALYSIS_CONFIG_INVALID", "At least one era required")
    for era in config["eras"]:
        if set(era) != {"id", "start", "end", "label"} or not re.fullmatch(r"[A-Za-z0-9_-]+", era["id"]):
            fail("ANALYSIS_CONFIG_INVALID", "Invalid era fields/id")
        a, b = parse_date(era["start"]), parse_date(era["end"])
        if era["id"] in ids or not start <= a <= b <= end:
            fail("ANALYSIS_CONFIG_INVALID", "Duplicate or invalid era")
        if (previous is None and a != start) or (previous is not None and date.fromisoformat(a) != date.fromisoformat(previous) + timedelta(days=1)):
            fail("ANALYSIS_CONFIG_INVALID", "Eras must cover the window without overlap/gaps")
        ids.add(era["id"])
        previous = b
    if previous != end:
        fail("ANALYSIS_CONFIG_INVALID", "Eras must cover the entire window")
    contrast_ids = set()
    positions = {era["id"]: i for i, era in enumerate(config["eras"])}
    for contrast in config["primary_contrasts"]:
        if set(contrast) != {"id", "earlier", "later"}:
            fail("ANALYSIS_CONFIG_INVALID", "Invalid contrast fields")
        if contrast["id"] in contrast_ids or not re.fullmatch(r"[A-Za-z0-9_-]+", contrast["id"]):
            fail("ANALYSIS_CONFIG_INVALID", "Duplicate/invalid contrast ID")
        if contrast["earlier"] not in ids or contrast["later"] not in ids or positions[contrast["earlier"]] >= positions[contrast["later"]]:
            fail("ANALYSIS_CONFIG_INVALID", "Contrast must be later minus earlier")
        contrast_ids.add(contrast["id"])
    return config


def load_validated_dataset(root, prep_config, config):
    validation = validate_dataset(root, prep_config, config["data_version"])
    folder = project_path(root, prep_config["data"]["processed_dir"]) / config["data_version"]
    manifest_path = folder / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _, raw_rows = read_csv(folder / "matches_clean.csv", CLEAN_FIELDS)
    rows = []
    for raw in raw_rows:
        row = dict(raw)
        for field in ("eligible_venue_analysis", "eligible_tournament_analysis"):
            row[field] = boolean(raw[field])
        row["is_neutral"] = None if raw["is_neutral"] == "" else boolean(raw["is_neutral"])
        for field in ("year", "home_score", "away_score", "goal_difference"):
            row[field] = int(raw[field])
        row["home_win"] = int(raw["outcome"] == "home")
        rows.append(row)
    input_paths = [manifest_path, folder / "matches_clean.csv", project_path(root, manifest["lineage_path"])]
    input_paths += [project_path(root, f["path"]) for f in manifest["input_files"]]
    inputs = {p.relative_to(root).as_posix(): file_hash(p) for p in input_paths}
    return rows, manifest, validation, inputs


def sample_id(rows, data_version):
    return "sample-" + fingerprint({"data_version": data_version, "ids": sorted(r["match_id"] for r in rows)})[:20]


def era_for(day, config):
    return next((e["id"] for e in config["eras"] if e["start"] <= day <= e["end"]), "")


def select_samples(rows, config):
    samples = {"base_venue": [], "classified_venue": []}
    membership = []
    for row in rows:
        reasons = []
        if not config["analysis_start"] <= row["date"] <= config["analysis_end"]:
            reasons.append("outside_analysis_window")
        if not row["eligible_venue_analysis"]:
            reasons.append("venue_ineligible")
        if row["is_neutral"] is not False:
            reasons.append("neutral" if row["is_neutral"] is True else "neutral_unknown")
        base = not reasons
        known = row["eligible_tournament_analysis"] and row["tournament_group"] in GROUPS
        classified = base and known
        if base:
            samples["base_venue"].append(row)
        if classified:
            samples["classified_venue"].append(row)
        if base and not known:
            reasons.append("tournament_ineligible_or_unknown")
        membership.append(dict(data_version=config["data_version"], match_id=row["match_id"],
                               source_record_id=row["source_record_id"], date=row["date"],
                               analysis_era_id=era_for(row["date"], config), in_base_venue=base,
                               in_classified_venue=classified,
                               primary_exclusion_reason=reasons[0] if reasons else "",
                               exclusion_reasons=reasons))
    return samples, membership


def upstream_flow(root, manifest):
    """Use the manifest-bound lineage, not a guessed latest cleaning report."""
    _, lineage = read_csv(project_path(root, manifest["lineage_path"]))
    result_source = next(f for f in manifest["input_files"] if f["path"].endswith("/results.csv"))
    _, original = read_csv(project_path(root, result_source["path"]))
    from collections import Counter
    counts = Counter()
    for row in lineage:
        raw_day = original[int(row["source_record_no"]) - 1]["date"]
        try:
            period = str(int(parse_date(raw_day)[:4]) // 10 * 10)
        except ValueError:
            period = "undated"
        counts[(row["final_status"], period)] += 1
    return [dict(flow_id="upstream", stage=state, parent_stage="raw", reason=period,
                 n_records=count, basis="upstream_raw", status="ok")
            for (state, period), count in sorted(counts.items())]
