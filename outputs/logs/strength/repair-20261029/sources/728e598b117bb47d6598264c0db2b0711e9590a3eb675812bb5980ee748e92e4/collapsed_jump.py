"""Collapsed Poisson-jump likelihood EP with conditional jump reconstruction.

No prior count Gaussianization. Disjoint matches have independent jump noises;
shared-team matches form block factors sharing the SAME jump. Global posterior
is projected to one full Gaussian only at the end of each date (ADF across days).
EP convergence is not proof of exact long-history filtering.
"""
import itertools
import math
from datetime import date
import numpy as np
from scipy.special import ndtr,logsumexp
from scipy.stats import poisson
from .filter import batch_update,outcome_moments,NumericalFailure
from .gaussian import GaussianStrengthFilter


def count_weights(mu,tolerance):
    if mu==0:return np.ones(1)
    cap=int(poisson.isf(max(tolerance,1e-15),mu))
    while poisson.sf(cap,mu)>tolerance:cap+=1
    if cap>100:raise NumericalFailure("Poisson count support exceeds guarded budget")
    w=poisson.pmf(np.arange(cap+1),mu)
    if poisson.sf(cap,mu)>tolerance*1.001:raise NumericalFailure("Poisson tail gate")
    return w/w.sum()


def convolved_moments(means,variances,outcomes,kappas,mus,delta,jump_variance,tolerance):
    means,variances=np.asarray(means),np.asarray(variances)
    mus=np.asarray(mus);outcomes=np.asarray(outcomes);kappas=np.asarray(kappas)
    weights=[count_weights(float(mu),tolerance) for mu in mus];n=max(map(len,weights))
    ww=np.zeros((len(mus),n))
    for i,w in enumerate(weights):ww[i,:len(w)]=w
    vv=variances[:,None]+jump_variance*np.arange(n)[None,:]
    sd=np.sqrt(1+vv);z=means[:,None];k=kappas[:,None]
    lower=np.choose(outcomes,[delta,-delta,-np.inf])[:,None]
    upper=np.choose(outcomes,[np.inf,delta,-delta])[:,None]
    lo=(lower-z)/sd;hi=(upper-z)/sd
    p=np.where(lo>0,ndtr(-lo)-ndtr(-hi),ndtr(hi)-ndtr(lo))
    pl=np.exp(-.5*lo**2)/math.sqrt(2*math.pi);ph=np.exp(-.5*hi**2)/math.sqrt(2*math.pi)
    lpl=np.zeros_like(lo);hph=np.zeros_like(hi)
    np.multiply(lo,pl,out=lpl,where=np.isfinite(lo));np.multiply(hi,ph,out=hph,where=np.isfinite(hi))
    evidence=(ww*(k*p+(1-k)/3)).sum(axis=1)
    first=(ww*k*(pl-ph)/sd).sum(axis=1)/evidence
    second=(ww*k*(lpl-hph)/(sd*sd)).sum(axis=1)/evidence
    tm=means+variances*first;tv=variances+variances**2*(second-first**2)
    if np.any(tv<=0) or not np.isfinite(tv).all():raise NumericalFailure("Invalid collapsed scalar moment")
    return evidence,tm,tv


def single_local(mean,variance,outcome,kappa,mu_home,mu_away,delta,jv,tolerance):
    """Exact local moments of (old performance, Jhome, Jaway), binomial counts."""
    total=mu_home+mu_away;weights=count_weights(total,tolerance)
    fraction=mu_home/total if total else .5
    z=[];vv=[];seconds=[];der=[];raw_vars=[]
    for n,w in enumerate(weights):
        evidence,_,_,g,c=outcome_moments(mean,variance+n*jv,outcome,delta,kappa)
        eh=n*fraction;ea=n-eh;vb=n*fraction*(1-fraction)
        v=np.array([variance,eh*jv,-ea*jv]);v2=np.outer(v,v)
        v2[1,1]+=vb*jv*jv;v2[2,2]+=vb*jv*jv
        v2[1,2]+=vb*jv*jv;v2[2,1]+=vb*jv*jv
        z.append(w*evidence);vv.append(v);seconds.append(v2*(c+g*g));der.append(g)
        raw_vars.append([variance,eh*jv,ea*jv])
    z=np.array(z);z/=z.sum();vv=np.array(vv);shift=np.sum(z[:,None]*np.array(der)[:,None]*vv,axis=0)
    cov=np.diag(z@np.array(raw_vars))+np.einsum('n,nij->ij',z,np.array(seconds))-np.outer(shift,shift)
    return np.array([mean,0.,0.])+shift,(cov+cov.T)/2


