import numpy as np
from scipy.optimize._numdiff import approx_derivative
from src.strength.calibration import fit,predict,objective,online_offsets,switching_mixture,matrix_objective
from src.strength.collapsed_jump import CollapsedJumpFilter,single_local,count_weights
from src.strength.gaussian import GaussianStrengthFilter
from src.strength.filter import outcome_moments
from src.strength.io import config
import json


def test_calibration_gradient_and_identity_map():
    u=np.array([[1.,-.4],[-1.,.2],[.1,-.8]])
    y=np.array([0,1,2]);t=np.array([.2,-.1,1.1])
    value,gradient=objective(t,u,y,8.,True)
    numeric=approx_derivative(lambda z:objective(z,u,y,8.,True)[0],t).ravel()
    np.testing.assert_allclose(gradient,numeric,atol=1e-7)
    p=np.array([[.5,.3,.2],[.1,.2,.7]])
    s=dict(theta=[0.,0.,1.],covariance=np.eye(3).tolist())
    np.testing.assert_allclose(predict(p,s,integrate=False),p)


def test_calibration_improves_training_objective_and_quadrature_stable():
    p=np.tile([.6,.25,.15],(300,1));y=np.tile([0,1,2],100)
    s=fit(p,y)
    assert s['theta'][0]<0
    a=predict(p[:2],s,9);b=predict(p[:2],s,17)
    np.testing.assert_allclose(a.sum(axis=1),1,atol=1e-12)
    assert np.max(abs(a-b))<.001


def test_exact_single_jump_local_matches_independent_double_count_sum():
    mh,ma=.04,.08;jv=1.44;mean=.7;var=.6
    m,c=single_local(mean,var,2,.95,mh,ma,.4,jv,1e-13)
    values=[]
    for i,wh in enumerate(count_weights(mh,1e-14)):
        for j,wa in enumerate(count_weights(ma,1e-14)):
            prior=np.diag([var,i*jv,j*jv]);a=np.array([1,1,-1]);v=prior@a
            z,_,_,g,h=outcome_moments(mean,float(a@v),2,.4,.95)
            values.append((wh*wa*z,np.array([mean,0,0])+v*g,prior+np.outer(v,v)*h))
    total=sum(w for w,_,_ in values);mm=sum(w*mu for w,mu,_ in values)/total
    cc=sum(w*(vc+np.outer(mu-mm,mu-mm)) for w,mu,vc in values)/total
    np.testing.assert_allclose(m,mm,atol=1e-10);np.testing.assert_allclose(c,cc,atol=1e-10)


def test_collapsed_zero_jump_equals_gaussian_and_restore():
    cfg=config();p=dict(cfg['pilot']['base'],jump_rate=0)
    a=CollapsedJumpFilter(['A','B','C','D'],p,cfg['numerics'])
    b=GaussianStrengthFilter(['A','B','C','D'],p,cfg['numerics'])
    for day,gs in [('1960-01-01',[('A','B',0),('C','D',1)]),('1961-01-01',[('A','C',2),('B','A',0)])]:
        games=[dict(match_id=str(i),home=h,away=aw,venue=1,friendly=False,outcome=y) for i,(h,aw,y) in enumerate(gs)]
        a.day(day,games);b.day(day,games)
        np.testing.assert_allclose(a.mean,b.mean,atol=1e-6);np.testing.assert_allclose(a.cov,b.cov,atol=1e-6)
    restored=CollapsedJumpFilter.restore(json.loads(json.dumps(a.state())))
    np.testing.assert_array_equal(a.cov,restored.cov)


