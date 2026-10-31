"""Prefix-stable independent truth. No estimator imports or policy-dependent RNG."""
import hashlib
from datetime import date
import numpy as np
from scipy.special import ndtr, expit

TEAMS=('A','B','C','D')


def stream(seed,purpose,month=None,link=None,fixture=None):
    key=f'latent-v2|{seed}|{purpose}|{month}|{link}|{fixture}'
    return np.random.Generator(np.random.PCG64(int.from_bytes(hashlib.sha256(key.encode()).digest()[:16],'big')))


def generate(seed,path,link,months=360):
    if path not in ('constant','drift','jump') or link not in ('probit','logistic') or months<1:
        raise ValueError('INVALID_LONG_WORLD')
    base=np.array([.8,.25,-.35,-.7])+stream(seed,'base').normal(0,.1,4);base-=base.mean()
    world=f'latent-v2:{seed}:{path}:{link}';games=[];truth=[]
    cdf=ndtr if link=='probit' else lambda x:expit(x/(np.sqrt(3)/np.pi))
    for m in range(months):
        s=base.copy()
        if path=='drift':s+=max(0,min(1,(m-240)/120))*np.array([-1.2,.6,.6,0.])
        elif path=='jump' and m>=288:s+=np.array([-1.6,0.,.8,.8])
        s-=s.mean();day=date(2000+m//12,m%12+1,15).isoformat()
        truth.append(dict(world_id=world,seed=seed,path=path,link=link,month=m,date=day,
                          **{'true_'+t:float(v) for t,v in zip(TEAMS,s)}))
        order=stream(seed,'schedule',m).permutation(4)
        for j in range(2):
            hi,ai=map(int,order[2*j:2*j+2]);venue=int(m%7!=0);friendly=m%3==0
            mean=s[hi]-s[ai]+.25*venue;k=.95*(.65 if friendly else 1.)
            p=np.array([1-cdf(.4-mean),cdf(.4-mean)-cdf(-.4-mean),cdf(-.4-mean)])
            p=k*p+(1-k)/3;u=float(stream(seed,'outcome',m,link,j).random())
            outcome=int(np.searchsorted(np.cumsum(p),u,side='right'))
            games.append(dict(match_id=f'{world}:{m}:{j}',date=day,home=TEAMS[hi],away=TEAMS[ai],
                venue=venue,friendly=friendly,outcome=min(outcome,2),month=m,world_id=world,
                true_p_home=float(p[0]),true_p_draw=float(p[1]),true_p_away=float(p[2])))
    return games,truth


def extend(seed,path,link,old_games,old_truth,months):
    games,truth=generate(seed,path,link,months)
    if games[:len(old_games)]!=old_games or truth[:len(old_truth)]!=old_truth:
        raise ValueError('SIMULATION_PREFIX_CHANGED')
    return games,truth
