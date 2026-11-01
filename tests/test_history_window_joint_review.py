import math
import pytest
from src.history_window.joint_review import paired


def test_paired_probability_loss_clips_extremes_and_keeps_labels():
    a=[dict(match_id='a',date='2000-01-01',home_win=1,probability=0),dict(match_id='b',date='2000-01-02',home_win=0,probability=1)]
    b=[dict(r,probability=.5) for r in a]
    value=paired(a,list(reversed(b)),1e-6)
    expected=(-math.log(1e-6)-math.log(1- (1-1e-6)))/2-math.log(2)
    assert value['mean_loss_minus_baseline']==pytest.approx(expected)
    assert value['worse_matches']==2 and value['better_matches']==0


def test_same_ids_with_different_actual_labels_are_rejected():
    a=[dict(match_id='a',date='2000-01-01',home_win=1,probability=.7)]
    with pytest.raises(ValueError,match='PAIRED_FACTS_DIFFER'):paired(a,[dict(a[0],home_win=0)],1e-6)
