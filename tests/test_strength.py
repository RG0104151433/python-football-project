"""Meaningful mathematical, chronology and numerical tests for the pilot."""
import copy
import json
import math

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import ndtr

from src.strength.filter import (StrengthFilter, outcome_moments, probabilities, batch_update,
                                  joint_quadrature, NumericalFailure)
from src.strength.io import config
from src.strength.experiment import params, baseline, score
from src.strength.prepare import membership, episode


@pytest.mark.parametrize("outcome", range(3))
@pytest.mark.parametrize("kappa", [1.0, 0.6])
def test_single_match_against_independent_integral(outcome, kappa):
    m, v, delta = 0.7, 0.8, 0.3

    def kernel(x):
        p = [ndtr(x - delta), ndtr(delta - x) - ndtr(-delta - x), ndtr(-delta - x)][outcome]
        return (kappa * p + (1 - kappa) / 3) * math.exp(-(x - m)**2 / (2*v)) / math.sqrt(2*math.pi*v)

    z = quad(kernel, -12, 12, epsabs=1e-12)[0]
    em = quad(lambda x: x * kernel(x), -12, 12, epsabs=1e-12)[0] / z
    ev = quad(lambda x: (x-em)**2 * kernel(x), -12, 12, epsabs=1e-12)[0] / z
    actual = outcome_moments(m, v, outcome, delta, kappa)
    np.testing.assert_allclose(actual[:3], [z, em, ev], atol=1e-10)


def make_engine(candidate="both", numerics=None):
    cfg = config()
    return StrengthFilter(["A", "B", "C"], params(cfg, next(c for c in cfg["pilot"]["candidates"] if c["id"] == candidate)),
                          numerics or cfg["numerics"])


def game(mid="x", outcome=0, home="A", away="B", venue=1):
    return dict(match_id=mid, home=home, away=away, outcome=outcome, venue=venue, friendly=False)


def test_away_victory_learns_both_and_neutral_has_no_home_update():
    e = make_engine("smooth")
    e.day("1960-01-01", [game(outcome=2, venue=0)])
    m = e.components[0].mean
    assert m[0] < 0 < m[1]
    assert m[-1] == 0


def test_role_swap_symmetry():
    e, f = make_engine(), make_engine()
    p = e.day("1960-01-01", [game()])[0]
    q = f.day("1960-01-01", [game(outcome=2, home="B", away="A", venue=-1)])[0]
    np.testing.assert_allclose([p["p_home"], p["p_draw"], p["p_away"]],
                               [q["p_away"], q["p_draw"], q["p_home"]], atol=1e-12)
    np.testing.assert_allclose(e.components[0].mean, f.components[0].mean, atol=1e-12)


def test_current_results_do_not_change_current_predictions():
    e, f = make_engine(), make_engine()
    a = e.day("1960-01-01", [game(outcome=0)])[0]
    b = f.day("1960-01-01", [game(outcome=2)])[0]
    assert [a[k] for k in ("p_home", "p_draw", "p_away")] == [b[k] for k in ("p_home", "p_draw", "p_away")]
    assert e.components[0].mean[0] != f.components[0].mean[0]


def test_same_date_all_predictions_before_joint_update_and_order_invariant():
    batch = [game("a"), game("b", 2, "A", "C")]
    e, f = make_engine(), make_engine()
    p = e.day("1960-01-01", batch)
    q = f.day("1960-01-01", list(reversed(batch)))
    assert p == q
    assert p[0]["home_history"] == p[1]["home_history"] == 0
    assert p[0]["home_mean"] == p[1]["home_mean"] == 0
    np.testing.assert_allclose(e.components[0].cov, f.components[0].cov, atol=1e-12)


def test_checkpoint_roundtrip_continues_same_predictions():
    e = make_engine()
    e.day("1960-01-01", [game()])
    f = StrengthFilter.restore(json.loads(json.dumps(e.state())))
    a = e.day("1960-02-01", [game("z", 1)])
    b = f.day("1960-02-01", [game("z", 1)])
    assert a == b
    assert e.state() == f.state()


def test_inactivity_mean_unchanged_and_variance_increases():
    e = make_engine("smooth")
    e.day("1960-01-01", [game()])
    children, _ = e.advance("1961-01-01", ["A", "B"])
    np.testing.assert_equal(children[0].mean, e.components[0].mean)
    assert children[0].cov[0, 0] > e.components[0].cov[0, 0]


