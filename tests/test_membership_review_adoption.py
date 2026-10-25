"""Study approval must be scoped and take precedence without rewriting facts."""
import pytest

from scripts.adopt_membership_reviews import apply_review
from src.data_contract import PrepError


def match(mid="m1", in_study="true"):
    return dict(match_id=mid, date="1992-06-01", in_previous_study=in_study,
                home_source_team_id="a", away_source_team_id="b",
                home_source_label="Alpha", away_source_label="Beta",
                home_status="pending", away_status="conditional_member",
                home_evidence_id="old", away_evidence_id="old",
                home_reason="old", away_reason="old", membership_status="pending",
                change_from_previous_study="quarantined_pending", eligible_under_provisional_policy="false")


def suggestion(status="non_member", label="Alpha"):
    return dict(proposed_membership=status, source_team_label=label, assessment_id="test-advice")


def test_approval_overrides_exclusion_for_complete_match_and_preserves_source():
    row = match()
    rows, decisions, changes = apply_review([row], {("m1", "a"): suggestion()}, {"m1"}, "human-approval")
    assert rows[0]["eligible_under_provisional_policy"] == "true"
    assert rows[0]["membership_status"] == "conditional_both_members"
    assert {d["adopted_membership"] for d in decisions} == {"member"}
    assert all(rows[0][k] == row[k] for k in ("date", "match_id", "home_source_label", "away_source_label"))
    assert row["membership_status"] == "pending"
    assert changes[0]["old_disposition"] == "quarantined_pending"


def test_one_nonmember_excludes_match_and_untouched_population_stays_unchanged():
    outside = match("outside", "false")
    rows, _, _ = apply_review([match(), outside], {("m1", "a"): suggestion()}, set(), "approval")
    assert rows[0]["change_from_previous_study"] == "excluded_by_membership_evidence"
    assert rows[1] == outside


@pytest.mark.parametrize("rows,sides,approved", [
    ([match()], {}, {"unknown"}),
    ([match(in_study="false")], {}, {"m1"}),
    ([match(in_study="false")], {("m1", "a"): suggestion()}, set()),
    ([match()], {("m1", "a"): suggestion(label="Wrong")}, set()),
    ([match(), match()], {}, set()),
])
def test_invalid_scope_label_or_duplicate_fails(rows, sides, approved):
    with pytest.raises(PrepError):
        apply_review(rows, sides, approved, "approval")
