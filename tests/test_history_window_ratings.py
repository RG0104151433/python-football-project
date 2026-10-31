import copy,time
from pathlib import Path
import numpy as np
import pytest
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.history_window.ratings import numerical_cache,annual_job,segment,Guard,full_forecast
from src.history_window.simulation_long import generate
from tests.test_history_window import PARAMS,NUM,game

def cfg():return dict(max_job_seconds=600,max_rss_mib=2048,checkpoint_dates=2,phase_seconds={'test':600})

def test_cached_helper_preserves_full_state_and_probabilities():
    gg,tt=generate(631201,'jump','probit',12)
    def replay(cached):
        e=CollapsedJumpFilter(['A','B','C','D'],PARAMS,NUM);rr=[]
        with numerical_cache(cached,single_factor=False):
            for day in sorted({g['date'] for g in gg}):rr+=e.day(day,[g for g in gg if g['date']==day])
        return rr,e.state()
    a,sa=replay(False);b,sb=replay(True)
    assert a==b and sa==sb


def test_single_factor_cavity_cache_matches_original_full_state():
    batches=[('2000-01-01',[game('a','2000-01-01'),game('b','2000-01-01','A','C',2)]),
             ('2000-07-01',[game('c','2000-07-01','C','A',1),game('d','2000-07-01','C','B',0)])]
    def execute(cached):
        e=CollapsedJumpFilter(['A','B','C'],PARAMS,NUM);rr=[]
        with numerical_cache(cached):
            for day,gg in batches:rr+=e.day(day,gg)
        return rr,e
    a,x=execute(False);b,y=execute(True)
    np.testing.assert_allclose(x.mean,y.mean,atol=1e-9,rtol=0);np.testing.assert_allclose(x.cov,y.cov,atol=1e-9,rtol=0)
    for r,s in zip(a,b):
        for k in ('difference','difference_variance','p_home','p_draw','p_away'):assert abs(r[k]-s[k])<1e-10

def test_annual_warmup_not_backfilled_and_expiry(tmp_path):
    gg=[game('old','1997-01-01'),game('past','1999-01-01'),game('now','2000-01-01'),game('later','2001-01-01')]
    c=cfg()
    with numerical_cache():
        rr,_,_,_=annual_job(gg,['A','B'],PARAMS,NUM,2000,2,tmp_path,c,Guard(c,'test'))
        ss,_,_,_=annual_job(gg,['A','B'],PARAMS,NUM,2001,2,tmp_path,c,Guard(c,'test'))
    assert [r['match_id'] for r in rr]==['now'] and rr[0]['home_history']==1
    assert [r['match_id'] for r in ss]==['later'] and ss[0]['window_left']=='1999-01-01'
    assert ss[0]['home_history']==2

def test_resume_and_current_or_future_result_invariance(tmp_path):
    gg,_=generate(631201,'constant','probit',18);c=cfg();eids={g['match_id'] for g in gg if g['date']>='2001-01-01'}
    with numerical_cache():
        a,pa,sa,_=annual_job(gg,['A','B','C','D'],PARAMS,NUM,2001,2,tmp_path/'one',c,Guard(c,'test'),eids,True,start='2000-01-01')
        b,pb,sb,_=annual_job(gg,['A','B','C','D'],PARAMS,NUM,2001,2,tmp_path/'one',c,Guard(c,'test'),eids,True,start='2000-01-01')
    assert a==b and pa==pb and sa==sb
    engine=CollapsedJumpFilter.restore(sa);before=copy.deepcopy(engine.state())
    target=dict(gg[-1],date='2002-01-01')
    u=full_forecast(engine,target['date'],[target]);v=full_forecast(engine,target['date'],[dict(target,outcome=2)])
    assert u==v and engine.state()['mean']==before['mean'] and engine.state()['cov']==before['cov']

def test_checkpoint_replay_matches_uninterrupted(tmp_path):
    gg,_=generate(631201,'constant','probit',12);c=cfg();guard=Guard(c,'test')
    class Stop:
        calls=0
        def check(self,started):
            self.calls+=1
            if self.calls==6:raise TimeoutError('TEST_STOP')
    with numerical_cache():
        with pytest.raises(TimeoutError):annual_job(gg,['A','B','C','D'],PARAMS,NUM,2000,2,tmp_path/'stopped',c,Stop(),collect_sim=True,start='2000-01-01')
        a,pa,sa,_=annual_job(gg,['A','B','C','D'],PARAMS,NUM,2000,2,tmp_path/'stopped',c,guard,collect_sim=True,start='2000-01-01')
        b,pb,sb,_=annual_job(gg,['A','B','C','D'],PARAMS,NUM,2000,2,tmp_path/'fresh',c,guard,collect_sim=True,start='2000-01-01')
    assert a==b and pa==pb
    np.testing.assert_allclose(sa['mean'],sb['mean'],atol=1e-9,rtol=0)
    np.testing.assert_allclose(sa['cov'],sb['cov'],atol=1e-9,rtol=0)


def test_future_placeholders_and_current_outcome_do_not_rewrite_features(tmp_path):
    gg,_=generate(631201,'constant','probit',3);c=cfg()
    with numerical_cache():
        a,_,_,_=annual_job(gg,['A','B','C','D'],PARAMS,NUM,2000,2,tmp_path/'a',c,Guard(c,'test'),start='2000-01-01')
        altered=[dict(g,outcome=(g['outcome']+1)%3) for g in gg]
        b,_,_,_=annual_job(altered,['A','B','C','D','ZZ_FUTURE'],PARAMS,NUM,2000,2,tmp_path/'b',c,Guard(c,'test'),start='2000-01-01')
    for r,s in zip(a[:2],b[:2]):
        for key in ('difference','difference_variance','home_variance','away_variance','p_home','p_draw','p_away'):
            assert r[key]==pytest.approx(s[key],abs=1e-12)
    assert any(r['difference']!=s['difference'] for r,s in zip(a[2:],b[2:]))


def test_checkpoint_sharing_violation_retry(tmp_path,monkeypatch):
    import src.history_window.ratings as module
    original=module.write_json;calls=[]
    def sometimes(path,value):
        calls.append(1)
        if len(calls)<3:raise PermissionError('transient sharing violation')
        original(path,value)
    monkeypatch.setattr(module,'write_json',sometimes)
    module.write_checkpoint(tmp_path/'cp.json',{'committed':True})
    assert len(calls)==3 and (tmp_path/'cp.json').exists()
