"""Preview protects frozen facts and fails explicitly on unsafe proposals."""
import copy
import json
from pathlib import Path
import shutil

import pytest

from scripts.audit_team_identity import json_bytes, run_inventory
from scripts.plan_team_identity import (REVIEW_FIELDS, run_plan, validate_proposals, verify_plan)
from src.data_contract import PrepError, csv_bytes
from test_team_identity_inventory import prepared_project, records


def example():
    data = records()
    review = [dict(source_team_id=r["team_id"], source_team_label=r["canonical_name"],
                   current_observation="unresolved", observation_date="", evidence_ids="[]",
                   historical_status="pending", population_status="pending", checked_by="AI",
                   independently_reviewed_by="", notes="Unknown historical population") for r in data["registry"]]
    evidence = [dict(evidence_id="e1", title="Synthetic source", url="https://example.org/fixture",
                     accessed_on="2026-10-24", locator="Synthetic case", claim="Fixture only",
                     limits="No real-world claim", capture_kind="test")]
    decision = dict(decision_id="d1", action="exclude_match", status="proposed", source_team_id="team:alpha",
                    start="1980-01-01", end="1980-01-01", match_id=data["clean"][0]["match_id"],
                    expected={k: data["clean"][0].get(k, "") for k in (
                        "date", "home_team", "away_team", "home_score", "away_score", "country", "is_neutral")},
                    annotation="Proposed boundary", evidence_ids=["e1"], reason="Fixture scope",
                    checked_by="AI", independently_reviewed_by="")
    # Inventory fixture omits scores; complete them without changing its semantics.
    for r in data["clean"]:
        r["home_score"], r["away_score"] = "1", "0"
    decision["expected"]["home_score"], decision["expected"]["away_score"] = "1", "0"
    policy = dict(schema_version="team-identity-policy-draft-v1", policy_id="test-draft", status="proposed",
                  unresolved="block_publication", scope=data["scope"], population_question="Synthetic boundary?")
    return data, review, evidence, [decision], policy


def test_preview_counts_unique_matches_without_mutating_facts_or_approving_population():
    args = example()
    before = copy.deepcopy(args)
    impacts, blockers, _, summary = validate_proposals(*args)
    assert args == before
    assert summary["scenario_remaining_study_matches"] == 1
    assert summary["decisions_applied"] == 0 and summary["ready_for_publication"] is False
    assert len(blockers) == 3 and summary["publication_blocking_study_labels"] == 2
    assert impacts[0]["facts_changed"] is False and impacts[0]["requires_new_population"] is True


@pytest.mark.parametrize("mutation,code", [
    ("score", "PLAN_OLD_VALUE_MISMATCH"), ("evidence", "PLAN_EVIDENCE_REFERENCE_INVALID"),
    ("missing_team", "PLAN_REVIEW_COVERAGE_INVALID"), ("reversed", "PLAN_INTERVAL_INVALID"),
    ("merge", "PLAN_ACTION_UNSUPPORTED"), ("duplicate", "PLAN_DECISION_DUPLICATE"),
    ("no_target", "PLAN_MATCH_NOT_FOUND"), ("approved", "PLAN_DECISION_INVALID"),
    ("partial_expected", "PLAN_OLD_VALUE_REQUIRED"), ("policy", "PLAN_POLICY_INVALID"),
])
def test_invalid_proposals_fail(mutation, code):
    args = example()
    data, review, evidence, decisions, policy = args
    d = decisions[0]
    if mutation == "score": d["expected"]["home_score"] = "99"
    elif mutation == "evidence": d["evidence_ids"] = ["missing"]
    elif mutation == "missing_team": review.pop()
    elif mutation == "reversed": d["end"] = "1979-12-31"
    elif mutation == "merge": d["action"] = "merge_entities"
    elif mutation == "duplicate": decisions.append(copy.deepcopy(d))
    elif mutation == "no_target": d["match_id"] = "missing"
    elif mutation == "approved": d["status"] = "approved"
    elif mutation == "partial_expected": d["expected"].pop("country")
    else: policy["unresolved"] = "include"
    with pytest.raises(PrepError) as exc:
        validate_proposals(*args)
    assert exc.value.code == code


