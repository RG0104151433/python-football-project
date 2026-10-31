import pytest
from src.history_window.ratings import adapt_facts

def test_new_policy_adapter_replaces_distribution_and_marks_uncomputed_initialization():
    f=dict(match_id='x',date='2000-01-01',home_rating_entity='A',away_rating_entity='B',
           initialization_sensitive='true',strength_difference='999')
    s=dict(match_id='x',date='2000-01-01',home='A',away='B',difference=.3,difference_variance=1.,difference_base_variance=.8,
           home_jump_intensity=.1,away_jump_intensity=.1,jump_scale_sd=1.,home_variance=.5,away_variance=.5,
           home_away_covariance=0.,home_history=1,away_history=2,cold_start=True,previously_disconnected=False,prediction_cutoff='1999-12-31')
    r=adapt_facts([f],[s],'annual2-v1')[0]
    assert r['strength_difference']==.3 and r['initialization_sensitive'] is None and r['rating_run_id']=='annual2-v1'
    assert f['strength_difference']=='999'
    with pytest.raises(ValueError):adapt_facts([f],[],'annual2-v1')
