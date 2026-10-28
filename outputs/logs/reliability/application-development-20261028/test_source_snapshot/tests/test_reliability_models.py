"""Hand distributions and independent numerical calculations for new routes."""
import itertools
import math

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import ndtr

from src.reliability.models import (FixedDesign, association_objective, bvn_cdf,
    clipped_intervals, coloring_valid, color_constant, correlation_and_gradient,
    exact_mc_limits, fit_margin, generate, graph_bounds, greedy_colors, keyed_rng,
    pair_metadata, scenario_from_fit, select_pairs)


def toy():
    facts=[]
    for i,(h,a,day) in enumerate([(0,1,1),(1,2,1),(0,2,2),(2,0,10)]):
        facts.append(dict(match_id=str(i),date=f"1980-01-{day:02}",year="1980",era="1980s",
                          tournament_group="friendly",home_team_id=str(h),away_team_id=str(a)))
    return FixedDesign(facts, [[.25]*4,[1,0,-1,0],[0,0,0,0]], ["mean","difference","zero"], {"F":[0,1,2]}, [])


@pytest.mark.parametrize("h,k,r", [(0,0,.8),(0,1,-.8),(1,0,.4),(.4,-.9,.7),(-3,-2,-.8),(4,-5,.5),(.3,2,0),(-1,-2,.95)])
def test_bivariate_probability_independent_positive_integral(h,k,r):
    ref,err=quad(lambda x: math.exp(-x*x/2)/math.sqrt(2*math.pi)*ndtr((k-r*x)/math.sqrt(1-r*r)),
                 -np.inf,h,epsabs=1e-12,epsrel=1e-11)
    assert err<1e-10
    assert abs(float(bvn_cdf(h,k,r))-ref)<1e-10


def test_four_quadrants_sum_to_one():
    for h,k,r in itertools.product([-.9,0,.8],[-1,0,1.2],[-.9,0,.9]):
        probs=[float(bvn_cdf(sh*h,sk*k,sh*sk*r)) for sh,sk in itertools.product([-1,1],repeat=2)]
        assert min(probs)>=0
        assert abs(sum(probs)-1)<1e-12


def test_analytic_correlation_gradient_matches_finite_difference():
    d=toy();pairs=pair_metadata(d,np.array([0,0,1]),np.array([1,2,3]))
    par=np.r_[.2,.1,.1,.2,np.log(365),np.log(30)]
    _,grad=correlation_and_gradient(par,pairs)
    for j in range(6):
        delta=np.eye(6)[j]*1e-5
        numeric=(correlation_and_gradient(par+delta,pairs)[0]-correlation_and_gradient(par-delta,pairs)[0])/2e-5
        np.testing.assert_allclose(grad[:,j],numeric,atol=1e-9)


def test_pair_likelihood_gradient_matches_finite_difference():
    d=toy();pairs=pair_metadata(d,np.array([0,0,1]),np.array([1,2,3]))
    fun=association_objective(d,pairs,np.array([.3,.5,.7,.6]),np.array([1,0,1,0]))
    par=np.r_[.2,.1,.1,.2,np.log(365),np.log(30)]
    _,g=fun(par)
    for j in range(6):
        delta=np.eye(6)[j]*1e-5
        num=(fun(par+delta)[0]-fun(par-delta)[0])/2e-5
        assert abs(num-g[j])<1e-8


@pytest.mark.parametrize("L", [0,1,90,"all_dependent"])
def test_graph_both_roles_equal_dates_and_logical_clipping(L):
    d=toy();colors=greedy_colors(d,L)
    assert coloring_valid(d,colors,L)
    # AB and BC share a team across roles and must differ, even at L=0.
    assert colors[0]!=colors[1]
    g=graph_bounds(d,L,True)
    assert np.all(g["C"]<=g["C_baseline"]+1e-12)
    assert g["half"][2]==0
    lo,hi=clipped_intervals(d,d.apply([1,0,1,0]),g["half"])
    assert np.all(lo>=d.lo) and np.all(hi<=d.hi)
    if L=="all_dependent":
        np.testing.assert_allclose(g["C"],d.span**2)
        np.testing.assert_allclose(lo,d.lo);np.testing.assert_allclose(hi,d.hi)


def test_cell_separation_is_failure_not_optimizer_success():
    d=toy();base=fit_margin(d,np.zeros(4))
    assert not base["ok"] and base["status"]=="separated_unpenalized_cell"
    revised=fit_margin(d,np.zeros(4),cell_ridge=.5)
    assert revised["ok"] and revised["diagnostic"]["separated_cells"]==[0]


def test_seeded_pair_selection_does_not_use_outcome():
    d=toy();a=select_pairs(d);b=select_pairs(d)
    assert a["sha256"]==b["sha256"] and len(a["i"])==6


def test_model_margins_and_signed_correlation_simulation():
    d=toy();par=np.r_[.8,0,0,0,np.log(3650),np.log(365)]
    s=scenario_from_fit(par)
    y=generate(d,np.full(4,.5),s,20000,keyed_rng("unit",20261028))
    assert np.max(abs(y.mean(axis=0)-.5))<.016
    # AB vs BC: one common team with opposite signs, latent rho=-.4.
    expected=math.asin(-.4)/(2*math.pi)
    empirical=np.mean((y[:,0]-.5)*(y[:,1]-.5))
    assert abs(empirical-expected)<.008
    assert np.all(d.apply(y)[:,2]==0)


def test_cp_endpoints_and_finite_reference_rank():
    assert exact_mc_limits(0,100)["lower99"]==0
    assert exact_mc_limits(100,100)["upper99"]==1
    assert exact_mc_limits(100,100)["lower99"]<.96
    assert math.ceil((199+1)*.95)==190
