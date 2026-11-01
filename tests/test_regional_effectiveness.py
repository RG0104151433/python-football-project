import math
import pytest
from src.regional_effectiveness import unique,match_facts,validate_forecast,groups,bin_index,describe,past_frequencies


def test_duplicate_or_mismatched_facts_rejected():
    a=dict(match_id='a',date='2010-01-01',home_win='1',home_region='150',tournament_group='friendly')
    with pytest.raises(ValueError,match='DUPLICATE'):unique([a,a],'test')
    with pytest.raises(ValueError,match='PAIRED'):match_facts(a,dict(a,home_win='0'))


def test_invalid_forecasts_rejected():
    for y,p in [('2',.5),('1',float('nan')),('1',1.01)]:
        with pytest.raises(ValueError):validate_forecast(dict(home_win=y,probability=p,date='2010-01-01'))


def test_south_america_is_subset_and_other_america_disjoint():
    assert groups(dict(home_region='019',home_unit='005'))==['ALL','019','SOUTH_AMERICA']
    assert groups(dict(home_region='019',home_unit='029'))==['ALL','019','OTHER_AMERICAS']
    assert groups(dict(home_region='',home_unit=''))==['ALL','UNKNOWN']


def test_calibration_edges_include_zero_and_one():
    edges=[0,.2,.4,.6,.8,1]
    assert [bin_index(p,edges) for p in [0,.19999,.2,.8,1]]==[0,0,1,4,4]


def test_metrics_hand_calculation_and_empty_cells():
    rows=[dict(p=.8,home_win=1),dict(p=.4,home_win=0)]
    m=describe(rows,'p',1e-6)
    assert m['log_loss']==pytest.approx((-math.log(.8)-math.log(.6))/2)
    assert m['brier']==pytest.approx(.1)
    assert m['bias_pp']==pytest.approx(10)
    assert describe([],'p',1e-6)['log_loss'] is None


def test_past_frequency_never_uses_target_or_later_results():
    facts=[dict(date='2009-12-31',home_win='1'),dict(date='2010-01-01',home_win='0')]
    before=past_frequencies(facts,[2010],'1980-01-01')
    facts[1]['home_win']='1'
    assert past_frequencies(facts,[2010],'1980-01-01')==before
