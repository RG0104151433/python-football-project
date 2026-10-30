import copy
import numpy as np
from src.strength.global_run import choose,replay
from src.strength.io import ROOT
import json


def test_selection_prefers_simpler_only_inside_prespecified_margin():
    cfg={"selection":{"tie_margin":.01}}
    rows=[dict(model="complex",period="selection_validation",log_loss=.90,modules=1,candidate_order=1,start=1950),
          dict(model="simple",period="selection_validation",log_loss=.905,modules=0,candidate_order=0,start=1950)]
    winner,best=choose(rows,cfg)
    assert winner["model"]=="simple" and best==.90
    rows[1]["log_loss"]=.92
    assert choose(rows,cfg)[0]["model"]=="complex"


def test_adding_future_outcomes_does_not_rewrite_past_features():
    cfg=json.loads((ROOT/"config/strength_global.json").read_text(encoding="utf-8"))
    p=cfg["candidates"][0]["parameters"]
    games=[dict(match_id="a",date="1970-01-01",home="A",away="B",venue=1,friendly=False,outcome=0),
           dict(match_id="b",date="1971-01-01",home="C",away="A",venue=0,friendly=True,outcome=2)]
    a,_,_=replay(games,cfg,p,1950)
    future=games+[dict(match_id="c",date="1980-01-01",home="FUTURE",away="A",venue=1,friendly=False,outcome=1)]
    b,_,_=replay(future,cfg,p,1950)
    for r,s in zip(a,b[:2]):
        np.testing.assert_allclose([r[k] for k in ("home_mean","away_mean","p_home","p_draw","p_away")],
                                   [s[k] for k in ("home_mean","away_mean","p_home","p_draw","p_away")],atol=1e-12)


def test_structural_parsimony_does_not_prefer_arbitrary_parameter_order():
    cfg={"selection":{"tie_margin":.01,"policy":"structural_family_then_minimum_loss"}}
    rows=[dict(model="simple_early",period="selection_validation",log_loss=.905,modules=0,candidate_order=0,start=1960),
          dict(model="simple_best",period="selection_validation",log_loss=.900,modules=0,candidate_order=1,start=1950),
          dict(model="complex",period="selection_validation",log_loss=.899,modules=1,candidate_order=2,start=1950)]
    assert choose(rows,cfg)[0]["model"]=="simple_best"


def test_calibration_screen_precedes_structural_tie_break():
    cfg={"selection":{"tie_margin":.01,"max_absolute_class_bias":.03,"policy":"structural_family_then_minimum_loss"}}
    rows=[dict(model="bad",period="selection_validation",log_loss=.8,modules=0,candidate_order=0,start=1950,max_absolute_class_bias=.05),
          dict(model="good",period="selection_validation",log_loss=.9,modules=1,candidate_order=1,start=1950,max_absolute_class_bias=.02)]
    assert choose(rows,cfg)[0]["model"]=="good"
