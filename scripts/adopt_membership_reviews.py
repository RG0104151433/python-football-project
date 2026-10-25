"""Publish a versioned study-membership overlay from user-accepted reviews."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_team_identity import digest, file_hash, json_bytes, load_json, safe
from scripts.build_team_identity import MATCH_FIELDS, verify_identity
from scripts.plan_team_identity import ensure
from src.data_contract import csv_bytes, read_csv

DECISION_FIELDS = "match_id source_team_id source_team_label assessment_id proposed_membership adopted_membership approval_id basis".split()
CHANGE_FIELDS = "match_id old_membership_status new_membership_status old_disposition new_disposition user_match_approval".split()


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def effective_reviews(root, config, inputs):
    assessments = {}
    for relative in config["submission_dirs"]:
        folder = safe(root, relative)
        for path in sorted(folder.glob("*.jsonl")):
            inputs[path.relative_to(root).as_posix()] = file_hash(path)
        for item in jsonl(folder / "evidence.jsonl"):
            if item.get("local_path") and item.get("sha256"):
                p = item["local_path"]
                actual = file_hash(safe(root, p))
                ensure(actual == item["sha256"], "REVIEW_EVIDENCE_CHANGED", p)
                inputs[p] = actual
        for item in jsonl(folder / "case_assessments.jsonl"):
            aid = item["assessment_id"]
            ensure(aid not in assessments, "REVIEW_DUPLICATE_ID", aid)
            assessments[aid] = item
    coverage_path = safe(root, config["coverage"])
    inputs[config["coverage"]] = file_hash(coverage_path)
    _, coverage = read_csv(coverage_path)
    task_path = safe(root, config["tasks"])
    inputs[config["tasks"]] = file_hash(task_path)
    _, tasks = read_csv(task_path)
    task_map = {(t["source_team_id"], t["pending_status"]): t for t in tasks}
    keys = [(r["source_team_id"], r["pending_status"]) for r in coverage]
    ensure(len(keys) == len(set(keys)) == len(task_map) and set(keys) == set(task_map),
           "REVIEW_TASK_COVERAGE", "Task keys must match exactly")
    selected = {}
    for task in coverage:
        key = (task["source_team_id"], task["pending_status"])
        ids = json.loads(task["current_assessment_ids"]) or json.loads(task["previous_assessment_ids"])
        got = set()
        for aid in ids:
            ensure(aid in assessments, "REVIEW_ID_MISSING", aid)
            item = assessments[aid]
            ensure((item["source_team_id"], item["original_pending_status"]) == key,
                   "REVIEW_TASK_MISMATCH", aid)
            ensure(item["match_ids"] and item["source_team_label"] == task_map[key]["source_team_label"],
                   "REVIEW_EMPTY_OR_LABEL", aid)
            ensure(set(item["match_ids"]) <= set(json.loads(task_map[key]["match_ids"])),
                   "REVIEW_FOREIGN_MATCH", aid)
            got.update(item["match_ids"])
            selected[aid] = item
        ensure(got == set(json.loads(task_map[key]["match_ids"])), "REVIEW_TASK_INCOMPLETE", str(key))
    sides = {}
    unresolved = set()
    for aid, item in selected.items():
        ensure(item["proposed_membership"] in {"member", "non_member", "unresolved", "conflict"},
               "REVIEW_STATE_INVALID", aid)
        for mid in item["match_ids"]:
            key = (mid, item["source_team_id"])
            ensure(key not in sides, "REVIEW_DUPLICATE_SIDE", str(key))
            sides[key] = item
            if item["proposed_membership"] in {"unresolved", "conflict"}:
                unresolved.add(mid)
    return sides, unresolved


def apply_review(rows, sides, approved, approval_id):
    by_id = {r["match_id"]: r for r in rows}
    ensure(len(by_id) == len(rows), "REVIEW_OVERLAY_DUPLICATE", "Duplicate match ID")
    ensure(approved <= set(by_id), "REVIEW_APPROVAL_UNKNOWN_MATCH", "Unknown approved match")
    for (mid, tid), item in sides.items():
        ensure(mid in by_id and by_id[mid]["in_previous_study"] == "true", "REVIEW_OUTSIDE_STUDY", mid)
        ensure(any(by_id[mid][s + "_source_team_id"] == tid and
                   by_id[mid][s + "_source_label"] == item["source_team_label"] for s in ("home", "away")),
               "REVIEW_SIDE_MISMATCH", mid)
    changed, decisions, result = [], [], []
    for original in rows:
        row = dict(original)
        mid = row["match_id"]
        states = []
        touched = mid in approved or any((mid, row[s + "_source_team_id"]) in sides for s in ("home", "away"))
        if touched:
            ensure(row["in_previous_study"] == "true", "REVIEW_OUTSIDE_STUDY", mid)
            for s in ("home", "away"):
                tid = row[s + "_source_team_id"]
                item = sides.get((mid, tid))
                proposed = item["proposed_membership"] if item else "unchanged"
                adopted = "member" if mid in approved else proposed
                if adopted in {"member", "non_member"}:
                    row[s + "_status"] = "conditional_member" if adopted == "member" else "nonmember_before_admission"
                    row[s + "_evidence_id"] = approval_id
                    row[s + "_reason"] = ("User-attested inclusion of this match in current study; external review material not attached"
                                           if mid in approved else "Review suggestion accepted by project owner for this study; not a newly published FIFA record")
                    decisions.append(dict(match_id=mid, source_team_id=tid, source_team_label=row[s + "_source_label"],
                                          assessment_id=item["assessment_id"] if item else "", proposed_membership=proposed,
                                          adopted_membership=adopted, approval_id=approval_id,
                                          basis="user_match_inclusion" if mid in approved else "user_acceptance_of_review_suggestion"))
                states.append(row[s + "_status"])
            if "nonmember_before_admission" in states:
                state, disposition = "nonmember_evidence", "excluded_by_membership_evidence"
            elif states == ["conditional_member", "conditional_member"]:
                state, disposition = "conditional_both_members", "retained"
            else:
                state, disposition = "pending", "quarantined_pending"
            row.update(membership_status=state, change_from_previous_study=disposition,
                       eligible_under_provisional_policy="true" if disposition == "retained" else "false")
            if any(original[k] != row[k] for k in row):
                changed.append(dict(match_id=mid, old_membership_status=original["membership_status"],
                                    new_membership_status=state, old_disposition=original["change_from_previous_study"],
                                    new_disposition=disposition, user_match_approval=mid in approved))
        result.append(row)
    ensure(all(by_id[mid]["in_previous_study"] == "true" for mid in approved), "REVIEW_APPROVAL_SCOPE", "Approval outside study")
    ensure(all(r["eligible_under_provisional_policy"] == "true" for r in result if r["match_id"] in approved),
           "REVIEW_APPROVAL_NOT_APPLIED", "All approved matches must be included")
    return result, sorted(decisions, key=lambda r: (r["match_id"], r["source_team_id"])), changed


def build(root, relative):
    config = load_json(safe(root, relative))
    verify_identity(root, config["base_identity_manifest"])
    base = load_json(safe(root, config["base_identity_manifest"]))
    inputs = dict(base["inputs"])
    for p in [relative, config["base_identity_manifest"], *base["outputs"]]:
        inputs[p] = file_hash(safe(root, p))
    sides, unresolved = effective_reviews(root, config, inputs)
    approval = load_json(safe(root, config["approval"]))
    inputs[config["approval"]] = file_hash(safe(root, config["approval"]))
    ensure(approval["include_all_unresolved_matches"] is True and approval["accept_other_effective_suggestions"] is True
           and approval["evidence_status"] == "user_attested_not_archived" and approval["review_date"] == "2026-10-25",
           "REVIEW_APPROVAL_INVALID", "Explicit user study approval required")
    ensure(len(unresolved) == approval["approved_match_count"] == 117, "REVIEW_APPROVAL_SCOPE_CHANGED", "Approval set changed")
    op = next(p for p in base["outputs"] if p.endswith("/match_identity.csv"))
    _, original = read_csv(safe(root, op), MATCH_FIELDS)
    rows, decisions, changes = apply_review(original, sides, unresolved, approval["approval_id"])
    for row in rows:
        row["policy_id"] = "user-reviewed-study-20261025-v1"
    counts = dict(clean_matches=len(rows), previous_study_matches=sum(r["in_previous_study"] == "true" for r in rows),
                  membership_status=dict(Counter(r["membership_status"] for r in rows)),
                  study_disposition=dict(Counter(r["change_from_previous_study"] for r in rows if r["in_previous_study"] == "true")),
                  user_approved_matches=len(unresolved), changed_matches=len(changes))
    ensure(counts["study_disposition"].get("quarantined_pending", 0) == 0, "REVIEW_STUDY_PENDING", "Study decisions incomplete")
    sources = {**base["code_hashes"], "scripts/adopt_membership_reviews.py": file_hash(root / "scripts/adopt_membership_reviews.py")}
    identity = "identity-reviewed-" + digest(json_bytes(dict(inputs=inputs, code=sources)))[:20]
    folder = safe(root, "data/processed/team_identity/" + identity)
    policy = load_json(safe(root, next(p for p in base["outputs"] if p.endswith("/population_policy.json"))))
    policy.update(policy_id="user-reviewed-study-20261025-v1", approval_id=approval["approval_id"],
                  review_scope="Previous 1980-2024 non-neutral study candidates only", final_release_allowed=False,
                  user_approved_unresolved_matches=117,
                  note="Current study inclusion/exclusion is owner-accepted; no fabricated FIFA historical events or Elo identities")
    artifacts = {}
    for name in ("association_registry.csv", "label_crosswalk.csv", "historical_exceptions.json"):
        old = next(p for p in base["outputs"] if p.endswith("/" + name))
        artifacts[name] = safe(root, old).read_bytes()
    artifacts.update({"match_identity.csv": csv_bytes(MATCH_FIELDS, rows), "population_policy.json": json_bytes(policy),
                      "adopted_decisions.csv": csv_bytes(DECISION_FIELDS, decisions),
                      "membership_changes.csv": csv_bytes(CHANGE_FIELDS, sorted(changes, key=lambda r: r["match_id"])),
                      "user_approval.json": json_bytes(dict(approval, approved_match_ids=sorted(unresolved))),
                      "checks.json": json_bytes(dict(passed=True, counts=counts, full_history_verified=False)),
                      "data_dictionary.md": ("# User-reviewed study membership overlay\n\n"
                         "Same match_identity columns as the prior FIFA-year overlay; raw results and source labels unchanged.\n"
                         "conditional_both_members means eligible under the owner-accepted study policy, not complete official historical proof.\n"
                         "nonmember_evidence and nonmember_before_admission are legacy contract names also used for review-based exclusions.\n"
                         "Read reason/evidence_id and adopted_decisions before interpreting them as dated FIFA events.\n"
                         "The 117 match inclusions are user-attested; external supporting material was not attached.\n"
                         "fifa_code can be blank for reviewed historical labels; no synthetic codes or identity mergers.\n"
                         "history exceptions describe inherited source context; adopted_decisions is the explicit scoped override.\n"
                         "full_history_verified remains false; other clean records and Elo history are not covered by this approval.\n"
                         "CSV: UTF-8 BOM, LF. Boolean text is true/false. No score, venue, date or raw record correction.\n").encode("utf-8")})
    for p, h in {**inputs, **sources}.items():
        ensure(file_hash(safe(root, p)) == h, "REVIEW_INPUT_CHANGED", p)
    if folder.exists():
        return dict(verify_identity(root, (folder / "identity_manifest.json").relative_to(root).as_posix()),
                    manifest=(folder / "identity_manifest.json").relative_to(root).as_posix(), counts=counts)
    folder.mkdir(parents=True, exist_ok=False)
    outputs = {}
    for name, content in artifacts.items():
        p = folder / name
        with p.open("xb") as stream:
            stream.write(content)
        outputs[p.relative_to(root).as_posix()] = digest(content)
    manifest = dict(schema_version="fifa-identity-release-v1", status="published_provisional", identity_version=identity,
                    created_at_utc=datetime.now(timezone.utc).isoformat(), data_version=base["data_version"], scope=base["scope"],
                    policy_id=policy["policy_id"], full_history_verified=False, human_review_pending=False,
                    human_review_scope="Owner attestation for the current study candidate population; external evidence not archived",
                    other_population_review_pending=True, input_frozen=False, final_release=False,
                    base_identity_manifest=config["base_identity_manifest"], inputs=inputs, outputs=outputs,
                    code_hashes=sources, counts=counts)
    for p, h in {**inputs, **sources}.items():
        ensure(file_hash(safe(root, p)) == h, "REVIEW_INPUT_CHANGED", p)
    with (folder / "identity_manifest.json").open("xb") as stream:
        stream.write(json_bytes(manifest))
    return dict(identity_version=identity, manifest=(folder / "identity_manifest.json").relative_to(root).as_posix(), counts=counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/membership_review_adoption.json")
    args = parser.parse_args()
    print(json.dumps(build(ROOT, args.config), ensure_ascii=True))
