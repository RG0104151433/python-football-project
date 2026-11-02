from datetime import datetime,timezone
import pytest
from scripts.evaluate_future_matches import score_results

def forecast():
    return dict(match_id='fixture',date='2026-11-12',round='5',kickoff_cet='20:45',main_home_probability='.6',
        strength_reference_home_probability='.5',native_home_probability='.5',native_draw_probability='.3',native_away_probability='.2')

def result():
    return dict(match_id='fixture',home_score='1',away_score='0',final_confirmed='true',
                observed_at_utc='2026-11-12T23:00:00+00:00',source_url='https://example.invalid/synthetic-fixture')

def test_future_results_rejected_before_kickoff():
    with pytest.raises(ValueError,match='NOT_YET_AVAILABLE'):
        score_results([forecast()],[result()],datetime(2026,11,2,tzinfo=timezone.utc))

def test_synthetic_finished_fixture_scores_original_paired_forecasts():
    rr=score_results([forecast()],[result()],datetime(2026,11,13,tzinfo=timezone.utc))
    assert rr[0]['joint_minus_reference_loss']<0 and rr[0]['home_win']==1

def test_duplicate_and_unconfirmed_results_rejected():
    now=datetime(2026,11,13,tzinfo=timezone.utc)
    with pytest.raises(ValueError,match='DUPLICATE'):score_results([forecast()],[result(),result()],now)
    with pytest.raises(ValueError,match='UNCONFIRMED'):score_results([forecast()],[dict(result(),final_confirmed='false')],now)
