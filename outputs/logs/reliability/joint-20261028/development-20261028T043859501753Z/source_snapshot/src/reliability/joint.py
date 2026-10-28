"""Restricted moment joint mean/covariance estimation for fixed-design scores.

This is a second-moment working model, not a Gaussian likelihood for binary
scores. The projection correction is exact when E(Y) belongs to col(X).
Nonnegative fitting and a misspecified mean need explicit simulation checks.
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy import sparse
from scipy.linalg import cholesky_banded, cho_solve_banded, pinvh, qr
from scipy.optimize import nnls
from scipy.sparse.linalg import LinearOperator, cg


@dataclass
class CovarianceKernel:
    label: str
    Z: object
    factor: object = None

    def apply(self, v):
        if self.label == "independent":return np.asarray(v)
        z=self.Z.T @ v
        if self.factor is not None:z=cho_solve_banded((self.factor,True),np.asarray(z),check_finite=False)
        return np.asarray(self.Z @ z)


def ou_precision_factor(days,previous=None,tau=365):
    days=np.asarray(days,float);n=len(days)
    if previous is None:previous=np.r_[-1,np.arange(n-1)]
    previous=np.asarray(previous)
    first=previous<0
    gap=np.zeros(n);gap[~first]=days[~first]-days[previous[~first]]
    if np.any(gap[~first]<=0):raise ValueError("Deduplicate tied process states")
    rho=np.zeros(n);rho[~first]=np.exp(-gap[~first]/tau)
    inv=np.ones(n);inv[~first]=1/(-np.expm1(-2*gap[~first]/tau))
    diagonal=inv.copy()
    np.add.at(diagonal,previous[~first],rho[~first]**2*inv[~first])
    ab=np.zeros((2,n));ab[0]=diagonal
    # Each team occupies a contiguous time-ordered block.
    if np.any(previous[~first] != np.flatnonzero(~first)-1):raise ValueError("Noncontiguous Markov chain")
    js=np.flatnonzero(~first);ab[1,js-1]=-rho[js]*inv[js]
    return cholesky_banded(ab,lower=True,check_finite=False)


def kernels(design,team_taus=(30,365,730,1460,3650),time_taus=(30,365,730,1460,2920)):
    n=design.n;ev=design.team_events
    team_days=np.zeros(ev["n"])
    team_days[ev["home"]]=design.days;team_days[ev["away"]]=design.days
    rr=np.tile(np.arange(n),2);cc=np.r_[ev["home"],ev["away"]]
    minus=sparse.csr_matrix((np.r_[np.ones(n),-np.ones(n)]/math.sqrt(2),(rr,cc)),shape=(n,ev["n"]))
    plus=sparse.csr_matrix((np.ones(2*n)/math.sqrt(2),(rr,cc)),shape=(n,ev["n"]))
    pair=sparse.csr_matrix((np.ones(n),(np.arange(n),design.pair)),shape=(n,design.npairs))
    calendar=sparse.csr_matrix((np.ones(n),(np.arange(n),design.date_index)),shape=(n,len(design.unique_days)))
    result=[CovarianceKernel("independent",None),CovarianceKernel("pair",pair)]
    for tau in team_taus:
        factor=ou_precision_factor(team_days,ev["prev"],tau)
        result.extend([CovarianceKernel(f"minus:{tau}",minus,factor),CovarianceKernel(f"plus:{tau}",plus,factor)])
    for tau in time_taus:result.append(CovarianceKernel(f"time:{tau}",calendar,ou_precision_factor(design.unique_days,tau=tau)))
    return result


def raw_pair_entries(design,kernel,i,j):
    if kernel.label=="independent":return (i==j).astype(float)
    if kernel.label=="pair":return (design.pair[i]==design.pair[j]).astype(float)
    kind,scale=kernel.label.split(":");gap=np.abs(design.days[i]-design.days[j])
    value=np.exp(-gap/float(scale))
    if kind=="time":return value
    same=(design.home[i]==design.home[j]).astype(float)+(design.away[i]==design.away[j])
    cross=(design.home[i]==design.away[j]).astype(float)+(design.away[i]==design.home[j])
    return value*(same-cross if kind=="minus" else same+cross)/2


class RestrictedMoments:
    """Eliminate the common unknown mean in every covariance equation.

    For r=M Y and mu in col(X): E(r_i r_j)=(M Sigma M')_ij.
    The corrected design is built once, never from football outcomes.
    """
    def __init__(self,design,pairs,team_taus=(30,365,730,1460,3650),time_taus=(30,365,730,1460,2920),progress=None):
        self.design=design;self.X=design.X;self.X_dense=self.X.toarray()
        self.R=pinvh((self.X.T @ self.X).toarray(),rtol=1e-11)
        self.rank=int(np.linalg.matrix_rank((self.X.T @ self.X).toarray(),tol=1e-8))
        self.kernels=kernels(design,team_taus,time_taus);self.labels=[k.label for k in self.kernels]
        n=design.n
        self.i=np.r_[np.arange(n),pairs["i"]];self.j=np.r_[np.arange(n),pairs["j"]]
        strata=np.r_[np.full(n,25),pairs["relation"]*5+pairs["lag"]]
        count=np.bincount(strata,minlength=26)
        # Give each observed metadata stratum equal total squared weight.
        self.weight=1/np.sqrt(count[strata])
        self.diagonal_rows=n
        XR=self.X_dense @ self.R
        self.corrected=np.zeros((len(self.i),len(self.kernels)))
        self.naive=np.zeros_like(self.corrected)
        self.target_variance=np.zeros((design.A.shape[0],len(self.kernels)))
        A=design.A.toarray()
        self.target_covariance=np.zeros((len(self.kernels),len(A),len(A)))
        for k,kernel in enumerate(self.kernels):
            KX=kernel.apply(self.X_dense)
            RKR=self.R @ (self.X.T @ KX) @ self.R
            raw=raw_pair_entries(design,kernel,self.i,self.j)
            correction=np.einsum("ij,ij->i",XR[self.i],KX[self.j])+np.einsum("ij,ij->i",KX[self.i],XR[self.j])
            correction-=np.einsum("ij,ij->i",self.X_dense[self.i]@RKR,self.X_dense[self.j])
            self.corrected[:,k]=raw-correction;self.naive[:,k]=raw
            KA=kernel.apply(A.T)
            C=A @ KA;self.target_covariance[k]=(C+C.T)/2
            self.target_variance[:,k]=np.diag(C)
            if progress:progress(kernel.label)
        self.operators={}
        for name,B in (("uncorrected",self.naive),("restricted",self.corrected)):
            Q,R=qr(B*self.weight[:,None],mode="economic",check_finite=False)
            self.operators[name]=(Q,R)
        self.coarse=[j for j,s in enumerate(self.labels) if s in ("independent","pair","minus:365","plus:365","time:365","time:1460")]
        self.operators["coarse"]=qr(self.corrected[:,self.coarse]*self.weight[:,None],mode="economic",check_finite=False)
        self.singular_values=np.linalg.svd(self.corrected*self.weight[:,None],compute_uv=False)
        self.floor=.25*np.asarray(design.A.multiply(design.A).sum(axis=1)).ravel()

    def residual(self,Y):
        Y=np.asarray(Y,float)
        return Y-self.X @ (self.R @ (self.X.T @ Y))

    def fit(self,y,corrected=True,coarse=False):
        y=np.asarray(y,float);r=self.residual(y)
        moment=r[self.i]*r[self.j]
        Q,R=self.operators["coarse" if coarse else "restricted" if corrected else "uncorrected"]
        z=Q.T @ (moment*self.weight)
        theta,residual_norm=nnls(R,z,maxiter=1000)
        if coarse:
            full=np.zeros(len(self.labels));full[self.coarse]=theta;theta=full
        variance=np.maximum(self.target_variance @ theta,self.floor)
        variance=np.maximum(variance,0)
        mean_coeff=self.R @ (self.X.T @ y)
        return dict(theta=theta,variance=variance,mean_coeff=mean_coeff,
                    moment_residual_norm=float(residual_norm),
                    scale=np.sqrt(variance),all_constant=bool(np.all(y==y[0])),
                    corrected=corrected,mean_fit_outside_unit_interval=int(np.sum((self.X @ mean_coeff<0)|(self.X @ mean_coeff>1))))

    def save(self,path):
        arrays=dict(R=self.R,i=self.i,j=self.j,weight=self.weight,corrected=self.corrected,naive=self.naive,
                    target_variance=self.target_variance,target_covariance=self.target_covariance,
                    singular_values=self.singular_values,floor=self.floor,rank=self.rank,coarse=self.coarse,
                    labels=np.asarray(self.labels))
        for name,(Q,R) in self.operators.items():arrays[name+"_Q"]=Q;arrays[name+"_R"]=R
        np.savez_compressed(path,**arrays)

    @classmethod
    def load(cls,design,path):
        obj=cls.__new__(cls);obj.design=design;obj.X=design.X;obj.X_dense=None
        with np.load(path,allow_pickle=False) as src:
            for name in ("R","i","j","weight","corrected","naive","target_variance","target_covariance","singular_values","floor"):
                setattr(obj,name,src[name])
            obj.labels=src["labels"].tolist();obj.rank=int(src["rank"]);obj.coarse=src["coarse"].tolist()
            obj.operators={name:(src[name+"_Q"],src[name+"_R"]) for name in ("uncorrected","restricted","coarse")}
        obj.kernels=kernels(design)
        if obj.labels!=[k.label for k in obj.kernels]:raise ValueError("Cache kernel mismatch")
        return obj

    def joint_gls(self,y,theta,rtol=1e-8,maxiter=2000):
        """Henderson/GLS solution without an N-squared matrix.

        Solve (M Sigma M + H)alpha=M y, then recover beta and component
        conditional means. This couples the mean and slow common process.
        """
        theta=np.asarray(theta,float).copy();ridge=max(1e-10,theta.sum()*1e-6)
        def cov(v):
            result=ridge*np.asarray(v)
            for weight,kernel in zip(theta,self.kernels):
                if weight>0:result+=weight*kernel.apply(v)
            return result
        def matvec(v):
            mv=self.residual(v);return self.residual(cov(mv))+v-mv
        rhs=self.residual(y);iterations=[]
        op=LinearOperator((self.design.n,self.design.n),matvec=matvec,dtype=float)
        alpha,info=cg(op,rhs,rtol=rtol,atol=0,maxiter=maxiter,callback=lambda x:iterations.append(1))
        if info!=0:raise RuntimeError("Joint GLS did not converge:"+str(info))
        beta=self.R @ (self.X.T @ (y-cov(alpha)))
        components={k.label:w*k.apply(alpha) for w,k in zip(theta,self.kernels) if w>0 and k.label!="independent"}
        residual_error=float(np.linalg.norm(matvec(alpha)-rhs)/max(1,np.linalg.norm(rhs)))
        return dict(beta=beta,alpha=alpha,components=components,iterations=len(iterations),
                    relative_equation_residual=residual_error,noise_ridge=ridge,
                    mean=self.X @ beta,working_Gaussian_decomposition_not_a_binary_probability_forecast=True)


def family_scores(design,estimate,truth,scale):
    score={}
    for family,js in design.families.items():
        active=np.array(js)[scale[js]>0]
        err=np.abs(estimate[active]-truth[active])
        score[family]=float(np.max(err/scale[active])) if len(active) else 0.
    return score


def calibrated_halfwidth(design,fit,critical):
    half=np.zeros(len(design.targets))
    for f,ids in design.families.items():half[ids]=critical[f]*fit["scale"][ids]
    if fit["all_constant"]:half=np.maximum(half,design.span)
    return half


def finite_calibration_critical(scores,alpha=.025):
    scores=np.asarray(scores,float);rank=math.ceil((len(scores)+1)*(1-alpha))
    return float(np.sort(scores)[rank-1]) if rank<=len(scores) else float("inf")
