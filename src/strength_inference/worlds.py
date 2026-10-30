"""Read-only full-state queries and complete WDL feedback histories."""
from collections import defaultdict
from datetime import date
import time
import numpy as np
from scipy.special import ndtr
from src.strength.collapsed_jump import CollapsedJumpFilter, convolved_moments
from src.strength_joint.model import Kernel, slopes


def before_day(engine, day, batch):
    """Mirror the learner's lazy calendar advance without mutating it."""
    if engine.last_day is not None and day <= engine.last_day:
        raise ValueError("QUERY_MUST_PRECEDE_NEW_DATE")
    output, raw = [], []
    global_dt = (date.fromisoformat(day) - date.fromisoformat(engine.last_day)).days / 365.2425 if engine.last_day else 0.
    for g in batch:
        i, j = (engine.index[g[k]] for k in ("home", "away"))
        h = len(engine.teams) + (int(g["friendly"]) if engine.home_dimensions == 2 else 0)
        dt = [(date.fromisoformat(day) - date.fromisoformat(engine.last.get(g[k], day))).days / 365.2425 for k in ("home", "away")]
        nuh, nua = (engine.params["jump_rate"] * d for d in dt)
        base = engine.cov[i, i] + engine.cov[j, j] - 2 * engine.cov[i, j] + engine.params["q"] * sum(dt)
        v = g["venue"]
        mu = engine.mean[i] - engine.mean[j] + v * engine.mean[h]
        variance = base + v*v * (engine.cov[h, h] + engine.params.get("home_q", 0) * global_dt) + 2*v*(engine.cov[i, h]-engine.cov[j, h])
        kappa = (1-engine.params["epsilon"]) * (engine.params["alpha"] if g["friendly"] else 1)
        p = [float(convolved_moments([mu], [variance], [y], [kappa], [nuh+nua], engine.params["delta"],
                                    engine.params["jump_sd"]**2, engine.numerics.get("poisson_tail_tolerance", 1e-12))[0][0]) for y in range(3)]
        if min(p) <= 0 or abs(sum(p)-1) > 2e-10:
            raise ValueError("INVALID_RAW_WDL")
        raw.append(p)
        output.append(dict(match_id=g["match_id"], date=day, strength_difference=float(engine.mean[i]-engine.mean[j]),
            strength_difference_base_variance=float(base), home_jump_intensity=nuh, away_jump_intensity=nua,
            jump_scale_sd=engine.params["jump_sd"], strength_difference_variance=float(base+(nuh+nua)*engine.params["jump_sd"]**2),
            prediction_cutoff=engine.last_day or "initial_prior", home_history=engine.counts[g["home"]],
            away_history=engine.counts[g["away"]], cold_start=min(engine.counts[g["home"]], engine.counts[g["away"]]) < 5))
    return output, np.asarray(raw)


def complete_wdl(home_probability, raw_wdl, draw_odds_multiplier=1.):
    p = np.asarray(home_probability, float); q = np.asarray(raw_wdl, float)
    if draw_odds_multiplier <= 0 or q.shape != (len(p), 3) or np.any(q <= 0) or np.any((p <= 0) | (p >= 1)):
        raise ValueError("INVALID_WDL_COMPLETION_INPUT")
    ratio = draw_odds_multiplier*q[:, 1] / (draw_odds_multiplier*q[:, 1]+q[:, 2])
    return np.column_stack((p, (1-p)*ratio, (1-p)*(1-ratio)))


def generate(games, templates, design, generator, parameters, numerics, seed, day_correlation=0., draw_odds_multiplier=1.):
    if not 0 <= day_correlation < 1:
        raise ValueError("INVALID_COPULA_CORRELATION")
    started = time.perf_counter(); rng = np.random.default_rng(seed)
    engine = CollapsedJumpFilter({g[k] for g in games for k in ("home", "away")}, parameters, numerics)
    batches = defaultdict(list)
    for g in games: batches[g["date"]].append(g)
    selected, probabilities, max_error = [], [], 0.
    counts = [0, 0, 0]
    for day_index, (day, gs) in enumerate(sorted(batches.items())):
        gs = sorted(gs, key=lambda g: g["match_id"])
        pre, q = before_day(engine, day, gs)
        wdl = q.copy(); study_indices = [i for i, g in enumerate(gs) if g["study"]]
        rr = []
        for i in study_indices:
            r = dict(templates[gs[i]["match_id"]], **pre[i]); r.pop("home_variance", None); r.pop("away_variance", None); r.pop("home_away_covariance", None)
            rr.append(r)
        if rr:
            x, names = design.matrix(rr, generator["model_id"])
            if names != generator["names"]: raise ValueError("GENERATOR_DESIGN_CHANGED")
            theta = np.asarray(generator["theta"]); s = slopes(rr, generator["model_id"])
            p = Kernel(rr).evaluate(x @ theta[:x.shape[1]], np.exp(s @ theta[x.shape[1]:]))
            wdl[study_indices] = complete_wdl(p, q[study_indices], draw_odds_multiplier)
        # One shared normal per date, independent residual per game: marginal U(0,1).
        shared = rng.normal(); u = ndtr(np.sqrt(day_correlation)*shared + np.sqrt(1-day_correlation)*rng.normal(size=len(gs)))
        outcomes = (u[:, None] > np.cumsum(wdl, axis=1)[:, :2]).sum(axis=1)
        generated = [dict(g, outcome=int(y)) for g, y in zip(gs, outcomes)]
        scored = engine.day(day, generated)
        for i, r in enumerate(scored):
            max_error = max(max_error, abs(r["difference"]-pre[i]["strength_difference"]),
                abs(r["difference_variance"]-pre[i]["strength_difference_variance"]),
                float(np.max(abs(np.array([r["p_home"], r["p_draw"], r["p_away"]])-q[i]))))
            counts[int(outcomes[i])] += 1
            probabilities.append(dict(match_id=gs[i]["match_id"], date=day, true_home_probability=float(wdl[i, 0]),
                true_draw_probability=float(wdl[i, 1]), true_away_probability=float(wdl[i, 2]),
                generated_outcome=int(outcomes[i]), auxiliary_learning=not gs[i]["study"]))
        for r, i in zip(rr, study_indices):
            r.update(home_win=int(outcomes[i] == 0), outcome=("home", "draw", "away")[outcomes[i]])
            selected.append(r)
        if day_index % 1500 == 0:
            print("INFERENCE_WORLD", seed, day_index, day, len(selected), flush=True)
    if max_error > 2e-8: raise ValueError("READONLY_PREQUERY_DISAGREES_WITH_LEARNER")
    return selected, probabilities, dict(seed=seed, learning_matches=len(games), study_matches=len(selected), dates=len(batches),
        home_wins=counts[0], draws=counts[1], away_wins=counts[2], max_query_error=max_error,
        seconds=time.perf_counter()-started, day_correlation=day_correlation, draw_odds_multiplier=draw_odds_multiplier,
        full_feedback_replayed=True, all_same_day_generated_before_update=True, selection_repeated=False)
