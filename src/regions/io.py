"""Pinned input validation and portable, read-only joins."""
import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from ..artifact_store import resolve_artifact


class RegionError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require(condition, code, message):
    if not condition:
        raise RegionError(code, message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def project_path(root, value):
    root = Path(root).resolve()
    path = (root / str(value).replace("\\", "/")).resolve()
    require(path.is_relative_to(root), "REG_PATH", f"Outside repository: {value}")
    return path


def read_rows(path, key=None):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)),
                "REG_SCHEMA", f"Duplicate or absent headers: {path}")
        rows = list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows),
            "REG_SCHEMA", f"Malformed CSV row: {path}")
    if key:
        require(all(r.get(key) for r in rows), "REG_ID", f"Missing {key}: {path}")
        require(len({r[key] for r in rows}) == len(rows), "REG_DUPLICATE", f"Duplicate {key}: {path}")
    return rows


def strict_bool(value):
    require(value in ("true", "false"), "REG_BOOLEAN", f"Expected true/false, got {value!r}")
    return value == "true"


def score(value):
    require(bool(re.fullmatch(r"[0-9]+", value)), "REG_SCORE", f"Invalid score: {value!r}")
    return int(value)


def era_for(value, config):
    require(date.fromisoformat(value).isoformat() == value, "REG_DATE", value)
    eras = [e["id"] for e in config["strata"]["eras"] if e["start"] <= value <= e["end"]]
    require(len(eras) == 1, "REG_DATE", f"Date has no unique analysis era: {value}")
    return eras[0]


def study_labels(team, value, region, unit, base_rule, classification):
    """Apply fixed project exceptions without modifying the M49-based source."""
    rule = "BASE:" + base_rule
    for override in classification["overrides"]:
        if team == override["team_id"] and classification["scope"]["start"] <= value <= classification["scope"]["end"]:
            require((region, unit) == (override["base_region"], override["base_unit"]),
                    "REG_OVERRIDE_BASE", "Unexpected original classification: " + team)
            region, unit, rule = override["region"], override["unit"], override["rule_id"]
    for merge in classification["merges"]:
        if region == merge["region"] and unit in merge["base_units"]:
            unit, rule = merge["unit"], merge["rule_id"] + ":" + rule
    return region, unit, rule


def apply_study_labels(row, classification):
    row = dict(row)
    for role in ("home", "away"):
        for field in ("region", "unit"):
            row["base_" + role + "_" + field] = row[role + "_" + field]
        region, unit, rule = study_labels(row[role + "_team_id"], row["date"], row[role + "_region"],
                                         row[role + "_unit"], row[role + "_rule_id"], classification)
        row[role + "_region"], row[role + "_unit"], row[role + "_study_rule_id"] = region, unit, rule
    row["base_direction"], row["base_relation"] = row["direction"], row["relation"]
    hr, ar, hu, au = (row[k] for k in ("home_region", "away_region", "home_unit", "away_unit"))
    row["direction"] = (hr or "UNKNOWN") + ">" + (ar or "UNKNOWN")
    relation = "unknown"
    if hr and ar:
        if hr != ar:
            relation = "cross_region"
        elif hu and au:
            relation = "same_unit" if hu == au else "same_region_diff_unit"
    row["relation"] = relation
    for kind, usable in (("A", bool(hr)), ("B", relation != "unknown"), ("C", bool(hu))):
        row[kind + "_usable"] = usable
        row[kind + "_reason"] = "study_classification_known" if usable else "study_classification_unknown"
    return row


