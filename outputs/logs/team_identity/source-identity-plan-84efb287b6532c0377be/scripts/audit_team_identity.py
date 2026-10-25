"""Read-only team-label inventory. No identity classification, decisions or data edits.

Run directly from any working directory. Decision planning belongs to step four;
this release implements step two only, with a separately verifiable run manifest.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from src.data_contract import (CLEAN_FIELDS, SCHEMAS, TEAM_FIELDS, PrepError,
                               csv_bytes, fingerprint, normalize, parse_date, read_csv)
from src.validate import validate_dataset

CONFIG_FIELDS = {"schema_version", "data_version", "baseline_manifest",
                 "baseline_manifest_sha256", "prep_config", "analysis_config"}
CODE_FILES = ("scripts/audit_team_identity.py", "src/data_contract.py",
              "src/validate.py", "src/snapshot.py")
FIELDS = {
    "team_inventory": "source_team_id source_team_label raw_first_date raw_last_date raw_appearances clean_appearances study_appearances study_first_date study_last_date upstream_rule_count study_former_interval_appearances study_venue_name_flag_appearances review_priority clue_types identity_classification review_status",
    "review_queue": "source_team_id source_team_label review_priority study_appearances clue_types entity_type historical_name_decision scope_decision evidence_ids checked_by independently_reviewed_by review_status notes",
    "upstream_name_rules": "rule_id current_label former_label start_date end_date source_file source_sha256 source_record_no evidence_status",
    "historical_name_clues": "source_record_id match_id date side source_team_id source_team_label rule_id upstream_former_label in_clean in_study clue_status",
    "venue_name_flags": "match_id source_record_id date home_team_id home_team away_team_id away_team country city in_study flag_type review_status",
}
FIELDS = {k: v.split() for k, v in FIELDS.items()}


def fail(code, message):
    raise PrepError(code, message)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def safe(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        fail("IDENTITY_PATH_INVALID", str(value))
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        fail("IDENTITY_PATH_OUTSIDE_PROJECT", value)
    return path


def file_hash(path):
    return digest(path.read_bytes())


def load_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail("IDENTITY_JSON_DUPLICATE_KEY", key)
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)
    if not isinstance(value, dict):
        fail("IDENTITY_JSON_INVALID", str(path))
    return value


def verify_baseline(root, baseline):
    if baseline.get("schema_version") != "identity-baseline-v1":
        fail("IDENTITY_BASELINE_INVALID", "Unknown baseline schema")
    expected = {}
    for entry in baseline["files"]:
        path, h = entry["path"], entry["sha256"]
        safe(root, path)
        if path in expected or not re.fullmatch(r"[0-9a-f]{64}", h):
            fail("IDENTITY_BASELINE_INVALID", path)
        expected[path] = h
    archive = safe(root, baseline["archive"]["path"])
    if file_hash(archive) != baseline["archive"]["sha256"]:
        fail("IDENTITY_BASELINE_ARCHIVE_MISMATCH", str(archive))
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.namelist()
        if len(members) != len(set(members)) or set(members) != set(expected):
            fail("IDENTITY_BASELINE_MEMBERS_INVALID", "Archive membership differs")
        for name, h in expected.items():
            if digest(bundle.read(name)) != h:
                fail("IDENTITY_BASELINE_MEMBER_MISMATCH", name)
    return expected


def load_inputs(root, config_relative):
    config_path = safe(root, config_relative)
    config = load_json(config_path)
    if set(config) != CONFIG_FIELDS or config["schema_version"] != "team-identity-inventory-config-v1":
        fail("IDENTITY_CONFIG_INVALID", "Unexpected inventory config fields/schema")
    version = config["data_version"]
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", version):
        fail("IDENTITY_CONFIG_INVALID", "Invalid data version")
    baseline_path = safe(root, config["baseline_manifest"])
    if file_hash(baseline_path) != config["baseline_manifest_sha256"]:
        fail("IDENTITY_BASELINE_MANIFEST_MISMATCH", "Registered baseline was changed")
    baseline = load_json(baseline_path)
    if baseline["data_version"] != version:
        fail("IDENTITY_BASELINE_VERSION_MISMATCH", version)
    registered = verify_baseline(root, baseline)
    inputs = {config_relative: file_hash(config_path),
              config["baseline_manifest"]: file_hash(baseline_path),
              baseline["archive"]["path"]: baseline["archive"]["sha256"]}

    def pinned(relative):
        target = safe(root, relative)
        if relative not in registered or file_hash(target) != registered[relative]:
            fail("IDENTITY_INPUT_BASELINE_MISMATCH", relative)
        inputs[relative] = registered[relative]
        return target

    prep = load_json(pinned(config["prep_config"]))
    analysis = load_json(pinned(config["analysis_config"]))
    if analysis.get("schema_version") != "eras-config-v1" or analysis.get("data_version") != version:
        fail("IDENTITY_SCOPE_INVALID", "Scope must refer to the registered era configuration")
    start, end = parse_date(analysis["analysis_start"]), parse_date(analysis["analysis_end"])
    if not start <= end <= parse_date(prep["data"]["cutoff_date"]):
        fail("IDENTITY_SCOPE_INVALID", "Invalid analysis window")
    folder = safe(root, prep["data"]["processed_dir"]) / version
    manifest_relative = (folder / "dataset_manifest.json").relative_to(root).as_posix()
    manifest = load_json(pinned(manifest_relative))
    raw_manifest = load_json(pinned(prep["data"]["raw_dir"] + "/manifest.json"))
    for entry in raw_manifest["files"]:
        pinned(entry["path"])
    for name in manifest["output_hashes"]:
        pinned((folder / name).relative_to(root).as_posix())
    pinned(manifest["lineage_path"])
    registry_path = pinned("data/external/team_registry.csv")
    validation = validate_dataset(root, prep, version)
    result_entry = next(e for e in raw_manifest["files"] if e["path"].endswith("/results.csv"))
    former_entry = next(e for e in raw_manifest["files"] if e["path"].endswith("/former_names.csv"))
    return dict(config=config, inputs=inputs, baseline_id=baseline["baseline_id"],
                validation=validation, scope={"start": start, "end": end},
                raw=read_csv(safe(root, result_entry["path"]), SCHEMAS["results.csv"])[1],
                clean=read_csv(folder / "matches_clean.csv", CLEAN_FIELDS)[1],
                registry=read_csv(registry_path, TEAM_FIELDS)[1],
                former=read_csv(safe(root, former_entry["path"]), SCHEMAS["former_names.csv"])[1],
                results_sha=result_entry["sha256"], former_source=former_entry)


def selected(row, scope):
    return (scope["start"] <= row["date"] <= scope["end"]
            and row["eligible_venue_analysis"] == "true" and row["is_neutral"] == "false"
            and row["eligible_tournament_analysis"] == "true"
            and row["tournament_group"] in {"friendly", "non_friendly"})


def collect_inventory(raw, clean, registry, former, scope, results_sha, former_source):
    """Pure inventory on provided records; never infer membership from a label."""
    by_name, by_id = {}, {}
    for item in registry:
        name, team_id = item["canonical_name"], item["team_id"]
        if not name or name != normalize(name) or name in by_name or not team_id or team_id in by_id:
            fail("IDENTITY_REGISTRY_INVALID", name)
        by_name[name], by_id[team_id] = item, name
    raw_counts, clean_counts, study_counts = Counter(), Counter(), Counter()
    raw_dates, study_dates = defaultdict(list), defaultdict(list)
    raw_sources = set()
    clean_by_source = {r["source_record_id"]: r for r in clean}
    if len(clean_by_source) != len(clean) or len({r["match_id"] for r in clean}) != len(clean):
        fail("IDENTITY_CLEAN_DUPLICATE", "Duplicate clean match/source identity")
    study = [r for r in clean if selected(r, scope)]
    study_ids = {r["match_id"] for r in study}
    rules, rules_by_name = [], defaultdict(list)
    for number, item in enumerate(former, 1):
        start = parse_date(item["start_date"]) if item["start_date"] else "0001-01-01"
        end = parse_date(item["end_date"]) if item["end_date"] else "9999-12-31"
        current, old = normalize(item["current"]), normalize(item["former"])
        if not current or not old or start > end:
            fail("IDENTITY_FORMER_RULE_INVALID", str(number))
        rule = dict(rule_id=f"former:{former_source['sha256']}:{number}",
                    current_label=current, former_label=old, start_date=start, end_date=end,
                    source_file=former_source["path"], source_sha256=former_source["sha256"],
                    source_record_no=number, evidence_status="upstream_unverified")
        rules.append(rule)
        rules_by_name[current].append(rule)
    clues = []
    for number, row in enumerate(raw, 1):
        day = parse_date(row["date"])
        source = f"results:{results_sha}:{number}"
        raw_sources.add(source)
        # Source match IDs use the project's existing content-fingerprint contract.
        match_id = "results:" + fingerprint([row[k] for k in SCHEMAS["results.csv"]])
        if source in clean_by_source and clean_by_source[source]["match_id"] != match_id:
            fail("IDENTITY_SOURCE_CONTENT_MISMATCH", source)
        for side in ("home", "away"):
            name = normalize(row[side + "_team"])
            if name not in by_name:
                fail("IDENTITY_TEAM_UNREGISTERED", name)
            raw_counts[name] += 1
            raw_dates[name].append(day)
            for rule in rules_by_name[name]:
                if rule["start_date"] <= day <= rule["end_date"]:
                    clean_row = clean_by_source.get(source)
                    clues.append(dict(source_record_id=source, match_id=match_id, date=day,
                                      side=side, source_team_id=by_name[name]["team_id"],
                                      source_team_label=name, rule_id=rule["rule_id"],
                                      upstream_former_label=rule["former_label"],
                                      in_clean=clean_row is not None,
                                      in_study=clean_row is not None and clean_row["match_id"] in study_ids,
                                      clue_status="upstream_interval_not_error_verdict"))
    if not set(clean_by_source).issubset(raw_sources):
        fail("IDENTITY_CLEAN_SOURCE_UNKNOWN", "Clean rows are not covered by raw records")
    for row in clean:
        for side in ("home", "away"):
            name = row[side + "_team"]
            if name not in by_name or row[side + "_team_id"] != by_name[name]["team_id"]:
                fail("IDENTITY_CLEAN_TEAM_MISMATCH", name)
            clean_counts[name] += 1
            if row["match_id"] in study_ids:
                study_counts[name] += 1
                study_dates[name].append(row["date"])
    flags = []
    for row in clean:
        if (row["is_neutral"] == "false" and row["country"] == row["away_team"]
                and row["country"] != row["home_team"]):
            flag = {k: row[k] for k in ("match_id", "source_record_id", "date", "home_team_id",
                                       "home_team", "away_team_id", "away_team", "country", "city")}
            flag.update(in_study=row["match_id"] in study_ids,
                        flag_type="literal_away_country_match_not_venue_error_verdict", review_status="pending")
            flags.append(flag)
    clue_appearances, flagged_appearances = Counter(), Counter()
    for c in clues:
        if c["in_study"]:
            clue_appearances[c["source_team_label"]] += 1
    for flag in flags:
        if flag["in_study"]:
            flagged_appearances.update([flag["home_team"], flag["away_team"]])
    inventory, queue = [], []
    for name in sorted(raw_counts):
        types = []
        if clue_appearances[name]:
            types.append("upstream_historical_interval")
        if flagged_appearances[name]:
            types.append("literal_venue_name_relation")
        priority = "1_study_with_clues" if study_counts[name] and types else (
            "2_study_unreviewed" if study_counts[name] else "3_outside_study")
        item = dict(source_team_id=by_name[name]["team_id"], source_team_label=name,
                    raw_first_date=min(raw_dates[name]), raw_last_date=max(raw_dates[name]),
                    raw_appearances=raw_counts[name], clean_appearances=clean_counts[name],
                    study_appearances=study_counts[name],
                    study_first_date=min(study_dates[name]) if study_dates[name] else "",
                    study_last_date=max(study_dates[name]) if study_dates[name] else "",
                    upstream_rule_count=len(rules_by_name[name]),
                    study_former_interval_appearances=clue_appearances[name],
                    study_venue_name_flag_appearances=flagged_appearances[name],
                    review_priority=priority, clue_types=types,
                    identity_classification="unreviewed", review_status="pending")
        inventory.append(item)
        queue.append(dict(source_team_id=item["source_team_id"], source_team_label=name,
                          review_priority=priority, study_appearances=study_counts[name], clue_types=types,
                          entity_type="", historical_name_decision="", scope_decision="",
                          evidence_ids=[], checked_by="", independently_reviewed_by="",
                          review_status="pending", notes="Clues only; no automatic identity or scope decision."))
    queue.sort(key=lambda r: (r["review_priority"], -r["study_appearances"], r["source_team_id"]))
    clues.sort(key=lambda r: (r["source_record_id"], r["side"], r["rule_id"]))
    flags.sort(key=lambda r: (r["date"], r["match_id"]))
    counts = dict(raw_matches=len(raw), clean_matches=len(clean), study_matches=len(study),
                  registry_labels=len(registry), raw_labels=len(raw_counts), clean_labels=len(clean_counts),
                  study_labels=len(study_counts), upstream_rules=len(rules),
                  historical_clue_rows=len(clues),
                  study_matches_with_historical_clues=len({c["match_id"] for c in clues if c["in_study"]}),
                  study_literal_venue_flags=sum(f["in_study"] for f in flags),
                  review_priorities=dict(sorted(Counter(r["review_priority"] for r in inventory).items())))
    checks = dict(raw_appearances=sum(raw_counts.values()) == 2 * len(raw),
                  clean_appearances=sum(clean_counts.values()) == 2 * len(clean),
                  study_appearances=sum(study_counts.values()) == 2 * len(study),
                  all_raw_labels_registered=set(raw_counts).issubset(by_name),
                  queue_covers_inventory={r["source_team_id"] for r in queue} == {r["source_team_id"] for r in inventory},
                  unique_clues=len(clues) == len({(r["source_record_id"], r["side"], r["rule_id"]) for r in clues}),
                  no_identity_decisions=all(r["identity_classification"] == "unreviewed" for r in inventory))
    if not all(checks.values()):
        fail("IDENTITY_INVENTORY_RECONCILIATION_FAILED", str(checks))
    return dict(team_inventory=inventory, review_queue=queue, upstream_name_rules=rules,
                historical_name_clues=clues, venue_name_flags=flags), counts, checks


def code_hashes(root):
    return {p: file_hash(safe(root, p)) for p in CODE_FILES}


def verify_run(root, relative):
    manifest = load_json(safe(root, relative))
    if manifest.get("schema_version") != "team-identity-inventory-run-v1" or manifest.get("status") != "completed_inventory_only":
        fail("IDENTITY_RUN_INCOMPLETE", relative)
    for section in ("inputs", "outputs", "code_hashes"):
        for p, h in manifest[section].items():
            if file_hash(safe(root, p)) != h:
                fail("IDENTITY_RUN_HASH_MISMATCH", p)
    return dict(passed=True, inventory_id=manifest["inventory_id"],
                verified_outputs=len(manifest["outputs"]), identity_review="not_performed")


def run_inventory(root, config_relative):
    data = load_inputs(root, config_relative)
    sources = code_hashes(root)
    tables, counts, checks = collect_inventory(**{k: data[k] for k in (
        "raw", "clean", "registry", "former", "scope", "results_sha", "former_source")})
    identity = dict(schema="team-identity-inventory-v1", inputs=data["inputs"], code=sources,
                    scope=data["scope"], python=sys.version.split()[0])
    inventory_id = "identity-inventory-" + digest(json_bytes(identity))[:20]
    artifacts = {name + ".csv": csv_bytes(FIELDS[name], rows) for name, rows in tables.items()}
    artifacts["counts.json"] = json_bytes(counts)
    artifacts["checks.json"] = json_bytes(dict(passed=True, checks=checks, prep_validation=data["validation"]))
    dictionary = ["# Identity inventory fields", "", "UTF-8 BOM CSV, LF; integer counts; lowercase booleans; JSON arrays; empty fields are unknown, never approval.",
                  "No eligibility/identity decisions applied. Review priority is a research queue, not a confidence score.", ""]
    for name, fields in FIELDS.items():
        dictionary += ["## " + name, "", ", ".join(fields), ""]
    dictionary += ["source_team_id is the existing mechanical registry ID, not a validated historical entity.",
                   "raw/clean/study appearances count team participation; each match contributes two appearances.",
                   "historical_name_clues link upstream intervals on both raw sides, including rows excluded from clean; they are not corrected facts.",
                   "in_study follows the registered analysis dates, known non-neutral venue and known tournament eligibility.",
                   "review_queue is a prefilled draft; copy it before writing evidence. This release does not read it as executable decisions.",
                   "1_study_with_clues, 2_study_unreviewed, 3_outside_study sort review work only; ordinary labels still require identity review."]
    artifacts["data_dictionary.md"] = ("\n".join(dictionary) + "\n").encode("utf-8")
    summary = ["# 球队标签盘点（第二步）", "", f"inventory_id: {inventory_id}",
               f"数据版本：{data['config']['data_version']}；窗口：{data['scope']['start']}—{data['scope']['end']}。",
               f"原始标签{counts['raw_labels']}，清洗标签{counts['clean_labels']}，研究标签{counts['study_labels']}。",
               f"研究比赛{counts['study_matches']}；落在上游历史名称线索中的比赛{counts['study_matches_with_historical_clues']}。",
               "全部身份分类仍为unreviewed，全部工作表状态为pending。没有删队、改名、改比分或发布身份包。",
               "历史名称与字面场地关系仅为待查线索，不是错误裁定；排序不是FIFA资格或实体分类。",
               "review_queue.csv可复制到独立查证区填写，禁止覆盖本次运行成果；无来源时保留待定。",
               "后续查证形成明确决定后，再实现第四步的plan校验/预演；本版没有plan或发布入口。"]
    artifacts["summary.md"] = ("\n\n".join(summary) + "\n").encode("utf-8")
    # Check for concurrent edits before creating any successful run output.
    for p, h in {**data["inputs"], **sources}.items():
        if file_hash(safe(root, p)) != h:
            fail("IDENTITY_INPUT_CHANGED_DURING_RUN", p)
    run_id = "inventory-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    folder = safe(root, "outputs/logs/team_identity") / run_id
    folder.mkdir(parents=True, exist_ok=False)
    outputs = {}
    try:
        for name, content in artifacts.items():
            path = folder / name
            with path.open("xb") as stream:
                stream.write(content)
            outputs[path.relative_to(root).as_posix()] = digest(content)
        for p, h in {**data["inputs"], **sources}.items():
            if file_hash(safe(root, p)) != h:
                fail("IDENTITY_INPUT_CHANGED_DURING_RUN", p)
        manifest = dict(schema_version="team-identity-inventory-run-v1", status="completed_inventory_only",
                        inventory_id=inventory_id, run_id=run_id, baseline_id=data["baseline_id"],
                        created_at_utc=datetime.now(timezone.utc).isoformat(),
                        data_version=data["config"]["data_version"], scope=data["scope"],
                        inputs=data["inputs"], code_hashes=sources, outputs=outputs, counts=counts,
                        checks_passed=True, identity_review="not_performed", decisions_applied=0)
        with (folder / "run_manifest.json").open("xb") as stream:
            stream.write(json_bytes(manifest))
    except Exception as exc:
        with (folder / "failure.json").open("xb") as stream:
            stream.write(json_bytes(dict(status="failed", error=str(exc), completed_manifest=False)))
        raise
    return dict(status="completed_inventory_only", inventory_id=inventory_id,
                run_manifest=(folder / "run_manifest.json").relative_to(root).as_posix(), counts=counts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--config", default=None, help="Inventory config inside this repository")
    group.add_argument("--verify-run", help="Verify an existing inventory run; no files written")
    args = parser.parse_args(argv)
    try:
        result = verify_run(PROJECT, args.verify_run) if args.verify_run else run_inventory(
            PROJECT, args.config or "config/team_identity.json")
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (PrepError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps(dict(status="failed", error_code=getattr(exc, "code", "IDENTITY_INPUT_INVALID"),
                              message=str(exc)), ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
