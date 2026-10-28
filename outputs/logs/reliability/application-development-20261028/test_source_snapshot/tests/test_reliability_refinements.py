import math
import itertools
import json
from pathlib import Path

import numpy as np
import pytest

from src.reliability.models import keyed_rng,greedy_colors,coloring_valid,color_constant
from src.reliability.refinements import (team_banded,time_daily,coloring_valid_fast,
    weighted_colors,refine_graph,refined_intervals,generate_fast)
from tests.test_reliability_models import toy


def test_banded_recursion_equals_direct_irregular_recursion():
    d=toy();B=7;tau=30;ev=d.team_events
    rng=keyed_rng("banded-unit");raw=rng.normal(size=(ev["n"],B));values=raw.copy()
    for j in range(ev["n"]):
        if ev["prev"][j]>=0:
            rho=math.exp(-ev["gaps"][j]/tau)
            values[j]=rho*values[ev["prev"][j]]+math.sqrt(-math.expm1(-2*ev["gaps"][j]/tau))*raw[j]
    home,away=team_banded(d,B,tau,keyed_rng("banded-unit"))
    np.testing.assert_allclose(home,values[ev["home"]].T,atol=1e-14)
    np.testing.assert_allclose(away,values[ev["away"]].T,atol=1e-14)
    # Shared team on same day is one node, not two independent innovations.
    assert ev["away"][0]==ev["home"][1]


def test_daily_filter_equals_direct_stationary_recursion():
    d=toy();B=7;tau=365;length=int(d.days.max()-d.days.min()+1)
    rng=keyed_rng("daily-unit");initial=rng.normal(size=(B,1));noise=rng.normal(size=(B,length-1))
    values=np.zeros((B,length));values[:,0]=initial[:,0]
    rho=math.exp(-1/tau);sigma=math.sqrt(-math.expm1(-2/tau))
    for j in range(1,length):values[:,j]=rho*values[:,j-1]+sigma*noise[:,j-1]
    fast=time_daily(d,B,tau,keyed_rng("daily-unit"))
    np.testing.assert_allclose(fast,values[:,d.days-d.days.min()],atol=1e-14)


@pytest.mark.parametrize("L",[0,1,7,730])
def test_weighted_colors_and_independent_fast_validator(L):
    d=toy();a=np.array([.2,.1,-.3,.4])
    for reverse in (False,True):
        c=weighted_colors(d,a,L,reverse)
        assert coloring_valid_fast(d,c,L) and coloring_valid(d,c,L)
    bad=np.zeros(4,dtype=int)
    assert not coloring_valid_fast(d,bad,L)


def test_markov_interval_uniform_validity_in_perfect_dependence():
    d=toy();base=dict(C=np.array([1,4,0]),schemes=["singleton"]*3)
    g=refine_graph(d,"all_dependent",base)
    assert g["markov_choice"].all()
    # Any distribution on these binary vectors is allowed, not just independence.
    ys=np.array(list(itertools.product([0,1],repeat=4)),float)
    vals=d.apply(ys)
    for seed in range(30):
        masses=keyed_rng(seed,"markov-check").dirichlet(np.full(16,.3))
        truth=masses@vals;coverage=0
        for v,mass in zip(vals,masses):
            lo,hi=refined_intervals(d,v,g)
            if np.all((lo<=truth+1e-12)&(hi>=truth-1e-12)):coverage+=mass
        assert coverage>=.95-1e-12


def test_metadata_choice_does_not_intersect_two_unadjusted_95_intervals():
    d=toy();base=dict(C=np.array([.01,.01,0]),schemes=["independent"]*3)
    g=refine_graph(d,"all_dependent",base)
    # Choice fixed from widths; it cannot change after seeing Y.
    choice=g["markov_choice"].copy()
    for y in ([1,0,0,1],[0,1,1,0]):refined_intervals(d,d.apply(y),g)
    np.testing.assert_array_equal(choice,g["markov_choice"])


SCENARIOS=json.loads((Path(__file__).resolve().parents[1]/"config/reliability_validation_v1.json").read_text(encoding="utf-8-sig"))["simulations"]["scenarios"]


@pytest.mark.parametrize("scenario",SCENARIOS,ids=lambda s:s["id"])
def test_all_fast_generators_retain_their_specified_binary_margins(scenario):
    d=toy();p=np.array([.15,.4,.65,.85])
    y=generate_fast(d,p,scenario,12000,keyed_rng("all-generator-margins",scenario["id"]))
    assert set(np.unique(y))<={0,1}
    assert np.max(np.abs(y.mean(axis=0)-p))<.025


def test_fast_signed_same_day_covariance_matches_arcsine_formula():
    d=toy();sc=dict(latent=dict(minus=.8,plus=0,pair=0,time=0,e=.2),team_tau_days=3650,time_kernel="none")
    y=generate_fast(d,np.full(4,.5),sc,20000,keyed_rng("fast-copula-covariance"))
    expected=math.asin(-.4)/(2*math.pi)
    assert abs(np.mean((y[:,0]-.5)*(y[:,1]-.5))-expected)<.008
