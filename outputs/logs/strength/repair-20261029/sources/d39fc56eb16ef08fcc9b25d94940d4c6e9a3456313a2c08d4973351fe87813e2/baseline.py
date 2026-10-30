"""A specified fixed-step W/D/L rating baseline, not FIFA's official formula."""
from __future__ import annotations
import math
from collections import defaultdict
import numpy as np
from scipy.special import softmax


def fixed_step(games, k=20, home=60, draw=.75, start=1950):
    """Davidson-form probabilities, Elo-style expected-score gradient updates."""
    groups=defaultdict(list)
    for g in games:
        if int(g["date"][:4])>=start:
            groups[g["date"]].append(g)
    ratings=defaultdict(lambda:1500.)
    rows=[]
    for day,batch in sorted(groups.items()):
        increments=defaultdict(float)
        for g in sorted(batch,key=lambda r:r["match_id"]):
            gap=ratings[g["home"]]-ratings[g["away"]]+g["venue"]*home
            u=.5*math.log(10)/400*gap
            p=softmax([u,math.log(draw),-u])
            expected=float(p[0]+.5*p[1])
            observed=[1.,.5,0.][g["outcome"]]
            update=k*(observed-expected)
            increments[g["home"]]+=update
            increments[g["away"]]-=update
            rows.append(dict(match_id=g["match_id"],date=day,p_home=float(p[0]),p_draw=float(p[1]),
                             p_away=float(p[2]),outcome_index=g["outcome"]))
        for t,change in increments.items(): ratings[t]+=change
    return rows


def frequency(games,start=1950):
    """Venue-specific, past-only frequency baseline; same-date count freeze."""
    groups=defaultdict(list)
    for g in games:
        if int(g["date"][:4])>=start: groups[g["date"]].append(g)
    counts={0:np.ones(3),1:np.ones(3)}
    rows=[]
    for day,batch in sorted(groups.items()):
        for g in sorted(batch,key=lambda r:r["match_id"]):
            key=int(g["venue"]!=0)
            p=counts[key]/counts[key].sum()
            rows.append(dict(match_id=g["match_id"],date=day,p_home=float(p[0]),p_draw=float(p[1]),
                             p_away=float(p[2]),outcome_index=g["outcome"]))
        for g in batch: counts[int(g["venue"]!=0)][g["outcome"]]+=1
    return rows
