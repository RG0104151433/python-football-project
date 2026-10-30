"""Same-version contracts. Labels remain outcomes and never enter model predictors."""
from pathlib import Path
import json
import numpy as np
from src.data_contract import file_hash
from src.strength.io import ROOT, read_rows


def load(config_path="config/strength_joint.json"):
    cfg = json.loads((ROOT / config_path).read_text(encoding="utf-8-sig"))
    if cfg["schema_version"] != "strength-joint-v1":
        raise ValueError("INPUT_VERSION_MISMATCH: protocol")
    folder = ROOT / cfg["input"]
    if file_hash(folder / "manifest.json") != cfg["input_manifest_sha256"]:
        raise ValueError("INPUT_VERSION_MISMATCH: adopted manifest")
    manifest = json.loads((folder / "manifest.json").read_text())
    for name, digest in manifest["outputs"].items():
        if file_hash(folder / name) != digest:
            raise ValueError("INPUT_VERSION_MISMATCH: " + name)
    rows = read_rows(folder / "analysis_matches.csv")
    facts = {r["match_id"]: r for r in read_rows(ROOT / cfg["facts"])}
    if len(rows) != 24917 or len({r["match_id"] for r in rows}) != 24917 or {r["match_id"] for r in rows} != facts.keys():
        raise ValueError("INPUT_VERSION_MISMATCH: study IDs")
    fact_fields = ("date", "year", "era", "tournament_group", "home_region", "away_region", "home_unit", "away_unit", "outcome", "home_win")
    for r in rows:
        if any(r[k] != facts[r["match_id"]][k] for k in fact_fields):
            raise ValueError("INPUT_VERSION_MISMATCH: original facts")
    validate_rows(rows)
    targets = [r for r in read_rows(ROOT / cfg["targets"]) if r["family"] == "CORE"]
    if len(targets) != 32:
        raise ValueError("INPUT_VERSION_MISMATCH: CORE target count")
    geography = json.loads((ROOT / cfg["regions_config"]).read_text(encoding="utf-8-sig"))
    inputs = {config_path: file_hash(ROOT / config_path), cfg["input"] + "/manifest.json": file_hash(folder / "manifest.json"),
              cfg["facts"]: file_hash(ROOT / cfg["facts"]), cfg["targets"]: file_hash(ROOT / cfg["targets"]),
              cfg["regions_config"]: file_hash(ROOT / cfg["regions_config"])}
    return cfg, rows, targets, geography, inputs


def validate_rows(rows):
    for r in rows:
        if r["prediction_cutoff"] >= r["date"]:
            raise ValueError("FUTURE_INFORMATION: " + r["match_id"])
        if r["outcome"] not in ("home", "draw", "away") or int(r["home_win"]) != (r["outcome"] == "home"):
            raise ValueError("INVALID_OUTCOME")
        mu, v, base, nh, na, sd = [float(r[k]) for k in (
            "strength_difference", "strength_difference_variance", "strength_difference_base_variance",
            "home_jump_intensity", "away_jump_intensity", "jump_scale_sd")]
        if not np.isfinite([mu, v, base, nh, na, sd]).all() or base <= 0 or min(nh, na, sd) < 0 or abs(v - base - (nh + na) * sd * sd) > 2e-8:
            raise ValueError("DISTRIBUTION_FIELDS_MISSING: " + r["match_id"])
    return True


def distribution(rows):
    return {name: np.array([float(r[field]) for r in rows]) for name, field in (
        ("mu", "strength_difference"), ("base", "strength_difference_base_variance"),
        ("nu_h", "home_jump_intensity"), ("nu_a", "away_jump_intensity"), ("sd", "jump_scale_sd"))}
