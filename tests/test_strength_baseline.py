import copy
import numpy as np
from src.strength.baseline import fixed_step,frequency


def test_fixed_step_and_frequency_same_date_no_leak():
    games=[dict(match_id="a",date="1970-01-01",home="A",away="B",venue=1,outcome=0),
           dict(match_id="b",date="1970-01-01",home="A",away="C",venue=1,outcome=2)]
    changed=copy.deepcopy(games)
    changed[0]["outcome"]=2
    for method in (fixed_step,frequency):
        x,y=method(games),method(changed)
        for a,b in zip(x,y):
            np.testing.assert_array_equal([a[k] for k in ("p_home","p_draw","p_away")],
                                          [b[k] for k in ("p_home","p_draw","p_away")])


def test_fixed_step_neutral_and_reversed_teams_symmetric():
    g=[dict(match_id="a",date="1970-01-01",home="A",away="B",venue=0,outcome=0),
       dict(match_id="b",date="1970-02-01",home="A",away="B",venue=0,outcome=2)]
    h=[dict(r,home=r["away"],away=r["home"],outcome=2-r["outcome"]) for r in g]
    for a,b in zip(fixed_step(g),fixed_step(h)):
        np.testing.assert_allclose([a[k] for k in ("p_home","p_draw","p_away")],
                                  [b[k] for k in ("p_away","p_draw","p_home")],atol=1e-12)