def block_local(mean,cov,outcomes,kappas,incidence,mus,delta,jv,num,tolerance):
    """Shared-team count sum, with Gaussian-EP component evidence/moments."""
    total=float(sum(mus));cap=len(count_weights(total,tolerance))-1
    m=len(mean);t=len(mus);prior=np.zeros((m+t,m+t));prior[:m,:m]=cov
    design=np.concatenate((np.eye(m),incidence),axis=1)
    logs=[];means=[];covs=[]
    for n in range(cap+1):
        for choices in itertools.combinations_with_replacement(range(t),n):
            counts=np.bincount(choices,minlength=t)
            if np.any((np.array(mus)==0)&(counts>0)):continue
            logp=-total+sum(int(k)*math.log(mu)-math.lgamma(int(k)+1) for k,mu in zip(counts,mus) if mu>0)
            cc=prior.copy();cc[m:,m:]=np.diag(counts*jv)
            mm,vc,lz,_=batch_update(np.r_[mean,np.zeros(t)],cc,design,outcomes,kappas,delta,num)
            logs.append(logp+lz);means.append(mm);covs.append(vc)
    if len(logs)>50000:raise NumericalFailure("Shared-team local count budget")
    weights=np.exp(np.array(logs)-logsumexp(logs));means=np.array(means)
    mu=weights@means;center=means-mu
    vc=np.einsum('n,nij->ij',weights,np.array(covs))+np.einsum('n,ni,nj->ij',weights,center,center)
    return mu,(vc+vc.T)/2


def components(games):
    remaining=set(range(len(games)));groups=[]
    while remaining:
        group={min(remaining)};teams={games[min(remaining)][k] for k in ('home','away')}
        changed=True
        while changed:
            more={i for i in remaining-group if games[i]['home'] in teams or games[i]['away'] in teams}
            changed=bool(more);group|=more
            teams|={games[i][k] for i in more for k in ('home','away')}
        remaining-=group;groups.append(sorted(group))
    return groups


