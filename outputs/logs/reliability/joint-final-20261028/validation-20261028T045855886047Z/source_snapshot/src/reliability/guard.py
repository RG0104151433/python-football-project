"""Metadata-only scale protection for weak low-frequency variance directions.

This is not asserted to upper-bound true covariance. Independent scenario
calibration is responsible for the stated scope-limited coverage property.
"""
import numpy as np
from scipy import sparse
from .joint import CovarianceKernel,ou_precision_factor


def grouped_time_guard(design,taus=(365,1460,2920)):
    tags=[(r["era"],r["tournament_group"],r.get("home_unit","unknown"),r.get("away_unit","unknown")) for r in design.facts]
    keys=sorted(set((tag,int(day)) for tag,day in zip(tags,design.days)))
    index={k:i for i,k in enumerate(keys)}
    node=np.array([index[(tag,int(day))] for tag,day in zip(tags,design.days)])
    previous=np.full(len(keys),-1,dtype=int)
    for k in range(1,len(keys)):
        if keys[k][0]==keys[k-1][0]:previous[k]=k-1
    Z=sparse.csr_matrix((np.ones(design.n),(np.arange(design.n),node)),shape=(design.n,len(keys)))
    A=design.A.toarray();values=[]
    for tau in taus:
        kernel=CovarianceKernel("guard:"+str(tau),Z,ou_precision_factor([k[1] for k in keys],previous,tau))
        KA=kernel.apply(A.T)
        values.append(np.maximum(np.einsum("ij,ji->i",A,KA),0))
    return np.max(values,axis=0),dict(n_metadata_groups=len(set(tags)),n_process_states=len(keys),taus=list(taus),
        columns=["era","tournament_group","home_unit","away_unit"],outcomes_used=False,
        independent_groups_not_asserted_for_actual_football=True,scale_guard_not_a_variance_bound=True)


def protect_scale(fit,guard,eta):
    fit=fit.copy()
    fit["variance"]=np.maximum(fit["variance"],float(eta)*guard)
    fit["scale"]=np.sqrt(fit["variance"])
    fit["guard_eta"]=eta
    return fit
