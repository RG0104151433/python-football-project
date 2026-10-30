from datetime import date, timedelta
import numpy as np
import pytest
from scipy.special import ndtr
from src.strength_inference.worlds import complete_wdl, before_day
from src.strength_inference.targets import soft_probit_projection, probability_and_gradient
from src.strength_inference.methods import calendar_influence, bartlett_weights, multiplier_draws, summarize_draws


def test_draw_completion_preserves_home_and_nonhome_odds():
    q = np.array([[.3,.2,.5],[.1,.4,.5]])
    p = complete_wdl([.7,.2],q,2)
    assert np.allclose(p.sum(axis=1),1)
    assert np.allclose(p[:,0],[.7,.2])
    assert np.allclose(p[:,1]/p[:,2],2*q[:,1]/q[:,2])


def test_completion_rejects_invalid_inputs():
    with pytest.raises(ValueError): complete_wdl([1.],[[.3,.2,.5]])
    with pytest.raises(ValueError): complete_wdl([.5],[[.3,.2,.5]],0)


def test_soft_projection_recovers_known_coefficients_without_real_fit():
    x = np.column_stack((np.ones(90), np.tile([-1,0,1],30)))
    beta = np.array([.1,-.3]); result=soft_probit_projection(x,ndtr(x@beta))
    assert np.max(abs(np.array(result['theta'])-beta))<1e-7
    assert not result['truth_precision_admitted']


def test_calendar_distance_is_not_active_date_distance():
    calendar=np.zeros((10,2)); calendar[0]=[1,2]; calendar[9]=[-1,3]
    draws=multiplier_draws(calendar,40000,3,71001)
    expected=np.array([[2,-1],[-1,13.]])
    assert np.max(abs(np.cov(draws,rowvar=False)-expected))<.22


def test_paired_models_share_weights_and_cross_term():
    class InterceptDesign:
        def matrix(self, rows, model):
            return np.ones((len(rows),1)), ['intercept']
    rows=[dict(date=(date(2000,1,1)+timedelta(days=i)).isoformat(), home_win=i%2,
        strength_difference=0.,strength_difference_base_variance=1.,
        home_jump_intensity=0.,away_jump_intensity=0.,jump_scale_sd=1.) for i in range(40)]
    # Identical working fits must have identical, nonzero component influences
    # and zero paired difference. Exercise real bread/score/stack/multiplier code.
    model=dict(model_id='M0_nested',theta=[0.],names=['intercept'])
    jacobian=np.array([[1.,0.],[0.,1.],[-1.,1.]])
    calendar,_,_=calendar_influence({'M0_nested':model,'M3_nested':model},rows,InterceptDesign(),jacobian)
    draws=multiplier_draws(calendar,100,3,71002)
    assert np.var(draws[:,0])>0
    assert np.array_equal(draws[:,0],draws[:,1])
    assert np.max(abs(draws[:,2]))<1e-15


def test_multiplier_replay_is_deterministic():
    calendar=np.arange(60).reshape(20,3)/100
    assert np.array_equal(multiplier_draws(calendar,80,5,42),multiplier_draws(calendar,80,5,42))


def test_small_draws_do_not_produce_confidence_claim():
    assert summarize_draws(np.ones((2,4)))['status']=='INSUFFICIENT_DRAWS'