def test_online_maps_and_switching_weights_do_not_read_current_or_future_results():
    pp=np.tile([.55,.25,.2],(4,1));ds=['1970-01-01','1970-01-01','1971-01-01','1972-01-01'];cc=np.zeros((4,2),dtype=int)
    y=np.array([0,1,2,0]);different=np.array([2,2,2,0])
    a,_=online_offsets(pp,y,ds,cc);b,_=online_offsets(pp,different,ds,cc)
    np.testing.assert_array_equal(a[:2],b[:2]);assert np.max(abs(a[2:]-b[2:]))>.001
    experts=np.stack((pp,pp[:,::-1]),axis=1)
    a,_=switching_mixture(experts,y,ds,cc,[.5,.5]);b,_=switching_mixture(experts,different,ds,cc,[.5,.5])
    np.testing.assert_array_equal(a[:2],b[:2]);np.testing.assert_allclose(a.sum(axis=1),1)


def test_matrix_gradient_and_online_restart_match_continuous_run():
    u=np.array([[1.,-.4],[-1.,.2],[.1,-.8]]);y=np.array([0,1,2]);t=np.array([.1,-.1,1.,.2,-.1,1.])
    np.testing.assert_allclose(matrix_objective(t,u,y,8.)[1],approx_derivative(lambda z:matrix_objective(z,u,y,8.)[0],t).ravel(),atol=1e-7)
    p=np.tile([.55,.25,.2],(4,1));ds=['1970-01-01','1970-01-01','1971-01-01','1972-01-01'];cc=np.zeros((4,2),dtype=int)
    yy=np.array([0,1,2,0]);a,diag=online_offsets(p,yy,ds,cc)
    b,_=online_offsets(p[2:],yy[2:],ds[2:],cc[2:],initial_states=[diag[0]])
    np.testing.assert_array_equal(a[2:],b)
    experts=np.stack((p,p[:,::-1]),axis=1);a,diag=switching_mixture(experts,yy,ds,cc,[.5,.5])
    b,_=switching_mixture(experts[2:],yy[2:],ds[2:],cc[2:],[.5,.5],initial_states=[diag[0]])
    np.testing.assert_array_equal(a[2:],b)


def test_nonzero_jump_shared_team_role_swap_preserves_posterior():
    cfg=config();p=dict(cfg['pilot']['base'],home_q=.005)
    a=CollapsedJumpFilter(['A','B','C'],p,cfg['numerics'])
    a.day('1960-01-01',[dict(match_id='initial',home='A',away='B',venue=1,friendly=False,outcome=0)])
    b=CollapsedJumpFilter.restore(json.loads(json.dumps(a.state())))
    games=[dict(match_id='1',home='A',away='B',venue=1,friendly=False,outcome=2),
           dict(match_id='2',home='C',away='A',venue=1,friendly=True,outcome=1)]
    swapped=[dict(g,home=g['away'],away=g['home'],venue=-g['venue'],outcome=2-g['outcome']) for g in games]
    x=a.day('1961-01-01',games);y=b.day('1961-01-01',swapped)
    np.testing.assert_allclose(a.mean,b.mean,atol=1e-6);np.testing.assert_allclose(a.cov,b.cov,atol=1e-6)
    np.testing.assert_allclose([r['p_home'] for r in x],[r['p_away'] for r in y],atol=1e-12)


def test_nonzero_jump_current_results_do_not_change_current_forecasts():
    cfg=config();p=dict(cfg['pilot']['base'])
    a=CollapsedJumpFilter(['A','B','C'],p,cfg['numerics'])
    a.day('1960-01-01',[dict(match_id='initial',home='A',away='B',venue=1,friendly=False,outcome=0)])
    b=CollapsedJumpFilter.restore(json.loads(json.dumps(a.state())))
    games=[dict(match_id='1',home='A',away='B',venue=1,friendly=False,outcome=0),
           dict(match_id='2',home='B',away='C',venue=0,friendly=True,outcome=1)]
    x=a.day('1961-01-01',games);y=b.day('1961-01-01',[dict(g,outcome=2) for g in reversed(games)])
    for r,s in zip(x,y):
        np.testing.assert_array_equal([r[k] for k in ('p_home','p_draw','p_away','difference_variance')],
                                      [s[k] for k in ('p_home','p_draw','p_away','difference_variance')])
    assert np.max(abs(a.mean-b.mean))>1e-4
