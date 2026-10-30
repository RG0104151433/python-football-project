import math
import numpy as np
import pytest
from scipy.special import ndtr
from src.strength_joint.model import Kernel, objective, slopes
from src.strength_joint.design import Design, relation
from src.strength_joint.contract import validate_rows
from src.strength_joint.validation import before_day
from src.strength.collapsed_jump import CollapsedJumpFilter


def rows():
    output = []
    for i in range(24):
        output.append(dict(match_id=str(i), date="2000-01-02", prediction_cutoff="2000-01-01",
            home_win=i % 2, outcome="home" if i % 2 else "draw", era="1980s",
            tournament_group="friendly" if i % 3 else "non_friendly", home_region="150", away_region="150",
            home_unit="154" if i % 4 else "039", away_unit="039" if i % 5 else "154",
            strength_difference=(i - 12) / 8, strength_difference_base_variance=.3,
            home_jump_intensity=.03, away_jump_intensity=.07, jump_scale_sd=1.2,
            strength_difference_variance=.444))
    return output


def test_normal_integral_and_zero_slope():
    data = dict(mu=np.array([-.7, .4]), base=np.array([.8, 1.2]), nu_h=np.zeros(2), nu_a=np.zeros(2), sd=np.ones(2))
    kernel = Kernel(data=data)
    eta = np.array([.2, -.1]); b = .9
    assert np.max(abs(kernel.evaluate(eta, b) - ndtr((eta + b * data["mu"]) / np.sqrt(1 + b * b * data["base"])))) < 1e-14
    assert np.max(abs(kernel.evaluate(eta, 0) - ndtr(eta))) < 1e-14


def test_poisson_shape_is_not_total_variance_normal():
    data = dict(mu=np.array([1.4]), base=np.array([.2]), nu_h=np.array([.2]), nu_a=np.array([.1]), sd=np.array([2.]))
    p = Kernel(data=data).evaluate(np.array([.3]), 1.)
    q = Kernel(data=data, mode="total_normal").evaluate(np.array([.3]), 1.)
    assert abs(p[0] - q[0]) > .01


@pytest.mark.parametrize("model", ["M3_nested", "M4_type_slope"])
def test_gradient_including_distinct_friendly_slope(model):
    rs = rows(); d = Design(rs); x, names = d.matrix(rs, model); s = slopes(rs, model)
    theta = np.r_[np.linspace(-.1, .1, len(names)), np.linspace(math.log(.7), math.log(1.2), s.shape[1])]
    k = Kernel(rs); y = np.array([r["home_win"] for r in rs])
    _, grad = objective(theta, x, k, y, s)
    fd = []
    for j in range(len(theta)):
        step = np.zeros(len(theta)); step[j] = 1e-5
        fd.append((objective(theta + step, x, k, y, s)[0] - objective(theta - step, x, k, y, s)[0]) / 2e-5)
    assert np.max(abs(grad - fd)) < 1e-7


def test_within_parent_coding_weighted_zero_and_legal_scenario():
    rs = rows(); d = Design(rs); x, names = d.matrix(rs, "M3_nested")
    for i, name in enumerate(names):
        if ":within:" in name:
            assert abs(x[:, i].sum()) < 1e-12
    new = d.set_home_unit(dict(rs[0], home_region="142"), "039")
    assert new["home_region"] == "150"
    assert relation(new) == "same_region_other_unit"
    assert relation(d.set_away_unit(new, "039")) == "same_unit"


def test_outcomes_do_not_change_design_or_prior_probabilities():
    rs = rows(); other = [dict(r, home_win=1 - r["home_win"], outcome="away") for r in rs]
    d = Design(rs)
    assert np.array_equal(d.matrix(rs, "M5_relation")[0], d.matrix(other, "M5_relation")[0])
    assert np.array_equal(Kernel(rs).evaluate(np.zeros(len(rs)), 1.), Kernel(other).evaluate(np.zeros(len(rs)), 1.))


def test_input_contract_rejects_future_and_inconsistent_distribution():
    rs = rows(); assert validate_rows(rs)
    with pytest.raises(ValueError, match="FUTURE_INFORMATION"):
        validate_rows([dict(rs[0], prediction_cutoff=rs[0]["date"])])
    with pytest.raises(ValueError, match="DISTRIBUTION_FIELDS_MISSING"):
        validate_rows([dict(rs[0], strength_difference_variance=4.)])


def test_extreme_likelihood_is_finite_without_probability_clipping():
    data = dict(mu=np.array([100., -100.]), base=np.array([.3, .2]), nu_h=np.zeros(2), nu_a=np.zeros(2), sd=np.ones(2))
    logp, ge, gb = Kernel(data=data).evaluate(np.zeros(2), 1., np.array([0., 1.]))
    assert np.isfinite(logp).all() and np.isfinite(ge).all() and np.isfinite(gb).all()
    assert min(logp) < -1000


def test_feedback_query_matches_real_filter_and_does_not_update():
    p = dict(q=.03, delta=.4, alpha=.65, epsilon=.05, home_q=.005, jump_rate=.08, jump_sd=1.2)
    num = dict(ep_max_iter=300, ep_tolerance=1e-6, rank_tolerance=1e-12, ep_damping=.5, poisson_tail_tolerance=1e-12, psd_tolerance=1e-8)
    engine = CollapsedJumpFilter({"a", "b", "c"}, p, num)
    first = dict(match_id="1", home="a", away="b", venue=1, friendly=True, outcome=0)
    engine.day("2000-01-01", [first])
    batch = [dict(first, match_id="2", outcome=2), dict(first, match_id="3", away="c", outcome=1)]
    mean = engine.mean.copy(); cov = engine.cov.copy()
    before = before_day(engine, "2001-01-01", batch)
    assert np.array_equal(mean, engine.mean) and np.array_equal(cov, engine.cov)
    scored = engine.day("2001-01-01", batch)
    for r, q in zip(before, scored):
        assert abs(r["strength_difference"] - q["difference"]) < 1e-12
        assert abs(r["strength_difference_variance"] - q["difference_variance"]) < 1e-12
