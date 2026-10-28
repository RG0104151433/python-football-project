import itertools
import numpy as np
from src.reliability.graph_exact import worst_bernoulli_logmgf,sharper_halfwidth
from src.reliability.models import greedy_colors,graph_bounds
from src.reliability.guard import grouped_time_guard
from tests.test_reliability_models import toy


def test_bernoulli_supremum_bounds_all_grid_probabilities():
    for x in (.00001,.01,.5,1,5,20,100):
        p=np.linspace(.00001,.99999,20000)
        actual=np.logaddexp(np.log1p(-p),np.log(p)+x)-x*p
        exact=float(worst_bernoulli_logmgf(x))
        assert actual.max()<=exact+1e-10
        assert exact<=x*x/8+1e-10
        assert abs(float(worst_bernoulli_logmgf(-x))-exact)<1e-12


def test_sharper_graph_interval_keeps_independent_binary_coverage():
    d=toy();g=graph_bounds(d,0,False);color=greedy_colors(d,0)
    half=[]
    for j in range(3):
        h,_=sharper_halfwidth(d.A.getrow(j).toarray().ravel(),color,3,g["half"][j]);half.append(h)
        assert 0<=h<=g["half"][j]+1e-12
    for p in ([.1,.4,.7,.9],[.5]*4):
        truth=d.apply(p);covered=0
        for y in itertools.product([0,1],repeat=4):
            mass=np.prod([pi if yi else 1-pi for yi,pi in zip(y,p)])
            if np.all(np.abs(d.apply(y)-truth)<=np.array(half)+1e-12):covered+=mass
        assert covered>=.95-1e-12


def test_grouped_time_guard_is_nonnegative_and_outcome_free():
    d=toy();guard,meta=grouped_time_guard(d,taus=(30,365))
    assert np.all(guard>=0) and guard[2]==0
    assert not meta["outcomes_used"] and meta["scale_guard_not_a_variance_bound"]
