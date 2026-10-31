"""Independent known latent paths; deliberately includes observation mismatch."""
from datetime import date
import numpy as np
from scipy.special import ndtr, expit


def generate(seed, path, link, months=60):
    if path not in ('constant', 'drift', 'jump') or link not in ('probit', 'logistic'):
        raise ValueError("UNKNOWN_GENERATOR")
    rng = np.random.default_rng(seed); teams = ['A', 'B', 'C', 'D']
    base = np.array([.8, .25, -.35, -.7])+rng.normal(0, .1, 4)
    base -= base.mean(); games = []; truth = []
    cdf = ndtr if link == 'probit' else lambda x: expit(x/(np.sqrt(3)/np.pi))
    for m in range(months):
        skill = base.copy()
        if path == 'drift':
            skill += (m/max(months-1, 1))*np.array([-1.2, .6, .6, 0.])
        elif path == 'jump' and m >= months//2:
            skill += np.array([-1.6, 0., .8, .8])
        skill -= skill.mean()
        day = date(2000+m//12, m%12+1, 15).isoformat()
        order = rng.permutation(4)
        for j in (0, 2):
            hi, ai = int(order[j]), int(order[j+1])
            venue = 0 if m%7 == 0 else 1; friendly = m%3 == 0
            mean = skill[hi]-skill[ai]+.25*venue
            k = .95*(.65 if friendly else 1.)
            p = np.array([1-cdf(.4-mean), cdf(.4-mean)-cdf(-.4-mean), cdf(-.4-mean)])
            p = k*p+(1-k)/3
            outcome = int(rng.choice(3, p=p))
            mid = f"sim:{seed}:{path}:{link}:{m}:{j}"
            games.append(dict(match_id=mid, date=day, home=teams[hi], away=teams[ai],
                              venue=venue, friendly=friendly, outcome=outcome))
            truth.append(dict(match_id=mid, date=day, month=m, seed=seed, path=path, link=link,
                              home=teams[hi], away=teams[ai], true_difference=float(skill[hi]-skill[ai]),
                              true_home_probability=float(p[0]), outcome=outcome))
    return games, truth
