import itertools
import math

import numpy as np
from scipy.linalg import pinvh

from src.reliability.models import pair_metadata
from src.reliability.joint import kernels,RestrictedMoments,finite_calibration_critical
from tests.test_reliability_models import toy


def test_markov_precision_kernels_equal_direct_covariance():
    d=toy();I=np.eye(d.n)
    i,j=np.indices((d.n,d.n))
    for kernel in kernels(d,team_taus=(365,),time_taus=(30,)):
        actual=kernel.apply(I)
        from src.reliability.joint import raw_pair_entries
        expected=raw_pair_entries(d,kernel,i.ravel(),j.ravel()).reshape(d.n,d.n)
        np.testing.assert_allclose(actual,expected,atol=1e-11)
        assert np.linalg.eigvalsh(actual).min()>-1e-10


def test_projected_pair_design_matches_explicit_dense_projection():
    d=toy();i,j=np.triu_indices(d.n,1);pairs=pair_metadata(d,i,j)
    model=RestrictedMoments(d,pairs,team_taus=(365,),time_taus=(365,1460))
    X=d.X.toarray();M=np.eye(d.n)-X@pinvh(X.T@X)@X.T
    for k,kernel in enumerate(model.kernels):
        K=kernel.apply(np.eye(d.n));expected=M@K@M
        np.testing.assert_allclose(model.corrected[:,k],expected[model.i,model.j],atol=1e-10)


def test_binary_second_moment_identity_by_exact_enumeration():
    d=toy();i,j=np.triu_indices(d.n,1)
    model=RestrictedMoments(d,pair_metadata(d,i,j),team_taus=(365,),time_taus=(365,1460))
    average=np.zeros(len(model.i))
    for y in itertools.product([0.,1.],repeat=d.n):
        r=model.residual(np.array(y));average+=r[model.i]*r[model.j]/16
    np.testing.assert_allclose(average,.25*model.corrected[:,0],atol=1e-12)


def test_permanent_global_shock_unidentified_after_intercept_projection():
    d=toy();X=d.X.toarray();M=np.eye(d.n)-X@pinvh(X.T@X)@X.T
    np.testing.assert_allclose(M@np.ones((d.n,d.n))@M,0,atol=1e-12)
    assert np.sum(d.A.getrow(0).toarray())==1


def test_finite_calibration_rank_and_ties():
    assert finite_calibration_critical(np.arange(1999),.025)==1949
    assert finite_calibration_critical(np.ones(1999),.025)==1
    assert math.isinf(finite_calibration_critical(np.arange(5),.025))


def test_joint_gls_matches_dense_normal_equations():
    d=toy();i,j=np.triu_indices(d.n,1)
    model=RestrictedMoments(d,pair_metadata(d,i,j),team_taus=(365,),time_taus=(365,1460))
    theta=np.array([.1,.02,.02,.01,.03,.02])
    y=np.array([0.,1.,1.,0.])
    actual=model.joint_gls(y,theta,rtol=1e-10)
    Sigma=sum(w*k.apply(np.eye(d.n)) for w,k in zip(theta,model.kernels))+actual["noise_ridge"]*np.eye(d.n)
    X=d.X.toarray();inv=np.linalg.inv(Sigma)
    b=pinvh(X.T@inv@X)@X.T@inv@y
    np.testing.assert_allclose(actual["mean"],X@b,atol=1e-8)
    np.testing.assert_allclose(actual["alpha"],inv@(y-X@b),atol=1e-8)


def test_rank_coverage_exact_for_arbitrary_fitted_score_map():
    # A finite nonuniform score distribution may include the output of an
    # arbitrary deterministic nuisance-fitting algorithm. Ties conservative.
    values=np.array([0.,.2,1.,3.]);mass=np.array([.1,.3,.4,.2]);B=19;alpha=.05
    lower=np.r_[0,np.cumsum(mass)[:-1]]
    failure=np.sum(mass*lower**B)  # new score exceeds max of19 references
    assert failure<=alpha
