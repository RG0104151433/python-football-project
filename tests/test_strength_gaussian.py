import json
import numpy as np
import pytest
from src.strength.filter import StrengthFilter
from src.strength.gaussian import GaussianStrengthFilter
from src.strength.io import config
from src.strength.experiment import params


@pytest.mark.parametrize("candidate",["smooth","robust"])
def test_efficient_special_case_matches_original_full_covariance(candidate):
    cfg=config()
    p=params(cfg,next(c for c in cfg["pilot"]["candidates"] if c["id"]==candidate))
    a=StrengthFilter(["A","B","C"],p,cfg["numerics"])
    b=GaussianStrengthFilter(["A","B","C"],p,cfg["numerics"])
    batches=[
        ("1960-01-01",[dict(match_id="1",home="A",away="B",venue=1,friendly=False,outcome=0)]),
        ("1960-03-01",[dict(match_id="2",home="C",away="A",venue=0,friendly=True,outcome=1)]),
        ("1960-04-01",[dict(match_id="3",home="B",away="C",venue=1,friendly=False,outcome=2),
                       dict(match_id="4",home="A",away="B",venue=1,friendly=True,outcome=0)])]
    for day,games in batches:
        x,y=a.day(day,games),b.day(day,games)
        for r,s in zip(x,y):
            np.testing.assert_allclose([r[k] for k in ("p_home","p_draw","p_away","difference_variance")],
                                       [s[k] for k in ("p_home","p_draw","p_away","difference_variance")],atol=1e-12)
        np.testing.assert_allclose(a.components[0].mean,b.mean,atol=1e-12)
        np.testing.assert_allclose(a.components[0].cov,b.cov,atol=1e-12)
    c=GaussianStrengthFilter.restore(json.loads(json.dumps(b.state())))
    np.testing.assert_array_equal(c.mean,b.mean)
    assert c.last==b.last


def test_future_unused_roster_does_not_change_predictions():
    cfg=config()
    p=params(cfg,{"jump_rate":0})
    a=GaussianStrengthFilter(["A","B"],p,cfg["numerics"])
    b=GaussianStrengthFilter(["A","B","Z-not-yet-observed"],p,cfg["numerics"])
    for day in ("1960-01-01","1960-02-01"):
        g=[dict(match_id=day,home="A",away="B",venue=1,friendly=False,outcome=0)]
        x,y=a.day(day,g)[0],b.day(day,g)[0]
        assert [x[k] for k in ("p_home","p_draw","p_away")]==[y[k] for k in ("p_home","p_draw","p_away")]


def test_checkpoint_dictionary_is_a_snapshot_not_live_alias():
    cfg=config();p=params(cfg,{"jump_rate":0})
    e=GaussianStrengthFilter(["A","B","C"],p,cfg["numerics"])
    g=dict(match_id="first",home="A",away="B",venue=1,friendly=False,outcome=0)
    e.day("1979-01-01",[g])
    saved=e.state()
    encoded=json.dumps(saved,sort_keys=True)
    e.day("1980-01-01",[dict(g,match_id="second",home="C")])
    assert json.dumps(saved,sort_keys=True)==encoded
    assert saved["last"]["A"]=="1979-01-01" and "C" not in saved["last"]
