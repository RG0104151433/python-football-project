"""Exact window-membership replay of the existing approximate rating filter.

Exact means historical inclusion, NOT exact Bayesian filtering: existing EP/ADF
approximations remain. No cumulative checkpoint or out-of-window warmup is used.
"""
from collections import defaultdict
from datetime import date
import time
import numpy as np
from src.strength.collapsed_jump import CollapsedJumpFilter, convolved_moments
from .protocol import bounds


def forecast(engine, day, targets):
    """Pure pre-date prediction; never reads or updates current outcomes."""
    if engine.last_day is not None and engine.last_day >= day:
        raise ValueError("FUTURE_INFORMATION")
    active = {g[k] for g in targets for k in ('home', 'away')}
    if not active.issubset(engine.index):
        raise ValueError("UNKNOWN_TARGET_TEAM")
    cov = engine.cov.copy(); mus = {}
    for t in active:
        dt = (date.fromisoformat(day)-date.fromisoformat(engine.last.get(t, day))).days/365.2425
        cov[engine.index[t], engine.index[t]] += engine.params['q']*dt
        mus[t] = engine.params['jump_rate']*dt
    if engine.last_day:
        dt = (date.fromisoformat(day)-date.fromisoformat(engine.last_day)).days/365.2425
        for h in range(len(engine.teams), len(engine.mean)):
            cov[h, h] += engine.params.get('home_q', 0)*dt
    rows = []
    for g in sorted(targets, key=lambda r: r['match_id']):
        i, j = engine.index[g['home']], engine.index[g['away']]
        h = len(engine.teams)+(int(g['friendly']) if engine.home_dimensions == 2 else 0)
        a = np.zeros(len(engine.mean)); a[i] = 1; a[j] = -1; a[h] = g['venue']
        mu, var = float(a@engine.mean), float(a@cov@a)
        k = (1-engine.params['epsilon'])*(engine.params['alpha'] if g['friendly'] else 1)
        p = [float(convolved_moments([mu], [var], [y], [k], [mus[g['home']]+mus[g['away']]],
             engine.params['delta'], engine.params['jump_sd']**2,
             engine.numerics.get('poisson_tail_tolerance', 1e-12))[0][0]) for y in range(3)]
        base = float(cov[i, i]+cov[j, j]-2*cov[i, j])
        rows.append(dict(match_id=g['match_id'], date=day, home=g['home'], away=g['away'],
                         difference=float(engine.mean[i]-engine.mean[j]), difference_base_variance=base,
                         difference_variance=base+(mus[g['home']]+mus[g['away']])*engine.params['jump_sd']**2,
                         home_jump_intensity=mus[g['home']], away_jump_intensity=mus[g['away']],
                         jump_scale_sd=engine.params['jump_sd'], home_mean=float(engine.mean[i]),
                         away_mean=float(engine.mean[j]), home_term=float(engine.mean[h]),
                         home_history=engine.counts[g['home']], away_history=engine.counts[g['away']],
                         cold_start=min(engine.counts[g['home']], engine.counts[g['away']]) < 5,
                         p_home=p[0], p_draw=p[1], p_away=p[2],
                         prediction_cutoff=engine.last_day or 'initial_prior'))
    return rows


def strict_replay(games, targets, day, years, parameters, numerics, start="1950-01-01", budget_seconds=600):
    left, right = bounds(day, years, start)
    if not targets or any(g['date'] != day for g in targets):
        raise ValueError("TARGET_BATCH_DATE_MISMATCH")
    past = sorted((g for g in games if left <= g['date'] < right), key=lambda g: (g['date'], g['match_id']))
    if len({g['match_id'] for g in past+targets}) != len(past)+len(targets):
        raise ValueError("DUPLICATE_MATCH")
    teams = {g[k] for g in past+targets for k in ('home', 'away')}
    engine = CollapsedJumpFilter(teams, parameters, numerics, 1., .25)
    grouped = defaultdict(list)
    for g in past:
        grouped[g['date']].append(g)
    started = time.perf_counter()
    for d, batch in sorted(grouped.items()):
        if time.perf_counter()-started > budget_seconds:
            raise TimeoutError("STRICT_REPLAY_BUDGET")
        engine.day(d, batch)
    predictions = forecast(engine, day, targets)
    ledger = dict(left_inclusive=left, right_exclusive=right, history_rows=len(past),
                  history_dates=len(grouped), actual_min=past[0]['date'] if past else None,
                  actual_max=past[-1]['date'] if past else None, roster=len(teams), targets=len(targets),
                  checkpoint_restored=False, outside_window_warmup=False, prior_team_variance=1.,
                  prior_home_variance=.25, elapsed_seconds=time.perf_counter()-started,
                  cold_start_targets=sum(r['cold_start'] for r in predictions))
    return predictions, ledger, engine
