"""Step-four proposal validation and impact preview; never publish or edit matches.

Kept separate from the inventory executable so its previously registered source
hash remains verifiable. Only annotations and explicit single-match exclusions
are supported. Entity merges, factual amendments and publication are rejected.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.audit_team_identity import (code_hashes, digest, fail, file_hash, json_bytes,
    load_inputs, load_json, safe, selected, verify_run)
from src.data_contract import PrepError, csv_bytes, parse_date, read_csv

REVIEW_FIELDS = "source_team_id source_team_label current_observation observation_date evidence_ids historical_status population_status checked_by independently_reviewed_by notes".split()
IMPACT_FIELDS = "decision_id action status match_id source_record_id date side source_team_id source_team_label proposed_annotation in_study proposed_exclusion facts_changed requires_new_prep requires_new_population requires_entity_review evidence_ids".split()
ACTIONS = {"historical_annotation", "exclude_match"}
OBSERVATIONS = {"unresolved", "current_fifa_directory_literal", "current_fifa_alias_candidate",
                "current_conifa_directory_literal", "historical_conifa_context",
                "historical_transition_context", "regional_federation_context",
                "regional_selection_fixture_corroborated"}
DECISION_FIELDS = {"decision_id", "action", "status", "source_team_id", "start", "end",
                   "match_id", "expected", "annotation", "evidence_ids", "reason",
                   "checked_by", "independently_reviewed_by"}


def ensure(condition, code, message):
    if not condition:
        fail(code, message)


def validate_proposals(data, review, evidence, decisions, policy):
    """Pure validation. A successful preview is never publication approval."""
    registry = {r["team_id"]: r["canonical_name"] for r in data["registry"]}
    ensure(len(registry) == len(data["registry"]), "PLAN_REGISTRY_INVALID", "Duplicate ID")
    ensure(policy.get("schema_version") == "team-identity-policy-draft-v1"
           and policy.get("status") == "proposed" and policy.get("unresolved") == "block_publication"
           and policy.get("scope") == data["scope"] and bool(policy.get("policy_id"))
           and bool(policy.get("population_question")), "PLAN_POLICY_INVALID", "Invalid draft policy/scope")
    evidence_by_id = {}
    for e in evidence:
        required = {"evidence_id", "title", "url", "accessed_on", "locator", "claim", "limits", "capture_kind"}
        ensure(set(e) == required and all(isinstance(e[k], str) and e[k] for k in required),
               "PLAN_EVIDENCE_INVALID", "Incomplete evidence")
        ensure(e["evidence_id"] not in evidence_by_id and e["url"].startswith(("https://", "repo:")),
               "PLAN_EVIDENCE_INVALID", e["evidence_id"])
        parse_date(e["accessed_on"])
        evidence_by_id[e["evidence_id"]] = e

    def references(ids):
        ensure(isinstance(ids, list) and bool(ids) and all(isinstance(x, str) for x in ids)
               and len(ids) == len(set(ids)) and all(x in evidence_by_id for x in ids),
               "PLAN_EVIDENCE_REFERENCE_INVALID", str(ids))

    reviewed = {}
    for row in review:
        tid = row["source_team_id"]
        ensure(tid in registry and row["source_team_label"] == registry[tid] and tid not in reviewed,
               "PLAN_REVIEW_TARGET_INVALID", tid)
        ensure(row["historical_status"] in {"pending", "corroborated_transition_dates_pending"}
               and row["population_status"] == "pending" and bool(row["checked_by"])
               and bool(row["notes"]) and row["current_observation"] in OBSERVATIONS,
               "PLAN_REVIEW_STATUS_INVALID", tid)
        refs = json.loads(row["evidence_ids"])
        if row["current_observation"] == "unresolved":
            ensure(refs == [] and row["observation_date"] == "", "PLAN_REVIEW_STATUS_INVALID", tid)
        else:
            references(refs)
            parse_date(row["observation_date"])
        reviewed[tid] = row
    ensure(set(reviewed) == set(registry), "PLAN_REVIEW_COVERAGE_INVALID", "All source labels must be accounted for")
    clean = {r["match_id"]: r for r in data["clean"]}
    ensure(len(clean) == len(data["clean"]), "PLAN_MATCH_DUPLICATE", "Duplicate match")
    seen, intervals, impacts, summaries = set(), {}, [], []
    for d in decisions:
        ensure(set(d) == DECISION_FIELDS, "PLAN_DECISION_SCHEMA_INVALID", str(d.get("decision_id")))
        did, action, tid = d["decision_id"], d["action"], d["source_team_id"]
        ensure(isinstance(did, str) and did and did not in seen, "PLAN_DECISION_DUPLICATE", str(did))
        seen.add(did)
        ensure(action in ACTIONS, "PLAN_ACTION_UNSUPPORTED", str(action))
        ensure(d["status"] == "proposed" and tid in registry and bool(d["checked_by"])
               and bool(d["reason"]) and bool(d["annotation"]), "PLAN_DECISION_INVALID", did)
        references(d["evidence_ids"])
        start, end = parse_date(d["start"]), parse_date(d["end"])
        ensure(start <= end, "PLAN_INTERVAL_INVALID", did)
        if action == "historical_annotation":
            ensure(d["match_id"] == "" and d["expected"] == {}, "PLAN_DECISION_INVALID", did)
            key = (tid, action)
            for a, b in intervals.get(key, []):
                ensure(end < a or b < start, "PLAN_INTERVAL_CONFLICT", did)
            intervals.setdefault(key, []).append((start, end))
            targets = list(clean.values())
        else:
            ensure(d["match_id"] in clean and start == end, "PLAN_MATCH_NOT_FOUND", did)
            expected = d["expected"]
            ensure(isinstance(expected, dict) and set(expected) == {
                "date", "home_team", "away_team", "home_score", "away_score", "country", "is_neutral"},
                "PLAN_OLD_VALUE_REQUIRED", did)
            target = clean[d["match_id"]]
            ensure(all(target[k] == v for k, v in expected.items()), "PLAN_OLD_VALUE_MISMATCH", did)
            ensure(target["date"] == start, "PLAN_INTERVAL_INVALID", did)
            ensure(not any(r["match_id"] == d["match_id"] and r["action"] == action for r in impacts),
                   "PLAN_MATCH_CONFLICT", did)
            targets = [target]
        count = 0
        for r in targets:
            if not start <= r["date"] <= end:
                continue
            for side in ("home", "away"):
                if r[side + "_team_id"] != tid:
                    continue
                count += 1
                impacts.append(dict(decision_id=did, action=action, status=d["status"],
                    match_id=r["match_id"], source_record_id=r["source_record_id"], date=r["date"],
                    side=side, source_team_id=tid, source_team_label=r[side + "_team"],
                    proposed_annotation=d["annotation"], in_study=selected(r, data["scope"]),
                    proposed_exclusion=action == "exclude_match", facts_changed=False,
                    requires_new_prep=False, requires_new_population=action == "exclude_match",
                    requires_entity_review=action == "historical_annotation", evidence_ids=d["evidence_ids"]))
        ensure(count > 0, "PLAN_DECISION_NO_TARGET", did)
        summaries.append(dict(decision_id=did, action=action, affected_appearances=count))
    impacts.sort(key=lambda x: (x["decision_id"], x["date"], x["match_id"], x["side"]))
    study_ids = {r["match_id"] for r in data["clean"] if selected(r, data["scope"])}
    exclusions = {r["match_id"] for r in impacts if r["proposed_exclusion"] and r["in_study"]}
    study_teams = {r[s + "_team_id"] for r in data["clean"] if selected(r, data["scope"]) for s in ("home", "away")}
    blockers = [dict(source_team_id=tid, source_team_label=registry[tid],
                     issue="population_and_match_time_identity_not_approved", in_study=tid in study_teams)
                for tid in sorted(registry)]
    summary = dict(status="completed_preview_only", structural_validation_passed=True,
        ready_for_publication=False, decisions_applied=0, policy_id=policy["policy_id"],
        labels=len(review), study_labels=len(study_teams),
        observations=dict(sorted(Counter(r["current_observation"] for r in review).items())),
        proposed_decisions=len(decisions), affected_matches=len({r["match_id"] for r in impacts}),
        affected_study_matches=len({r["match_id"] for r in impacts if r["in_study"]}),
        baseline_study_matches=len(study_ids), scenario_excluded_study_matches=len(exclusions),
        scenario_remaining_study_matches=len(study_ids - exclusions),
        publication_blocking_study_labels=len(study_teams),
        home_away_or_score_changes=0, results_recomputed=False,
        limitations=["Current membership does not establish historical eligibility.",
                    "Historical interval endpoints remain upstream clues, not independently verified dates.",
                    "Scenario exclusions are incomplete proposals, not an approved national-team population.",
                    "No entity merge/split, amendment, withdrawal replay or publication is implemented."])
    return impacts, blockers, summaries, summary


def run_plan(root, config_relative):
    config = load_json(safe(root, config_relative))
    ensure(set(config) == {"schema_version", "inventory_config", "inventory_run", "review", "evidence", "decisions", "policy", "directory_observations"}
           and config["schema_version"] == "team-identity-plan-config-v1", "PLAN_CONFIG_INVALID", "Invalid plan config")
    verify_run(root, config["inventory_run"])
    data = load_inputs(root, config["inventory_config"])
    inventory = load_json(safe(root, config["inventory_run"]))
    ensure(inventory["data_version"] == data["config"]["data_version"] and inventory["scope"] == data["scope"]
           and inventory["inputs"] == data["inputs"], "PLAN_INVENTORY_MISMATCH", "Inventory inputs differ")
    inputs = dict(data["inputs"])
    for value in (config_relative, config["inventory_run"], config["review"], config["evidence"], config["decisions"], config["policy"], config["directory_observations"]):
        inputs[value] = file_hash(safe(root, value))
    sources = {**code_hashes(root), "scripts/plan_team_identity.py": file_hash(root / "scripts/plan_team_identity.py")}
    fields, review = read_csv(safe(root, config["review"]), REVIEW_FIELDS)
    ensure(fields == REVIEW_FIELDS, "PLAN_REVIEW_SCHEMA_INVALID", "Unexpected review columns")
    directory = load_json(safe(root, config["directory_observations"]))
    ensure(directory.get("schema_version") == "identity-directory-observations-v1"
           and directory.get("alias_status") == "manual_candidate_not_independently_verified",
           "PLAN_DIRECTORY_INVALID", "Invalid observation schema")
    names, aliases = directory["fifa_directory_names"], directory["alias_candidates"]
    ensure(isinstance(names, list) and all(isinstance(n, str) and n for n in names)
           and len(names) == len(set(names)) and isinstance(aliases, dict)
           and all(v in names for v in aliases.values()), "PLAN_DIRECTORY_INVALID", "Invalid names/candidates")
    for row in review:
        if row["current_observation"] == "current_fifa_directory_literal":
            ensure(row["source_team_label"] in names, "PLAN_DIRECTORY_INVALID", row["source_team_label"])
        elif row["current_observation"] == "current_fifa_alias_candidate":
            ensure(row["source_team_label"] in aliases, "PLAN_DIRECTORY_INVALID", row["source_team_label"])
    ev = load_json(safe(root, config["evidence"]))
    ds = load_json(safe(root, config["decisions"]))
    ensure(ev.get("schema_version") == "identity-evidence-v1" and ds.get("schema_version") == "identity-decisions-draft-v1",
           "PLAN_REVIEW_SCHEMA_INVALID", "Unknown evidence/decisions schema")
    impacts, blockers, decisions, summary = validate_proposals(data, review, ev["evidence"], ds["decisions"], load_json(safe(root, config["policy"])))
    plan_id = "identity-plan-" + digest(json_bytes(dict(inputs=inputs, code=sources, python=sys.version.split()[0])))[:20]
    summary["plan_id"] = plan_id
    def unchanged():
        for p, h in {**inputs, **sources}.items():
            ensure(file_hash(safe(root, p)) == h, "PLAN_INPUT_CHANGED", p)
    unchanged()
    artifacts = {"match_impacts.csv": csv_bytes(IMPACT_FIELDS, impacts),
        "unresolved.csv": csv_bytes("source_team_id source_team_label issue in_study".split(), blockers),
        "decision_impacts.json": json_bytes(dict(decisions=decisions)), "summary.json": json_bytes(summary),
        "checks.json": json_bytes(dict(structural_validation_passed=True, inventory_verified=True,
                                       prep_validation=data["validation"], ready_for_publication=False)),
        "summary.md": ("# 球队身份决定预演\n\n"
            f"计划编号：{plan_id}。仅预演，未应用决定、发布身份包或重算研究结果。\n\n"
            f"登记{len(review)}个来源标签；当前观察分类见summary.json。拟议决定{len(decisions)}项，"
            f"涉及{summary['affected_study_matches']}场当前研究比赛。\n\n"
            f"仅单场排除提案的演示：{summary['baseline_study_matches']} → {summary['scenario_remaining_study_matches']}场。"
            "这是不完整的人群方案，不能用作新正式样本或代表全部待排除比赛。\n\n"
            "结构校验通过；身份/人群发布验收未通过。当前会员信息不能证明过去每场资格，"
            "历史日期仍需逐项取证，人群政策和地理重合解释尚未批准。无A/B独立复核。\n\n"
            "后续：补齐unresolved.csv所列范围问题，确认政策后再实现发布；统计可靠性仍后置。\n").encode("utf-8"),
        "data_dictionary.md": ("# 预演字段\n\nCSV：UTF-8 BOM、LF、稳定排序；布尔true/false，evidence_ids为JSON数组。\n\n"
            "match_impacts.csv一行为决定×比赛×一方；去重场数须按match_id统计，不能直接相加各决定。\n\n"
            "proposed_annotation只存解释建议，不是替换球队主键；in_study使用原分析资格。"
            "proposed_exclusion仅表示情景建议；facts_changed恒false，不交换主客、不改比分或中立标记。\n\n"
            "requires_entity_review表示历史实体解释仍需审查；requires_new_population表示若批准须新人群版本并重算两题。"
            "unresolved覆盖全部来源标签，以in_study区分本次关卡与范围外事项。\n").encode("utf-8")}
    run_id = "plan-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    folder = safe(root, "outputs/logs/team_identity/" + run_id)
    folder.mkdir(parents=True, exist_ok=False)
    try:
        outputs = {}
        for name, content in artifacts.items():
            p = folder / name
            with p.open("xb") as f:
                f.write(content)
            outputs[p.relative_to(root).as_posix()] = digest(content)
        unchanged()
        manifest = dict(schema_version="team-identity-plan-run-v1", status="completed_preview_only",
            plan_id=plan_id, run_id=run_id, created_at_utc=datetime.now(timezone.utc).isoformat(),
            inputs=inputs, code_hashes=sources, outputs=outputs, summary=summary)
        with (folder / "run_manifest.json").open("xb") as f:
            f.write(json_bytes(manifest))
    except Exception as exc:
        with (folder / "failure.json").open("xb") as f:
            f.write(json_bytes(dict(status="failed", error=str(exc))))
        raise
    return dict(summary, run_manifest=(folder / "run_manifest.json").relative_to(root).as_posix())


def verify_plan(root, relative):
    manifest = load_json(safe(root, relative))
    ensure(manifest.get("schema_version") == "team-identity-plan-run-v1" and manifest.get("status") == "completed_preview_only",
           "PLAN_MANIFEST_INVALID", relative)
    for section in ("inputs", "code_hashes", "outputs"):
        for p, h in manifest[section].items():
            ensure(file_hash(safe(root, p)) == h, "PLAN_HASH_MISMATCH", p)
    return dict(passed=True, plan_id=manifest["plan_id"], verified_outputs=len(manifest["outputs"]), ready_for_publication=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--config")
    group.add_argument("--verify-run")
    args = parser.parse_args(argv)
    try:
        result = verify_plan(PROJECT, args.verify_run) if args.verify_run else run_plan(PROJECT, args.config or "config/team_identity_plan.json")
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (PrepError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status="failed", error_code=getattr(exc, "code", "PLAN_INPUT_INVALID"), message=str(exc)), ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
