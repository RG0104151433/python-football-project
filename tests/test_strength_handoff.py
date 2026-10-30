import json
import numpy as np
import pytest
from src.strength.streaming import partitions,StreamingStrengthFilter
from src.strength.gaussian import GaussianStrengthFilter
from src.strength.io import config
from src.strength.experiment import params
from src.strength.handoff import choose_past


@pytest.mark.parametrize("order",[0,1])
@pytest.mark.parametrize("mu",[[0,0],[.01,.1],[1.,2.,.1],[1e-9,.02]])
def test_event_partition_preserves_mass_expected_count_and_zero_jump(mu,order):
    parts=partitions(mu,order)
    assert abs(sum(p for p,_,_ in parts)-1)<1e-14
    assert abs(parts[0][0]-np.exp(-sum(mu)))<1e-14
    np.testing.assert_allclose(sum(p*c for p,c,_ in parts),mu,atol=1e-12)
    assert all(p>0 and np.all(c>=0) for p,c,_ in parts)


def game(mid="1",friendly=False,venue=1,outcome=0):
    return dict(match_id=mid,home="A",away="B",venue=venue,friendly=friendly,outcome=outcome)


def test_context_neutral_dynamic_and_restore():
    cfg=config();p=params(cfg,{"jump_rate":0,"home_by_type":True,"home_q":.02})
    e=GaussianStrengthFilter(["A","B"],p,cfg["numerics"])
    e.day("1970-01-01",[game()]);assert e.mean[2]>0 and e.mean[3]==0
    state=e.state();other=GaussianStrengthFilter.restore(json.loads(json.dumps(state)))
    rows=e.day("1971-01-01",[game("2",True,0)])
    restored=other.day("1971-01-01",[game("2",True,0)])
    np.testing.assert_allclose([rows[0][k] for k in ("p_home","p_draw","p_away")],
                              [restored[0][k] for k in ("p_home","p_draw","p_away")])
    assert rows[0]["home_term"]==0
    assert rows[0]["home_term_variance"]>.25
    assert json.dumps(state,sort_keys=True)!=json.dumps(e.state(),sort_keys=True)


def test_streaming_zero_jump_equals_original_gaussian_and_no_same_day_leak():
    cfg=config();p=params(cfg,{"jump_rate":0})
    a=StreamingStrengthFilter(["A","B"],p,{**cfg["numerics"],"max_components":4})
    b=GaussianStrengthFilter(["A","B"],p,cfg["numerics"])
    for day in ("1970-01-01","1971-01-01"):
        x,y=a.day(day,[game(day)]),b.day(day,[game(day)])
        np.testing.assert_allclose([x[0][k] for k in ("p_home","p_draw","p_away","difference_variance")],
                                  [y[0][k] for k in ("p_home","p_draw","p_away","difference_variance")],atol=1e-12)


def test_annual_choice_prefers_complex_only_beyond_frozen_margin():
    candidates=[dict(id="simple",modules=0),dict(id="complex",modules=2)]
    assert choose_past(candidates,{"simple":.9,"complex":.899},.002)=="simple"
    assert choose_past(candidates,{"simple":.9,"complex":.89},.002)=="complex"


def test_restore_rejects_future_metadata_and_cycles():
    cfg=config();p=params(cfg,{"jump_rate":0})
    e=GaussianStrengthFilter(["A","B"],p,cfg["numerics"])
    e.day("1970-01-01",[game()]);s=e.state();s["last"]["A"]="1980-01-01"
    with pytest.raises(ValueError,match="future"):GaussianStrengthFilter.restore(s)
    s=e.state();s["parent"]={"A":"B","B":"A"}
    with pytest.raises(ValueError,match="cycle"):GaussianStrengthFilter.restore(s)
