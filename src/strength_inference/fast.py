"""Numerically equivalent cached queries and sparse frozen scenario operators.

Only pure Poisson count weights are cached. Filtering, EP tolerance and the
full covariance remain those of the adopted collapsed-jump implementation.
"""
from collections import defaultdict
from datetime import date
from functools import lru_cache
import numpy as np
from scipy.special import ndtr
from scipy.sparse import csr_matrix
import src.strength.collapsed_jump as cj
from src.strength_joint.design import Design
from src.strength_joint.model import Kernel
from src.strength_stage6_sensitivity import read, materialize
from src.strength.io import ROOT


def install_count_cache():
    if getattr(cj.count_weights, "_inference_cached", False):
        return
    original = cj.count_weights
    @lru_cache(maxsize=65536)
    def cached(mu, tolerance):
        result = original(mu, tolerance)
        result.setflags(write=False)
        return result
    cached._inference_cached = True
    cj.count_weights = cached


def query(engine, day, batch):
    """Same lazy prior as worlds.before_day, vectorized probability-only query."""
    if engine.last_day is not None and day <= engine.last_day:
        raise ValueError("INVALID_QUERY_DATE")
    rows, means, variances, kappas, intensities = [], [], [], [], []
    gd = (date.fromisoformat(day)-date.fromisoformat(engine.last_day)).days/365.2425 if engine.last_day else 0.
    for g in batch:
        i,j=(engine.index[g[k]] for k in ("home","away"))
        h=len(engine.teams)+(int(g["friendly"]) if engine.home_dimensions==2 else 0)
        ds=[(date.fromisoformat(day)-date.fromisoformat(engine.last.get(g[k],day))).days/365.2425 for k in ("home","away")]
        nh,na=(engine.params["jump_rate"]*d for d in ds)
        base=engine.cov[i,i]+engine.cov[j,j]-2*engine.cov[i,j]+engine.params["q"]*sum(ds)
        venue=g["venue"]
        means.append(engine.mean[i]-engine.mean[j]+venue*engine.mean[h])
        variances.append(base+venue**2*(engine.cov[h,h]+engine.params.get("home_q",0)*gd)+2*venue*(engine.cov[i,h]-engine.cov[j,h]))
        kappas.append((1-engine.params["epsilon"])*(engine.params["alpha"] if g["friendly"] else 1))
        intensities.append(nh+na)
        rows.append(dict(match_id=g["match_id"],date=day,strength_difference=float(engine.mean[i]-engine.mean[j]),
            strength_difference_base_variance=float(base),home_jump_intensity=nh,away_jump_intensity=na,
            jump_scale_sd=engine.params["jump_sd"],strength_difference_variance=float(base+(nh+na)*engine.params["jump_sd"]**2),
            prediction_cutoff=engine.last_day or "initial_prior",home_history=engine.counts[g["home"]],
            away_history=engine.counts[g["away"]],cold_start=min(engine.counts[g["home"]],engine.counts[g["away"]])<5))
    tolerance=engine.numerics.get("poisson_tail_tolerance",1e-12)
    weights=[cj.count_weights(float(mu),tolerance) for mu in intensities]
    cap=max(map(len,weights));w=np.zeros((len(batch),cap))
    for i,v in enumerate(weights):w[i,:len(v)]=v
    sd=np.sqrt(1+np.array(variances)[:,None]+engine.params["jump_sd"]**2*np.arange(cap))
    mu=np.array(means)[:,None];delta=engine.params["delta"];k=np.array(kappas)
    upper=ndtr((delta-mu)/sd);lower=ndtr((-delta-mu)/sd)
    home=k*np.sum(w*ndtr((mu-delta)/sd),axis=1)+(1-k)/3
    draw=k*np.sum(w*(upper-lower),axis=1)+(1-k)/3
    away=k*np.sum(w*lower,axis=1)+(1-k)/3
    return rows,np.column_stack((home,draw,away))


class FrozenTargets:
    """Outcome-free sparse scenario matrices; scores are rerated in every world."""
    def __init__(self,c):
        self.rows=c['rows'];self.ids=[r['match_id'] for r in self.rows]
        self.index={mid:i for i,mid in enumerate(self.ids)};self.design=Design(self.rows)
        self.registry=c['registry'];self.x,self.names=self.design.matrix(self.rows,'M0_nested')
        prep=ROOT/c['cfg']['preparation'];members=defaultdict(list);pieces=defaultdict(list)
        for r in read(prep/'reference_membership.csv.gz'):members[r['reference_id']].append(r['match_id'])
        for r in read(prep/'scenario_mixtures.csv'):pieces[r['target_id'],r['reference_kind'],r['arm']].append(r)
        row_index={r['match_id']:r for r in self.rows};self.operators={}
        for item in self.registry:
            tid=item['target_id']
            if tid in self.operators:continue
            ids=members[item['reference_id']];arms=[]
            for arm,sign in [('1',1),('2',-1)]:
                for mass,rr in materialize(pieces[tid,item['reference_kind'],arm],ids,row_index):
                    indices=np.array([self.index[r['match_id']] for r in rr],dtype=np.int32)
                    x,names=self.design.matrix(rr,'M0_nested')
                    if names!=self.names:raise ValueError('FROZEN_DESIGN_CHANGED')
                    arms.append((sign*mass,indices,csr_matrix(x)))
            self.operators[tid]=arms

    def evaluate(self,beta0,theta3,rows,gradients=False):
        kernel=Kernel(rows);b=float(np.exp(theta3[-1]));beta3=np.array(theta3[:-1]);beta0=np.array(beta0)
        vv=kernel.v;ww=np.exp(kernel.logw);mu=kernel.mu
        delta={};jac={}
        for tid,operators in self.operators.items():
            d0=d3=0.;j0=np.zeros(len(beta0));j3=np.zeros(len(theta3))
            for mass,idx,x in operators:
                e0=x@beta0;e3=x@beta3;t=e3+b*mu[idx]
                scale=np.sqrt(1+b*b*vv[idx]);z=t[:,None]/scale
                p3=np.sum(ww[idx]*ndtr(z),axis=1)
                d0+=mass*float(ndtr(e0).mean());d3+=mass*float(p3.mean())
                if gradients:
                    phi=np.exp(-z*z/2)/np.sqrt(2*np.pi)
                    ge=np.sum(ww[idx]*phi/scale,axis=1)
                    gb=np.sum(ww[idx]*phi*(mu[idx,None]/scale-t[:,None]*b*vv[idx]/scale**3),axis=1)*b
                    j0+=mass*np.asarray(x.T@(np.exp(-e0*e0/2)/np.sqrt(2*np.pi))).ravel()/len(idx)
                    j3[:-1]+=mass*np.asarray(x.T@ge).ravel()/len(idx);j3[-1]+=mass*float(gb.mean())
            delta[tid]=(100*d0,100*d3);jac[tid]=(100*j0,100*j3)
        values=[];jj=[]
        for item in self.registry:
            d0,d3=delta[item['target_id']];j0,j3=jac[item['target_id']]
            paired=item['effect_size_axis']=='paired_change'
            values.append(d3-d0 if paired else d3)
            jj.append(np.r_[-j0 if paired else np.zeros(len(beta0)),j3])
        return np.array(values),np.array(jj)
