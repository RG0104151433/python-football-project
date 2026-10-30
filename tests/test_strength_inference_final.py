from datetime import date,timedelta
import numpy as np
from scipy.special import ndtr
from src.strength_inference.fast import install_count_cache,query
from src.strength_inference.worlds import before_day
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength_predictive_validation import metrics
from src.strength_inference_numerics import ReliableJumpFilter,RETRY_EVENTS
from src.strength.filter import NumericalFailure


def test_fast_prior_respects_full_covariance_neutral_and_roles():
    p=dict(q=.03,jump_rate=.08,jump_sd=1.2,delta=.4,alpha=.65,epsilon=.05,home_q=.005)
    n=dict(ep_tolerance=1e-6,ep_max_iter=300,ep_damping=.5,rank_tolerance=1e-12,poisson_tail_tolerance=1e-12)
    engine=CollapsedJumpFilter(['A','B','C'],p,n);install_count_cache()
    for i in range(5):
        day=(date(1980,1,1)+timedelta(days=90*i)).isoformat()
        gs=[dict(match_id=str(i),date=day,home='A' if i%2 else 'B',away='C',venue=0 if i==3 else 1,friendly=i%2==0,outcome=i%3)]
        before=engine.mean.copy();rr,a=before_day(engine,day,gs);ss,b=query(engine,day,gs)
        assert np.max(abs(a-b))<2e-12
        assert np.array_equal(engine.mean,before)
        assert abs(rr[0]['strength_difference_variance']-ss[0]['strength_difference_variance'])<1e-14
        engine.day(day,gs)


def test_binary_forecast_metrics_have_explicit_units_and_targets():
    rr=[dict(probability=.8,home_win=1),dict(probability=.2,home_win=0)]
    m=metrics(rr)
    assert abs(m['log_loss']+np.log(.8))<1e-12
    assert abs(m['brier']-.04)<1e-12
    assert m['binary_accuracy']==1 and m['calibration_bias_pp']==0


def test_strict_retry_restores_pre_date_state_and_keeps_outcome(monkeypatch):
    p=dict(q=.03,jump_rate=.08,jump_sd=1.2,delta=.4,alpha=.65,epsilon=.05,home_q=.005)
    n=dict(ep_tolerance=1e-6,ep_max_iter=300,ep_damping=.5,rank_tolerance=1e-12,poisson_tail_tolerance=1e-12)
    engine=ReliableJumpFilter(['A','B'],p,n);reference=CollapsedJumpFilter(['A','B'],p,n)
    real=CollapsedJumpFilter.day;calls=[]
    def injected(self,day,games):
        calls.append(games[0]['outcome'])
        if len(calls)==1:
            self.mean[0]+=9;self.cov[0,0]+=10
            raise NumericalFailure('injected failure after state mutation')
        return real(self,day,games)
    monkeypatch.setattr(CollapsedJumpFilter,'day',injected);RETRY_EVENTS.clear()
    gs=[dict(match_id='one',date='1980-01-01',home='A',away='B',venue=1,friendly=False,outcome=2)]
    result=engine.day('1980-01-01',gs);expected=real(reference,'1980-01-01',gs)
    assert calls==[2,2] and len(RETRY_EVENTS)==1
    assert abs(result[0]['difference']-expected[0]['difference'])<1e-14
    assert np.max(abs(engine.mean-reference.mean))<1e-5
    assert engine.numerics==n and engine.counts==reference.counts
