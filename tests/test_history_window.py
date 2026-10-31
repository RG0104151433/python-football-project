import copy
import math
import numpy as np
import pytest
from scipy.special import logsumexp
from src.history_window.protocol import anniversary,bounds,training_slice,select_past,log_losses,paired_radius
from src.history_window.replay import strict_replay,forecast
from src.history_window.simulation import generate
from src.strength.collapsed_jump import CollapsedJumpFilter

PARAMS=dict(q=.03,delta=.4,alpha=.65,epsilon=.05,home_q=.005,jump_rate=.08,jump_sd=1.2)
NUM=dict(ep_max_iter=300,ep_tolerance=1e-6,ep_damping=.5,rank_tolerance=1e-12,poisson_tail_tolerance=1e-12,psd_tolerance=1e-8)


def game(mid,day,home='A',away='B',outcome=0,venue=1):
    return dict(match_id=mid,date=day,home=home,away=away,outcome=outcome,venue=venue,friendly=False)


def test_calendar_inclusive_anniversary_and_exclusive_day():
    assert anniversary('2000-02-29',2)=='1998-02-28'
    assert anniversary('2004-02-29',4)=='2000-02-29'
    rr=[dict(match_id=str(i),date=d) for i,d in enumerate(['1997-12-31','1998-01-01','1999-12-31','2000-01-01'])]
    rows,ledger=training_slice(rr,2000,2)
    assert [r['date'] for r in rows]==['1998-01-01','1999-12-31']
    assert bounds('2000-01-01',None,'1980-01-01')==('1980-01-01','2000-01-01')
    with pytest.raises(ValueError): anniversary('2000-01-01',0)


def test_window_resets_all_state_and_ignores_outside_results():
    gg=[game('old','1990-01-01'),game('inside','1999-06-01'),game('target','2000-01-01')]
    a,ledger,engine=strict_replay(gg,[gg[-1]],'2000-01-01',2,PARAMS,NUM)
    changed=[dict(g,outcome=2) if g['date']<'1998-01-01' or g['date']>='2000-01-01' else g for g in gg]
    b,_,_=strict_replay(changed,[changed[-1]],'2000-01-01',2,PARAMS,NUM)
    assert a==b and ledger['history_rows']==1 and a[0]['home_history']==1
    empty,_,fresh=strict_replay(gg,[gg[-1]],'2000-01-01',1,PARAMS,NUM,start='1999-12-01')
    assert empty[0]['home_history']==0 and empty[0]['home_term']==0
    assert np.allclose(fresh.mean,0) and np.allclose(np.diag(fresh.cov),[1,1,.25])


@pytest.mark.parametrize('neutral',[False,True])
def test_pure_prediction_matches_original_batch_and_no_same_day_leak(neutral):
    engine=CollapsedJumpFilter(['A','B','C','D'],PARAMS,NUM)
    engine.day('1999-01-01',[game('one','1999-01-01')])
    batch=[game('two','2000-01-01',venue=0 if neutral else 1),game('three','2000-01-01','C','D',2)]
    before=copy.deepcopy(engine.state()); ours=forecast(engine,'2000-01-01',batch)
    assert engine.state()==before
    theirs=engine.day('2000-01-01',batch)
    for a,b in zip(ours,theirs):
        for key in ('difference','difference_variance','home_term','home_mean','away_mean','p_home','p_draw','p_away'):
            assert a[key]==pytest.approx(b[key],abs=1e-12)
    changed=CollapsedJumpFilter.restore(before)
    other=forecast(changed,'2000-01-01',[dict(g,outcome=(g['outcome']+1)%3) for g in batch])
    assert ours==other


def test_cold_start_survives_and_both_teams_update():
    first=game('a','1999-01-01'); target=game('b','2000-01-01',home='B',away='NEW')
    rows,_,engine=strict_replay([first],[target],'2000-01-01',2,PARAMS,NUM)
    assert rows[0]['home_history']==1 and rows[0]['away_history']==0 and rows[0]['cold_start']
    assert engine.mean[engine.index['A']]>0 and engine.mean[engine.index['B']]<0


def test_future_year_cannot_change_window_selection():
    rows=[dict(year=year,window=w,matches=10,id_set_sha256=str(year),loss_sum=v) for year in range(2000,2010)
          for w,v in [('2y',5),('cumulative',6)]]
    assert select_past(rows,2010,[2,None])=='2y'
    rows.append(dict(year=2010,window='2y',matches=100,id_set_sha256='bad',loss_sum=999))
    assert select_past(rows,2010,[2,None])=='2y'
    rows[0]['id_set_sha256']='mismatched'
    with pytest.raises(ValueError,match='SAMPLE_MISMATCH'): select_past(rows,2010,[2,None])


def test_clipped_loss_and_hoeffding_daily_mgf_with_complete_within_day_dependence():
    eps=1e-6; b=math.log((1-eps)/eps)
    assert max(abs(log_losses([eps,1-eps],[0,1])-log_losses([1-eps,eps],[0,1])))==pytest.approx(b)
    # All seven matches share one Bernoulli result: deliberately no independence.
    losses=7*(log_losses([.2,.2],[0,1])-log_losses([.8,.8],[0,1]))
    for true_p in (.05,.5,.9):
        mean=np.dot([1-true_p,true_p],losses)
        for lam in (1e-4,.01,.1):
            for sign in (-1,1):
                logmgf=logsumexp(np.log([1-true_p,true_p])+sign*lam*(losses-mean))
                assert logmgf <= lam*lam*b*b*7**2/2+1e-12
    assert paired_radius([100])>paired_radius([1]*100)
    assert paired_radius([1]*100,pairs=60)>paired_radius([1]*100,pairs=1)


@pytest.mark.parametrize('path',['constant','drift','jump'])
@pytest.mark.parametrize('link',['probit','logistic'])
def test_independent_truth_generator_repeats_without_estimator(path,link):
    a,t=generate(1,path,link); b,u=generate(1,path,link)
    assert a==b and t==u and len(a)==120
    assert all(0<r['true_home_probability']<1 for r in t)
    assert any(g['venue']==0 for g in a) and any(g['friendly'] for g in a)
    if path=='jump':
        assert abs(t[0]['true_difference'])!=abs(t[-1]['true_difference'])