def test_poisson_truncation_and_budget_fail_explicitly():
    e = make_engine()
    e.day("1960-01-01", [game()])
    with pytest.raises(NumericalFailure, match="tail"):
        e.advance("2060-01-01", ["A", "B"])


def test_paths_persist_and_covariance_positive():
    e = make_engine()
    e.day("1960-01-01", [game()])
    for month in range(2, 7):
        e.day(f"1960-{month:02d}-01", [game(str(month), 2)])
    assert any(c.path for c in e.components)
    assert abs(sum(c.weight for c in e.components) - 1) < 1e-12
    assert all(np.linalg.eigvalsh(c.cov).min() > -1e-10 for c in e.components)


@pytest.mark.parametrize("y", [0, 1, 2])
def test_extreme_probabilities_are_finite(y):
    p = probabilities(20, 0.2, 0.3, 0.95)
    assert np.isfinite(p).all() and abs(p.sum() - 1) < 1e-12 and p.min() > 0
    _, m, v, _, _ = outcome_moments(20, 0.2, y, 0.3, 0.95)
    assert math.isfinite(m) and v > 0


def test_duplicate_or_past_day_rejected():
    e = make_engine()
    with pytest.raises(ValueError, match="Duplicate"):
        e.day("1960-01-01", [game(), game()])
    e.day("1960-01-01", [game()])
    with pytest.raises(ValueError, match="Dates"):
        e.day("1960-01-01", [game("z")])


def test_membership_conservative_years_and_exact_dates():
    registry = {"X": {"affiliation_years": "1905, 1950"}}
    assert not membership("1950-09-01", "X", "X", registry, {})[0]
    assert membership("1951-01-01", "X", "X", registry, {})[0]
    assert not membership("1949-01-01", "X", "X", registry, {})[0]
    assert membership("1950-07-01", "X", "X", registry, {"X": "1950-07-01"})[0]


def test_entity_boundary_prevents_unjustified_inheritance():
    windows = {"X": [("1950-01-01", "1960-12-31", "unresolved")]}
    assert episode("X", "team:x", "1960-06-01", windows) != episode("X", "team:x", "1961-01-01", windows)


def test_frequency_baseline_does_not_read_same_day_results():
    a = [dict(match_id="a", date="1960-01-01", outcome=0),
         dict(match_id="b", date="1960-01-01", outcome=2)]
    b = copy.deepcopy(a)
    b[0]["outcome"] = 2
    assert baseline(a)[1]["p_home"] == baseline(b)[1]["p_home"]


def test_joint_ep_reference_in_independent_performance_case():
    cfg = config()
    m, c = np.zeros(4), np.eye(4)
    a = np.array([[1, -1, 0, 0], [0, 0, 1, -1]])
    em, ec, ez, _ = batch_update(m, c, a, [0, 1], [.95, .6], .3, cfg["numerics"])
    rm, rc, rz = joint_quadrature(m, c, a, [0, 1], [.95, .6], .3, 55)
    np.testing.assert_allclose(em, rm, atol=2e-6)
    np.testing.assert_allclose(ec, rc, atol=2e-6)
    assert abs(ez-rz) < 2e-6


def test_joint_ep_permutation_without_sorting():
    cfg = config()
    m, c = np.array([.4, -.1, .2]), np.array([[1., .2, .1], [.2, .8, -.1], [.1, -.1, .5]])
    a = np.array([[1., -1., 1.], [0., 1., 0.]])
    r = batch_update(m, c, a, [0, 2], [.95, .65], .3, cfg["numerics"])
    s = batch_update(m, c, a[::-1], [2, 0], [.65, .95], .3, cfg["numerics"])
    for i in range(3):
        np.testing.assert_allclose(r[i], s[i], atol=1e-10)


def test_invalid_checkpoint_rejected():
    e = make_engine()
    state = e.state()
    state["components"][0]["cov"][0][0] = -1
    with pytest.raises(ValueError, match="covariance"):
        StrengthFilter.restore(state)


def test_poisson_enumerated_weights_and_prior_mean():
    e = make_engine()
    e.day("1960-01-01", [game()])
    children, tail = e.advance("1960-03-01", ["A", "B"])
    assert abs(sum(c.weight for c in children) - 1) < 1e-12
    assert 0 < tail < e.numerics["max_transition_prior_tail"]
    assert all(np.array_equal(c.mean, e.components[0].mean) for c in children)
