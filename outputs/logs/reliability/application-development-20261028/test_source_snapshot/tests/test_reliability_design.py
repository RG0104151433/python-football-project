"""Hand-computable hazards in the Q4 target/design interface; no CI tests."""
from fractions import Fraction
import numpy as np
import pytest

from src.reliability.design import DesignError, competition_context, compile_components, numerical_row_rank, shared_pair_counts
from scripts.audit_reliability_design import select_component_indices


def component(ids, q=Fraction(1), sign=1, cell="toy"):
    return dict(indices=ids, q_numerator=q.numerator, q_denominator=q.denominator,
                multiplier=sign, cell_id=cell)


@pytest.mark.parametrize("wins,expected", [([1, 0, 0], Fraction(1, 3)), ([1, 1, 1], Fraction(1)), ([0, 0, 0], Fraction(0))])
def test_direct_probability_retains_draws_and_losses(wins, expected):
    facts = [dict(home_win=y) for y in wins]
    a, exact, missing = compile_components(facts, [component([0, 1, 2])])
    assert not missing and exact == expected
    assert np.allclose(a, [1/3, 1/3, 1/3])


def test_unequal_cell_sizes_use_reference_not_equal_matches():
    facts = [dict(home_win=y) for y in [1, 1, 0, 0]]
    a, exact, missing = compile_components(facts, [component([0], Fraction(1, 2)), component([1, 2, 3], Fraction(1, 2))])
    assert not missing and exact == Fraction(2, 3)
    assert np.allclose(a, [1/2, 1/6, 1/6, 1/6])


@pytest.mark.parametrize("q,available", [(Fraction(1, 2), False), (Fraction(0), True)])
def test_missing_layer_positive_and_zero_reference_differ(q, available):
    a, exact, missing = compile_components([dict(home_win=1)], [component([0]), component([], q, cell="missing")])
    assert (a is not None) == available
    assert missing == ([] if available else ["missing"])
    if not available:
        assert exact is None


def test_raw_adjusted_change_combines_shared_match_coefficients():
    facts = [dict(home_win=y) for y in [1, 0, 1, 0]]
    raw = [component([0, 1]), component([2, 3], sign=-1)]
    adjusted = [component([0], Fraction(1, 4)), component([1], Fraction(3, 4)),
                component([2], Fraction(1, 2), -1), component([3], Fraction(1, 2), -1)]
    inverse = [dict(p, multiplier=-p["multiplier"]) for p in adjusted]
    a, exact, missing = compile_components(facts, raw + inverse)
    assert not missing and exact == Fraction(1, 4)
    assert np.allclose(a, [.25, -.25, 0, 0])
    assert abs(a.sum()) < 1e-15


def test_reverse_fixtures_count_both_shared_teams_without_double_counting_pairs():
    facts = [dict(home_team_id=h, away_team_id=a) for h, a in [("A", "B"), ("B", "A"), ("A", "C"), ("D", "E")]]
    counts = shared_pair_counts(facts)
    assert counts["all_match_pairs"] == 6
    assert counts["sharing_any_team_pairs"] == 3
    assert counts["same_home_pairs"] == 1
    assert counts["same_away_pairs"] == 0
    assert counts["cross_role_shared_team_incidents"] == 3
    assert counts["repeated_unordered_pair_match_pairs"] == 1
    assert counts["max_match_dependency_degree"] == 2


def test_overlap_not_replication_and_three_group_contrasts_have_rank_two():
    a = np.array([[1., -1, 0], [0, 1, -1], [1, 0, -1], [1, -1, 0]])
    assert numerical_row_rank(a) == 2


def test_signed_coefficients_do_not_imply_negative_probabilities():
    facts = [dict(home_win=0), dict(home_win=1)]
    a, exact, missing = compile_components(facts, [component([0]), component([1], sign=-1)])
    assert not missing and exact == -1
    assert a.tolist() == [1., -1.]


def test_competition_join_uses_provenance_and_never_invents_edition():
    raw = [dict(date="2000-01-01", home_score="1", away_score="0", city="X", country="Y", neutral="FALSE", tournament="Cup")]
    fact = {k: raw[0][k] for k in ("date", "home_score", "away_score", "city", "country")}
    fact.update(match_id="one", source_record_id="results:abc:1", tournament_group="non_friendly", year="2000")
    joined = competition_context([fact], raw, "abc")[0]
    assert joined["tournament_name"] == "Cup" and joined["edition_id"] == joined["round_id"] == ""
    with pytest.raises(DesignError, match="source identity"):
        competition_context([fact], raw, "different")
    with pytest.raises(DesignError, match="join failed"):
        competition_context([dict(fact, date="2001-01-01")], raw, "abc")


@pytest.mark.parametrize("recipe,expected", [
    ({"scope": "era", "period_id": "1980s", "tournament_group": "friendly"}, [0]),
    ({"scope": "rolling", "period_id": "1981_1990", "tournament_group": "friendly"}, [1]),
    ({"scope": "overall", "period_id": "all", "tournament_group": "friendly"}, [0, 1]),
])
def test_independent_auditor_respects_scope_not_only_explicit_era_column(recipe, expected):
    facts = [dict(year="1980", era="1980s", tournament_group="friendly"),
             dict(year="1990", era="1990s", tournament_group="friendly"),
             dict(year="1985", era="1980s", tournament_group="non_friendly")]
    assert select_component_indices(facts, range(3), recipe) == expected