def test_historical_annotation_inclusive_endpoints_and_overlap_rejection():
    args = example()
    d = args[3][0]
    d.update(action="historical_annotation", match_id="", expected={})
    assert len(validate_proposals(*args)[0]) == 1
    args[3].append(dict(d, decision_id="d2"))
    with pytest.raises(PrepError) as exc:
        validate_proposals(*args)
    assert exc.value.code == "PLAN_INTERVAL_CONFLICT"


def test_end_to_end_preview_repeats_verifies_and_refuses_changed_old_values(prepared_project):
    root, _, _ = prepared_project
    source = Path(__file__).resolve().parents[1] / "scripts/plan_team_identity.py"
    shutil.copyfile(source, root / "scripts/plan_team_identity.py")
    inventory = run_inventory(root, "config/team_identity.json")
    args = example()
    # Use the actual pipeline IDs and facts rather than the synthetic rawsha IDs.
    inv_config = json.loads((root / "config/team_identity.json").read_text())
    with (root / f"data/processed/{inv_config['data_version']}/matches_clean.csv").open(encoding="utf-8-sig") as f:
        import csv
        match = next(r for r in csv.DictReader(f) if r["date"] == "1980-01-01")
    d = args[3][0]
    d["match_id"] = match["match_id"]
    d["expected"] = {k: match[k] for k in d["expected"]}
    folder = root / "review"
    folder.mkdir()
    (folder / "labels.csv").write_bytes(csv_bytes(REVIEW_FIELDS, args[1]))
    (folder / "evidence.json").write_bytes(json_bytes(dict(schema_version="identity-evidence-v1", evidence=args[2])))
    (folder / "decisions.json").write_bytes(json_bytes(dict(schema_version="identity-decisions-draft-v1", decisions=args[3])))
    (folder / "policy.json").write_bytes(json_bytes(args[4]))
    (folder / "directory.json").write_bytes(json_bytes(dict(schema_version="identity-directory-observations-v1",
        alias_status="manual_candidate_not_independently_verified", fifa_directory_names=[], alias_candidates={})))
    config = dict(schema_version="team-identity-plan-config-v1", inventory_config="config/team_identity.json",
                  inventory_run=inventory["run_manifest"], review="review/labels.csv", evidence="review/evidence.json",
                  decisions="review/decisions.json", policy="review/policy.json", directory_observations="review/directory.json")
    (root / "plan.json").write_bytes(json_bytes(config))
    a, b = run_plan(root, "plan.json"), run_plan(root, "plan.json")
    assert a["plan_id"] == b["plan_id"] and a["run_manifest"] != b["run_manifest"]
    m1 = json.loads((root / a["run_manifest"]).read_text())
    m2 = json.loads((root / b["run_manifest"]).read_text())
    assert {Path(p).name: h for p, h in m1["outputs"].items()} == {Path(p).name: h for p, h in m2["outputs"].items()}
    assert verify_plan(root, a["run_manifest"])["passed"]
    target = root / next(p for p in m1["outputs"] if p.endswith("match_impacts.csv"))
    assert target.read_bytes().startswith(b"\xef\xbb\xbf") and b"\r\n" not in target.read_bytes()
    target.write_bytes(b"tampered")
    with pytest.raises(PrepError) as exc:
        verify_plan(root, a["run_manifest"])
    assert exc.value.code == "PLAN_HASH_MISMATCH"
    assert verify_plan(root, b["run_manifest"])["passed"]
    d["expected"]["home_score"] = "999"
    (folder / "decisions.json").write_bytes(json_bytes(dict(schema_version="identity-decisions-draft-v1", decisions=args[3])))
    count_before = len(list((root / "outputs/logs/team_identity").glob("plan-*")))
    with pytest.raises(PrepError) as exc:
        run_plan(root, "plan.json")
    assert exc.value.code == "PLAN_OLD_VALUE_MISMATCH"
    assert len(list((root / "outputs/logs/team_identity").glob("plan-*"))) == count_before