def jump_update(mean,cov,design,games,index,mus,params,num):
    pm=design@mean;cross=cov@design.T;pc=design@cross
    eig,vec=np.linalg.eigh((pc+pc.T)/2);keep=eig>num['rank_tolerance']
    root=vec[:,keep]*np.sqrt(eig[keep]);gain=(cross@vec[:,keep])/np.sqrt(eig[keep])
    m=len(games);r=root.shape[1];T=np.zeros((m,m));eta=np.zeros(m)
    outcomes=np.array([g['outcome'] for g in games]);ks=np.array([(1-params['epsilon'])*(params['alpha'] if g['friendly'] else 1) for g in games])
    groups=components(games);single=np.array([g[0] for g in groups if len(g)==1],dtype=int)
    blocks=[g for g in groups if len(g)>1]
    tol=num.get('poisson_tail_tolerance',1e-12)/max(1,m)
    mg=np.array([mus[g['home']]+mus[g['away']] for g in games]);jv=params['jump_sd']**2

    def posterior(tt,ee):
        precision=np.eye(r)+root.T@tt@root
        np.linalg.cholesky(precision)
        cw=np.linalg.inv(precision);mw=cw@root.T@(ee-tt@pm)
        return pm+root@mw,root@cw@root.T,mw,cw

    def cavity(qm,qc,ids):
        cc=qc[np.ix_(ids,ids)];inv=np.linalg.inv(cc)
        prec=inv-T[np.ix_(ids,ids)];np.linalg.cholesky(prec)
        cv=np.linalg.inv(prec);cm=cv@(inv@qm[ids]-eta[ids]);return cm,cv

    def block_tilt(ids,cm,cv):
        teams=sorted({games[i][k] for i in ids for k in ('home','away')});inc=np.zeros((len(ids),len(teams)))
        for a,i in enumerate(ids):inc[a,teams.index(games[i]['home'])]=1;inc[a,teams.index(games[i]['away'])]=-1
        tm,tv=block_local(cm,cv,outcomes[ids],ks[ids],inc,[mus[t] for t in teams],params['delta'],jv,num,tol)
        return teams,tm,tv

    for iteration in range(1,num['ep_max_iter']+1):
        qm,qc,_,_=posterior(T,eta);newT=np.zeros_like(T);neweta=np.zeros_like(eta)
        if len(single):
            precision=1/np.diag(qc)[single]-np.diag(T)[single]
            if np.any(precision<=0):raise NumericalFailure("Collapsed cavity precision")
            cv=1/precision;cm=cv*(qm[single]/np.diag(qc)[single]-eta[single])
            _,tm,tv=convolved_moments(cm,cv,outcomes[single],ks[single],mg[single],params['delta'],jv,tol)
            newT[single,single]=1/tv-1/cv;neweta[single]=tm/tv-cm/cv
        for ids in blocks:
            cm,cv=cavity(qm,qc,ids);_,tm,tv=block_tilt(ids,cm,cv);inv=np.linalg.inv(tv[:len(ids),:len(ids)])
            newT[np.ix_(ids,ids)]=inv-np.linalg.inv(cv);neweta[ids]=inv@tm[:len(ids)]-np.linalg.solve(cv,cm)
        dT=newT-T;de=neweta-eta;damping=num.get('ep_damping',.5)
        for attempt in range(18):
            tt=T+damping*dT;ee=eta+damping*de
            try:
                mm,cc,_,_=posterior(tt,ee)
                if len(single) and np.any(1/np.diag(cc)[single]-np.diag(tt)[single]<=0):raise np.linalg.LinAlgError()
                for ids in blocks:np.linalg.cholesky(np.linalg.inv(cc[np.ix_(ids,ids)])-tt[np.ix_(ids,ids)])
                break
            except np.linalg.LinAlgError:damping*=.5
        else:raise NumericalFailure("Collapsed EP damping failed")
        error=max(float(np.max(abs(tt-T))),float(np.max(abs(ee-eta))))
        T,eta=tt,ee
        if error<num['ep_tolerance']:break
    else:raise NumericalFailure("Collapsed EP did not converge")
    qm,qc,mw,cw=posterior(T,eta)
    F=gain.copy();shift=np.zeros(len(mean));residual=np.zeros_like(cov)
    for ids in groups:
        cm,cv=cavity(qm,qc,ids)
        if len(ids)==1:
            i=ids[0];g=games[i];teams=[g['home'],g['away']]
            tm,tv=single_local(cm[0],cv[0,0],outcomes[i],ks[i],mus[g['home']],mus[g['away']],params['delta'],jv,tol)
        else:teams,tm,tv=block_tilt(ids,cm,cv)
        n=len(ids);cu=tv[:n,:n];B=tv[n:,:n]@np.linalg.inv(cu)
        rr=tv[n:,n:]-B@tv[:n,n:];rr=(rr+rr.T)/2
        if np.linalg.eigvalsh(rr).min() < -1e-8:raise NumericalFailure("Conditional jump residual not PSD")
        positions=[index[t] for t in teams]
        F[positions]+=B@root[ids]
        shift[positions]+=tm[n:]+B@(pm[ids]-tm[:n])
        residual[np.ix_(positions,positions)]+=rr
    post_mean=mean+shift+F@mw
    post_cov=cov-gain@gain.T+F@cw@F.T+residual
    return post_mean,(post_cov+post_cov.T)/2,iteration,len(blocks)


