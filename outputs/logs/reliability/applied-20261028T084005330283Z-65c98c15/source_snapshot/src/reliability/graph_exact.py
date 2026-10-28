"""Sharper graph Chernoff bound, without estimating Bernoulli probabilities."""
import math
import numpy as np
from scipy.optimize import minimize_scalar
from .models import greedy_colors,coloring_valid
from .refinements import weighted_colors,coloring_valid_fast


def worst_bernoulli_logmgf(x):
    """sup_p log E exp[x(B-p)], B~Bernoulli(p); even in x."""
    x=np.abs(np.asarray(x,float));small=x<1e-3
    safe=np.where(small,1,x)
    ratio=np.zeros_like(safe);moderate=safe<700
    ratio[moderate]=safe[moderate]/np.expm1(safe[moderate])
    general=safe+np.log1p(-np.exp(-safe))-np.log(safe)-1+ratio
    series=x*x/8-x**4/576+x**6/25920
    return np.where(small,series,general)


def sharper_halfwidth(a,color,m,old_half,alpha=.05):
    ids=np.flatnonzero(a)
    if not len(ids):return 0.,0.
    v=np.bincount(color[ids],weights=a[ids]**2)
    total=np.sqrt(v).sum();r=total/np.sqrt(v[color[ids]])
    amount=np.abs(a[ids])*r;weight=1/r;penalty=math.log(2*m/alpha)
    def objective(z):
        lam=math.exp(z)
        return float((np.dot(weight,worst_bernoulli_logmgf(lam*amount))+penalty)/lam)
    opt=minimize_scalar(objective,bounds=(-12,22),method="bounded",options=dict(xatol=1e-8))
    return min(old_half,float(opt.fun)),float(opt.x)


def refine_all(design,base):
    results=[]
    for L in (90,365,730,1460,"all_dependent"):
        g=base[str(L)];global_color=greedy_colors(design,L)
        for j,tid in enumerate(design.targets):
            a=design.A.getrow(j).toarray().ravel();scheme=g["schemes"][j]
            if L=="all_dependent" or scheme=="global_chronological":color=global_color
            elif scheme.startswith("weighted"):color=weighted_colors(design,a,L,"reverse" in scheme)
            else:color=greedy_colors(design,L,np.flatnonzero(a),"reverse" in scheme)
            if not coloring_valid_fast(design,color,L):raise ValueError("Invalid reused graph coloring")
            f=next(f for f,ids in design.families.items() if j in ids);m=len(design.families[f])
            h,z=sharper_halfwidth(a,color,m,g["half"][j])
            delta=.05/(2*m);markov=(1-delta)*design.span[j]
            results.append(dict(L_days=L,target_id=tid,family=f,old_half=g["half"][j],new_half=h,
                lambda_log=z,logical_span=float(design.span[j]),
                largest_possible_graph_width=float(min(2*h,design.span[j])),
                bounded_reference_width=float(markov),
                theory="setwise graph independence for Chernoff; boundedness-only for Markov; no real graph certified"))
    return results
