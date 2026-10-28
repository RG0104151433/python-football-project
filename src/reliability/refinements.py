"""Documented refinements: same-law simulation and design-only finite bounds."""
from collections import defaultdict
import heapq
import math

import numpy as np
from scipy.linalg import solve_banded
from scipy.signal import lfilter
from scipy.special import ndtri
from scipy.stats import t as student_t

from .models import color_constant,ModelFailure


def coloring_valid_fast(design,color,L):
    ids=np.flatnonzero(color>=0)
    keys=np.r_[color[ids]*len(design.teams)+design.home[ids],color[ids]*len(design.teams)+design.away[ids]]
    if len(np.unique(keys))!=2*len(ids):return False
    order=ids[np.lexsort((design.days[ids],color[ids]))]
    same=np.diff(color[order])==0
    return not np.any(same) if L=="all_dependent" else bool(np.all(np.diff(design.days[order])[same]>L))


def weighted_colors(design,a,L,reverse=False):
    order=[i for i in design.order if a[i]!=0]
    if reverse:order=order[::-1]
    result=np.full(design.n,-1,dtype=int);waiting=[];available=[];teams=[];mass=[]
    for i in order:
        h,away=int(design.home[i]),int(design.away[i]);now=int(design.days[i])*(-1 if reverse else 1)
        while waiting and waiting[0][0]<now:
            _,c=heapq.heappop(waiting);heapq.heappush(available,(-mass[c],c))
        blocked=[];chosen=None
        while available:
            item=heapq.heappop(available);c=item[1]
            if h not in teams[c] and away not in teams[c]:chosen=c;break
            blocked.append(item)
        for item in blocked:heapq.heappush(available,item)
        if chosen is None:
            chosen=len(teams);teams.append(set());mass.append(0.)
        teams[chosen].update((h,away));mass[chosen]+=a[i]**2;result[i]=chosen
        heapq.heappush(waiting,(now+L,chosen))
    if not coloring_valid_fast(design,result,L):raise ModelFailure("Invalid weighted coloring")
    return result


def refine_graph(design,L,base):
    C=np.asarray(base["C"]).copy();schemes=list(base["schemes"])
    if L!="all_dependent":
        for j in range(design.A.shape[0]):
            a=design.A.getrow(j).toarray().ravel()
            for reverse in (False,True):
                colors=weighted_colors(design,a,L,reverse)
                candidate=color_constant(a,colors)
                if candidate<C[j]:C[j]=candidate;schemes[j]="weighted_reverse" if reverse else "weighted_chronological"
    half=np.zeros(len(C));delta=np.zeros(len(C))
    for f,js in design.families.items():
        half[js]=np.sqrt(C[js]/2*np.log(2*len(js)/.05));delta[js]=.05/(2*len(js))
    markov_width=(1-delta)*design.span
    # Selection is made before any Y is drawn, from worst-case widths only.
    markov_choice=2*half>=markov_width
    return dict(C=C,half=half,schemes=schemes,delta=delta,markov_choice=markov_choice,
                markov_width=markov_width,L=L)


def refined_intervals(design,estimate,g,fallback=True):
    lo=np.maximum(estimate-g["half"],design.lo);hi=np.minimum(estimate+g["half"],design.hi)
    if fallback:
        choice=g["markov_choice"]
        lo[choice]=design.lo[choice]+g["delta"][choice]*(estimate[choice]-design.lo[choice])
        hi[choice]=design.hi[choice]-g["delta"][choice]*(design.hi[choice]-estimate[choice])
    return lo,hi


def team_banded(design,B,tau,rng):
    ev=design.team_events;gap=ev["gaps"];first=ev["prev"]<0
    rho=np.exp(-gap/tau);rho[first]=0
    noise=rng.normal(size=(ev["n"],B))*np.where(first,1,np.sqrt(-np.expm1(-2*gap/tau)))[:,None]
    ab=np.zeros((2,ev["n"]));ab[0]=1;ab[1,:-1]=-rho[1:]
    values=solve_banded((1,0),ab,noise,overwrite_ab=True,overwrite_b=True,check_finite=False)
    return values[ev["home"]].T,values[ev["away"]].T


