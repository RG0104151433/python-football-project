"""Independent properties of numerical state-mixture reduction."""
import json
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import logsumexp

from src.strength.filter import Component, StrengthFilter
from src.strength.reduction import merge, moments, runnalls, cluster, ReducedStrengthFilter
from src.strength.io import config
from src.strength.experiment import params


def mixture():
    return [Component(.2, np.array([-1., .3]), np.array([[.5, .1], [.1, .8]]), ("a",)),
            Component(.3, np.array([0., -.3]), np.array([[.7, -.2], [-.2, .6]]), ("b",)),
            Component(.5, np.array([1., .8]), np.array([[1., .1], [.1, .4]]), ("c",))]


@pytest.mark.parametrize("method", ["runnalls", "cluster"])
def test_mass_full_covariance_and_mean_preserved(method):
    components = mixture()
    out, _ = (runnalls(components, 2) if method == "runnalls" else cluster(components, 2))
    assert len(out) <= 2
    assert abs(sum(c.weight for c in out)-1) < 1e-12
    a, b = moments(components), moments(out)
    np.testing.assert_allclose(a[0], b[0], atol=1e-12)
    np.testing.assert_allclose(a[1], b[1], atol=1e-12)
    assert all(np.linalg.eigvalsh(c.cov).min() > 0 for c in out)


def test_bound_exceeds_independent_numeric_scalar_KL():
    original = [Component(.4, np.array([-1.]), np.array([[.5]]), ()),
                Component(.6, np.array([.8]), np.array([[.9]]), ())]
    reduced, bound = runnalls(original, 1)
    c = reduced[0]

    def integrand(x):
        log_terms = [np.log(a.weight)-.5*np.log(2*np.pi*a.cov[0,0])-
                     (x-a.mean[0])**2/(2*a.cov[0,0]) for a in original]
        lf = logsumexp(log_terms)
        lg = -.5*np.log(2*np.pi*c.cov[0,0])-(x-c.mean[0])**2/(2*c.cov[0,0])
        return np.exp(lf)*(lf-lg)

    actual = quad(integrand, -15, 15, epsabs=1e-11)[0]
    assert actual >= -1e-12 and actual <= bound+1e-10


def test_identical_components_merge_without_invented_uncertainty():
    m = np.array([1., 2.])
    c = np.array([[1., .2], [.2, .8]])
    group = [Component(.5, m.copy(), c.copy(), ()), Component(.5, m.copy(), c.copy(), ())]
    out, bound = runnalls(group, 1)
    np.testing.assert_allclose(out[0].mean, m)
    np.testing.assert_allclose(out[0].cov, c)
    assert bound < 1e-12


@pytest.mark.parametrize("method", ["runnalls", "cluster", "hybrid"])
def test_reduced_filter_same_day_and_restore(method):
    cfg = config()
    numerical = {**cfg["numerics"], "reducer": method, "max_components": 3}
    e = ReducedStrengthFilter(["A", "B", "C"], params(cfg, {"id": "both"}), numerical)
    first = dict(match_id="a", home="A", away="B", outcome=2, venue=1, friendly=False)
    e.day("1960-01-01", [first])
    e.day("1960-03-01", [first])
    f = ReducedStrengthFilter.restore(json.loads(json.dumps(e.state())))
    batch = [dict(first, match_id="b"), dict(first, match_id="c", home="C", away="A", outcome=0)]
    p, q = e.day("1960-04-01", batch), f.day("1960-04-01", batch[::-1])
    assert p == q
    assert e.diagnostics[-1]["moment_error"] < 1e-10
    assert e.diagnostics[-1]["approximate_posterior_pruned_mass"] == 0