def load_inputs(root, relative="config/regions_study.json"):
    root = Path(root).resolve()
    config_path = project_path(root, relative)
    c = read_json(config_path)
    require(c["protocol_id"] in ("regions-study-v3", "regions-study-v4"), "REG_PROTOCOL", "Expected approved protocol")
    require(c["inference"]["p_values_or_confidence_intervals_in_q3"] is False,
            "REG_INFERENCE", "Q3 inference is not implemented")
    run = project_path(root, c["grouping"]["adopted_run"])
    manifest = read_json(run / "manifest.json")
    require(manifest["status"] == "ok" and not (run / "failure_report.json").exists(),
            "REG_UPSTREAM", "Cannot adopt a failed preparation run")
    inputs = {}

    def pin(path, expected=None):
        path = Path(path).resolve()
        require(path.is_relative_to(root), "REG_PATH", str(path))
        actual = sha(path)
        require(expected is None or actual == expected, "REG_HASH", f"Changed input: {path}")
        inputs[path.relative_to(root).as_posix()] = actual
        return path

    pin(config_path)
    pin(run / "manifest.json")
    for name, expected in manifest["files"].items():
        original = project_path(root, (run / name.replace("\\", "/")).relative_to(root))
        pin(resolve_artifact(original, root), expected)
    im_path = pin(run / "inputs/inputs_manifest.json", c["grouping"]["input_manifest_sha256"])
    require(sha(run / "code/prepare_region_mapping.py") == c["grouping"]["script_sha256"],
            "REG_HASH", "Grouping computation does not match protocol")
    items = read_json(im_path)["items"]
    paths = {}
    for key, item in items.items():
        original = (project_path(root, item["shared_path"]) if item.get("storage") == "shared"
                    else run / item["snapshot_path"].replace("\\", "/"))
        paths[key] = pin(resolve_artifact(original, root), item["sha256"])
    geo = read_rows(run / "match_region_relations.csv", "match_id")
    clean = {r["match_id"]: r for r in read_rows(paths["matches_clean"], "match_id")}
    membership = read_rows(paths["q2_membership"], "match_id")
    included = {r["match_id"]: r for r in membership if strict_bool(r["included"])}
    require(set(included) == {r["match_id"] for r in geo}, "REG_SAMPLE", "Q2 and Q3 sample IDs differ")
    require(len(geo) == c["scope"]["parent_matches"], "REG_SAMPLE", "Unexpected parent sample size")
    facts = []
    for g in sorted(geo, key=lambda r: r["match_id"]):
        mid = g["match_id"]
        require(mid in clean, "REG_JOIN", f"Missing result: {mid}")
        raw, member = clean[mid], included[mid]
        for k in ("data_version", "identity_version", "sample_id"):
            require(g[k] == member[k] == c["scope"][k], "REG_VERSION", f"Version conflict: {mid}/{k}")
        for k in ("date", "tournament_group"):
            require(g[k] == raw[k] == member[k], "REG_JOIN", f"Result metadata conflict: {mid}/{k}")
        for k in ("home_team_id", "away_team_id"):
            require(g[k] == raw[k], "REG_JOIN", f"Team identity conflict: {mid}/{k}")
        require(raw["source_record_id"] == member["source_record_id"], "REG_JOIN", f"Source conflict: {mid}")
        require(g["era"] == member["analysis_era_id"] == era_for(g["date"], c), "REG_DATE", mid)
        require(c["scope"]["start"] <= g["date"] <= c["scope"]["end"], "REG_DATE", mid)
        require(g["tournament_group"] in c["strata"]["tournament_groups"], "REG_TYPE", mid)
        require(not strict_bool(raw["is_neutral"]) and strict_bool(raw["eligible_venue_analysis"])
                and strict_bool(raw["eligible_tournament_analysis"]), "REG_SAMPLE", mid)
        require(raw["result_basis"] == c["scope"]["result_basis"], "REG_RESULT_BASIS", mid)
        hs, aws = score(raw["home_score"]), score(raw["away_score"])
        outcome = "home" if hs > aws else "away" if hs < aws else "draw"
        require(outcome == raw["outcome"], "REG_SCORE", f"Outcome conflict: {mid}")
        fact = {k: g[k] for k in ("match_id", "date", "era", "tournament_group", "home_team_id", "away_team_id",
                                  "home_region", "home_unit", "home_rule_id", "away_region", "away_unit", "away_rule_id",
                                  "direction", "relation")}
        fact.update({k: raw[k] for k in ("source_record_id", "home_team", "away_team", "city", "country", "result_basis")})
        fact.update(year=int(g["date"][:4]), home_score=hs, away_score=aws, home_win=int(hs > aws),
                    outcome=outcome, is_neutral=False)
        for kind in "ABC":
            fact[kind + "_usable"] = strict_bool(g[kind + "_usable"])
            fact[kind + "_reason"] = g[kind + "_reason"]
        for k in ("home_region", "home_unit", "away_region", "away_unit"):
            require(not fact[k] or bool(re.fullmatch(r"\d{3}", fact[k])), "REG_CODE", f"Bad geographic code: {mid}")
        facts.append(fact)
    if c["protocol_id"] == "regions-study-v4":
        path = pin(project_path(root, c["study_classification_path"]))
        require(read_json(path) == c["study_classification"], "REG_OVERRIDE_CONFIG", "Study classification differs from protocol")
        observed_teams = {r[k] for r in facts for k in ("home_team_id", "away_team_id")}
        require(all(rule["team_id"] in observed_teams for rule in c["study_classification"]["overrides"]),
                "REG_OVERRIDE_TEAM", "A requested classification team is absent")
        facts = [apply_study_labels(row, c["study_classification"]) for row in facts]
    roster = project_path(root, "outputs/tables/regions/preparation/regions-study-v2/team_geography_roster.csv")
    pin(roster)
    chinese = {r["team_id"]: r["team_name_zh"] for r in read_rows(roster)}
    require(all(r[k] in chinese for r in facts for k in ("home_team_id", "away_team_id")), "REG_LABEL", "Missing team label")
    return dict(root=root, config=c, config_path=config_path, facts=facts, inputs=inputs,
                grouping_run=c["grouping"]["adopted_run"], team_labels=chinese, base_roster=read_rows(roster))