def time_daily(design,B,tau,rng):
    first=int(design.days.min());length=int(design.days.max())-first+1
    rho=math.exp(-1/tau);sigma=math.sqrt(-math.expm1(-2/tau))
    initial=rng.normal(size=(B,1))
    innovations=rng.normal(size=(B,length-1))
    later,_=lfilter([sigma],[1,-rho],innovations,axis=1,zi=rho*initial)
    values=np.concatenate((initial,later),axis=1)
    return values[:,design.days-first]


def generate_fast(design,p,scenario,B,rng):
    """Exact same finite-dimensional laws as generate(), not same RNG draws.

    Daily AR(1) evaluates unobserved intermediate days, then selects fixture
    days; OU at integer dates is exactly this law, not a truncation/rounding.
    """
    w=scenario["latent"]
    loading=np.where(design.years<2000,.5,1.) if scenario.get("time_loading") else np.ones(design.n)
    noise=(1-w["minus"]-w["time"]*loading**2) if scenario.get("time_loading") else np.full(design.n,w["e"])
    latent=rng.normal(size=(B,design.n))*np.sqrt(noise)
    for name in ("minus","plus"):
        if w[name]:
            h,a=team_banded(design,B,scenario.get("team_tau_days",365),rng)
            latent+=np.sqrt(w[name]/2)*(h-a if name=="minus" else h+a)
    if w["pair"]:latent+=np.sqrt(w["pair"])*rng.normal(size=(B,design.npairs))[:,design.pair]
    if w["time"]:
        kernel=scenario["time_kernel"]
        if kernel=="OU":common=time_daily(design,B,scenario["time_tau_days"],rng)
        elif kernel=="one_global_normal":common=rng.normal(size=(B,1))
        elif kernel=="finite_gaussian_MA":
            L=scenario["time_range_days"];base=int(design.days.min())-L
            eps=rng.normal(size=(B,int(design.days.max())-base+1))
            cum=np.column_stack((np.zeros(B),np.cumsum(eps,axis=1)))
            end=design.days-base+1
            common=(cum[:,end]-cum[:,end-L-1])/np.sqrt(L+1)
        else:raise ValueError(kernel)
        latent+=np.sqrt(w["time"])*loading*common
    if w.get("synthetic_competition",0):
        groups=defaultdict(list)
        for i,r in enumerate(design.facts):groups[(r.get("tournament_name",r["tournament_group"]),r["year"])].append(i)
        ids=np.zeros(design.n,dtype=int);label=0
        for members in groups.values():
            members.sort(key=lambda i:(design.days[i],design.facts[i]["match_id"]))
            for start in range(0,len(members),20):ids[members[start:start+20]]=label;label+=1
        latent+=np.sqrt(w["synthetic_competition"])*rng.normal(size=(B,label))[:,ids]
    z=ndtri(p)
    if scenario.get("copula"):
        latent/=np.sqrt(rng.chisquare(5,size=(B,1))/5);z=student_t.ppf(p,5)
    return (latent+z>0).astype(float)


def bootstrap_fast(design,p,scenario,B,rng,batch=128):
    truth=design.apply(p);d=design.scale;pivots={f:[] for f in design.families}
    for start in range(0,B,batch):
        values=design.apply(generate_fast(design,p,scenario,min(batch,B-start),rng))
        for f,js in design.families.items():
            active=np.array(js)[d[js]>0]
            pivots[f].extend(np.max(np.abs(values[:,active]-truth[active])/d[active],axis=1).tolist() if len(active) else [0]*len(values))
    half=np.zeros(len(d));critical={};rank=math.ceil((B+1)*.95)
    for f,js in design.families.items():
        c=float(np.sort(pivots[f])[rank-1]) if rank<=B else float("inf")
        critical[f]=c;half[js]=np.where(d[js]>0,c*d[js],0)
    return half,dict(B=B,rank=rank,critical=critical,design_scale_not_SE=True)