class CollapsedJumpFilter(GaussianStrengthFilter):
    def __init__(self,teams,params,numerics,team_variance=1.,home_variance=.25):
        super().__init__(teams,dict(params,jump_rate=0),numerics,team_variance,home_variance)
        if params['jump_rate']<0 or params['jump_sd']<0:raise ValueError('Invalid jump model')
        self.params=dict(params)

    def day(self,day,games):
        if not games or self.last_day is not None and day<=self.last_day:raise ValueError('Date must advance')
        games=sorted(games,key=lambda g:g['match_id'])
        if len({g['match_id'] for g in games})!=len(games):raise ValueError('Duplicate match')
        active={g[k] for g in games for k in ('home','away')}
        if not active.issubset(self.index):raise ValueError('Unknown team')
        mus={}
        for t in active:
            dt=(date.fromisoformat(day)-date.fromisoformat(self.last.get(t,day))).days/365.2425
            self.cov[self.index[t],self.index[t]]+=self.params['q']*dt;mus[t]=self.params['jump_rate']*dt
        if self.last_day:
            dt=(date.fromisoformat(day)-date.fromisoformat(self.last_day)).days/365.2425
            for h in range(len(self.teams),len(self.mean)):self.cov[h,h]+=self.params.get('home_q',0)*dt
        A=np.zeros((len(games),len(self.mean)));rows=[]
        for k,g in enumerate(games):
            if g['home']==g['away'] or g['venue'] not in (-1,0,1) or g['outcome'] not in (0,1,2):raise ValueError('Invalid match')
            i,j=self.index[g['home']],self.index[g['away']];h=len(self.teams)+(int(g['friendly']) if self.home_dimensions==2 else 0)
            A[k,i]=1;A[k,j]=-1;A[k,h]=g['venue']
            mu=float(A[k]@self.mean);var=float(A[k]@self.cov@A[k]);kappa=(1-self.params['epsilon'])*(self.params['alpha'] if g['friendly'] else 1)
            p=[float(convolved_moments([mu],[var],[y],[kappa],[mus[g['home']]+mus[g['away']]],self.params['delta'],self.params['jump_sd']**2,
                self.numerics.get('poisson_tail_tolerance',1e-12))[0][0]) for y in range(3)]
            vh=self.cov[i,i]+mus[g['home']]*self.params['jump_sd']**2
            va=self.cov[j,j]+mus[g['away']]*self.params['jump_sd']**2
            rows.append(dict(match_id=g['match_id'],date=day,home=g['home'],away=g['away'],
                home_mean=float(self.mean[i]),away_mean=float(self.mean[j]),home_variance=float(vh),away_variance=float(va),
                home_away_covariance=float(self.cov[i,j]),difference=float(self.mean[i]-self.mean[j]),
                difference_variance=float(vh+va-2*self.cov[i,j]),home_term=float(self.mean[h]),home_term_variance=float(self.cov[h,h]),
                venue=g['venue'],friendly=g['friendly'],p_home=p[0],p_draw=p[1],p_away=p[2],
                home_history=self.counts[g['home']],away_history=self.counts[g['away']],
                cold_start=min(self.counts[g['home']],self.counts[g['away']])<5,
                previously_disconnected=self.find(g['home'])!=self.find(g['away']),outcome_index=g['outcome'],
                prediction_cutoff=self.last_day or 'initial_prior',prediction_basis='collapsed_jump_pre_day; Gaussian_ADF_at_day_boundary'))
        self.mean,self.cov,it,blocks=jump_update(self.mean,self.cov,A,games,self.index,mus,self.params,self.numerics)
        self.days+=1
        if not np.isfinite(self.cov).all() or np.diag(self.cov).min()<=0:raise NumericalFailure('Invalid jump covariance')
        if self.days%50==0 and np.linalg.eigvalsh(self.cov).min() < -1e-8:raise NumericalFailure('Jump covariance not PSD')
        for g in games:
            self.counts[g['home']]+=1;self.counts[g['away']]+=1;self.parent[self.find(g['home'])]=self.find(g['away'])
        for t in active:self.last[t]=day
        self.last_day=day;self.diagnostics.append(dict(date=day,matches=len(games),ep_iterations=it,shared_team_blocks=blocks))
        return rows

    def state(self):
        state=super().state();state['schema_version']='strength-collapsed-jump-v1';return state

    @classmethod
    def restore(cls,s):
        if s['schema_version']!='strength-collapsed-jump-v1':raise ValueError('Wrong checkpoint')
        normal=dict(s,schema_version='strength-gaussian-v1',params=dict(s['params'],jump_rate=0))
        checked=GaussianStrengthFilter.restore(normal)
        obj=cls(s['teams'],s['params'],s['numerics'])
        for name in ('mean','cov','last','counts','parent','last_day','days'):setattr(obj,name,getattr(checked,name))
        return obj
