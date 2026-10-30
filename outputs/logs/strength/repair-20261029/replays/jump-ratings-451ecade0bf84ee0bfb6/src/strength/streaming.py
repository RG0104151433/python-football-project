"""Bounded-memory jump approximation; all event mass and prior moments retained.

This Gaussianizes conditional Poisson counts. It is not exact jump filtering.
Online moment merges depend on deterministic child order; budget and partition
checks remain mandatory. Representative paths cannot identify true jump dates.
"""
from datetime import date
import math
import numpy as np
from .filter import StrengthFilter, Component, batch_update, probabilities, NumericalFailure
from .reduction import cluster, moments


def partitions(mu, order=1):
    mu=np.asarray(mu,dtype=float)
    if order not in (0,1) or np.any(mu<0) or not np.isfinite(mu).all():
        raise ValueError("Invalid event partition")
    total=float(mu.sum())
    if total==0:return [(1.,np.zeros(len(mu)),"no_jump")]
    p0=math.exp(-total)
    result=[(p0,np.zeros(len(mu)),"no_jump")]
    if order==1:
        for i,m in enumerate(mu):
            if m==0:continue
            positive=-math.expm1(-m)
            weight=positive*math.exp(-(total-m))
            counts=np.zeros(len(mu));counts[i]=m/positive
            result.append((weight,counts,"one_positive_team"))
        remaining=mu*(-np.expm1(-(total-mu)))
    else:remaining=mu.copy()
    residual=float(1-np.sum(np.array([w for w,_,_ in result],dtype=np.longdouble)))
    if residual>1e-15:
        result.append((residual,remaining/residual,"residual_positive_teams"))
    elif np.max(abs(remaining))>1e-12:
        raise NumericalFailure("Residual event probability underflow")
    weights=sum(w for w,_,_ in result)
    result=[(w/weights,c,label) for w,c,label in result if w>0]
    if np.max(abs(sum(w*c for w,c,_ in result)-mu))>1e-10:
        raise NumericalFailure("Event partition lost prior moments")
    return result


class StreamingStrengthFilter(StrengthFilter):
    def day(self,day,games):
        if not games or self.last_day is not None and day<=self.last_day:
            raise ValueError("Complete date batches must advance")
        games=sorted(games,key=lambda g:g["match_id"])
        if len({g["match_id"] for g in games})!=len(games):raise ValueError("Duplicate match")
        if any(g["venue"] not in {-1,0,1} or g["outcome"] not in {0,1,2} for g in games):
            raise ValueError("Invalid observation")
        active=sorted({g[k] for g in games for k in ("home","away")})
        if not set(active).issubset(self.index):raise ValueError("Unknown team")
        dt=np.array([(date.fromisoformat(day)-date.fromisoformat(self.last.get(t,day))).days/365.2425 for t in active])
        parts=partitions(self.params["jump_rate"]*dt,self.numerics.get("event_partition_order",1))
        design=self.design(games)
        kappas=[(1-self.params["epsilon"])*(self.params["alpha"] if g["friendly"] else 1) for g in games]
        budget=self.numerics["max_components"]
        n=len(self.teams)+1
        estimated=(4*budget+6)*n*n*8
        if estimated>self.numerics.get("max_child_bytes",math.inf):
            raise NumericalFailure("Streaming covariance buffer budget exceeded")
        predicted=np.zeros((len(games),3));prior_mean=np.zeros(n);prior_second=np.zeros((n,n))
        buffer=[];scale=-math.inf;merges=0;underflow=0;max_iter=0;peak=0

        def compress(target):
            nonlocal buffer,merges
            mass=sum(c.weight for c in buffer)
            for c in buffer:c.weight/=mass
            before_m,before_c=moments(buffer)
            reduced,_=cluster(buffer,target,self.numerics.get("cluster_iterations",30))
            after_m,after_c=moments(reduced)
            if max(np.max(abs(before_m-after_m)),np.max(abs(before_c-after_c)))>1e-8:
                raise NumericalFailure("Streaming merge lost full moments")
            for c in reduced:c.weight*=mass
            buffer=reduced;merges+=1

        for parent in self.components:
            for weight,counts,label in parts:
                w=parent.weight*weight
                cov=parent.cov.copy()
                for k,t in enumerate(active):
                    i=self.index[t];cov[i,i]+=self.params["q"]*dt[k]+counts[k]*self.params["jump_sd"]**2
                prior_mean+=w*parent.mean
                prior_second+=w*(cov+np.outer(parent.mean,parent.mean))
                pm=design@parent.mean;pc=design@cov@design.T
                for k in range(len(games)):
                    predicted[k]+=w*probabilities(pm[k],pc[k,k],self.params["delta"],kappas[k])
                m,c,logz,diag=batch_update(parent.mean,cov,design,[g["outcome"] for g in games],kappas,
                                           self.params["delta"],self.numerics)
                max_iter=max(max_iter,diag["iterations"])
                lw=math.log(w)+logz
                if lw>scale:
                    for comp in buffer:comp.weight*=math.exp(scale-lw)
                    scale=lw
                post_weight=math.exp(lw-scale)
                if post_weight==0:underflow+=1;continue
                buffer.append(Component(post_weight,m,c,(("partition",label),)))
                peak=max(peak,len(buffer))
                if len(buffer)>=4*budget:compress(2*budget)
        compress(budget)
        mass=sum(c.weight for c in buffer)
        for c in buffer:c.weight/=mass
        self.components=buffer
        prior_cov=prior_second-np.outer(prior_mean,prior_mean)
        rows=[]
        for k,g in enumerate(games):
            i,j=self.index[g["home"]],self.index[g["away"]]
            rows.append(dict(match_id=g["match_id"],date=day,home=g["home"],away=g["away"],
                p_home=float(predicted[k,0]),p_draw=float(predicted[k,1]),p_away=float(predicted[k,2]),
                difference=float(prior_mean[i]-prior_mean[j]),
                difference_variance=float(prior_cov[i,i]+prior_cov[j,j]-2*prior_cov[i,j]),
                outcome_index=g["outcome"],prediction_cutoff=self.last_day or "initial_prior"))
        for c in self.components:
            if not np.isfinite(c.cov).all() or np.diag(c.cov).min()<=0:raise NumericalFailure("Invalid streaming covariance")
        if (len(self.diagnostics)+1)%25==0:
            if any(np.linalg.eigvalsh(c.cov).min() < -self.numerics["psd_tolerance"] for c in self.components):
                raise NumericalFailure("Streaming retained covariance not PSD")
        for t in active:self.last[t]=day
        for g in games:self.counts[g["home"]]+=1;self.counts[g["away"]]+=1
        self.last_day=day
        self.diagnostics.append(dict(date=day,matches=len(games),event_parts=len(parts),
            retained=len(buffer),peak_covariance_buffer=peak,covariance_budget_estimate_bytes=estimated,
            merges=merges,underflow_weights=underflow,max_ep_iterations=max_iter,
            prior_mass_discarded=0,path_semantics="representative_only"))
        return rows
