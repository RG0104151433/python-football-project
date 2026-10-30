"""Numerical checks and actual outcome->score feedback simulations, not CI admission."""
from collections import defaultdict
from datetime import date
import math
import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr
from scipy.stats import poisson
from src.strength.collapsed_jump import CollapsedJumpFilter
from .contract import distribution
from .design import Design
from .model import Kernel, objective, slopes, fit, predict


def kernel_check(rows, design, numerics):
    """Independent scalar Gaussian integration and finite-difference derivatives."""
    sample = sorted(rows, key=lambda r: float(r["strength_difference_variance"]))[::max(1, len(rows) // 13)]
    kernel = Kernel(sample, tail=numerics["poisson_tail"])
    x, _ = design.matrix(sample, "M3_nested")
    y = np.array([int(r["home_win"]) for r in sample], float)
    s = slopes(sample, "M3_nested")
    theta = np.r_[np.linspace(-.12, .18, x.shape[1]), math.log(.8)]
    loss, gradient = objective(theta, x, kernel, y, s)
    fd = []
    for j in range(len(theta)):
        h = np.zeros(len(theta)); h[j] = 1e-5
        fd.append((objective(theta + h, x, kernel, y, s)[0] - objective(theta - h, x, kernel, y, s)[0]) / 2e-5)
    error = float(max(abs(gradient - fd)))
    p = kernel.evaluate(x @ theta[:-1], .8)
    independent = []
    for r, eta in zip(sample, x @ theta[:-1]):
        mu = float(r["strength_difference"]); base = float(r["strength_difference_base_variance"])
        nu = float(r["home_jump_intensity"]) + float(r["away_jump_intensity"]); sd = float(r["jump_scale_sd"])
        cap = int(poisson.isf(1e-14, nu)) if nu else 0
        value = 0.
        for n in range(cap + 1):
            vv = base + n * sd * sd
            q = quad(lambda z: ndtr(.8 * (mu + math.sqrt(vv) * z) + eta) * math.exp(-z * z / 2) / math.sqrt(2 * math.pi),
                     -11, 11, epsabs=2e-12)[0]
            value += poisson.pmf(n, nu) * q
        independent.append(value)
    probability_error = float(max(abs(p - independent)))
    passed = error < numerics["gradient_reference_gate"] and probability_error < numerics["probability_reference_gate"]
    return dict(passed=passed, samples=len(sample), max_gradient_error=error, max_independent_probability_error=probability_error,
                numerical_only_not_statistical_coverage=True)


def before_day(engine, day, batch):
    """Read the score distribution before outcomes without advancing the learner."""
    distribution_rows = []
    for g in batch:
        dt = {t: (date.fromisoformat(day) - date.fromisoformat(engine.last.get(t, day))).days / 365.2425 for t in (g["home"], g["away"])}
        i, j = engine.index[g["home"]], engine.index[g["away"]]
        base = engine.cov[i, i] + engine.cov[j, j] - 2 * engine.cov[i, j] + engine.params["q"] * sum(dt.values())
        nh, na = [engine.params["jump_rate"] * dt[g[k]] for k in ("home", "away")]
        distribution_rows.append(dict(match_id=g["match_id"], date=day,
            strength_difference=float(engine.mean[i] - engine.mean[j]), strength_difference_base_variance=float(base),
            home_jump_intensity=nh, away_jump_intensity=na, jump_scale_sd=engine.params["jump_sd"],
            strength_difference_variance=float(base + (nh + na) * engine.params["jump_sd"] ** 2),
            prediction_cutoff=engine.last_day or "initial_prior"))
    return distribution_rows


def feedback_world(games, templates, parameters, numerics, seed, world, small=False):
    """Complete W/D/L generated together before any same-day score update."""
    rng = np.random.default_rng(seed)
    engine = CollapsedJumpFilter({g[k] for g in games for k in ("home", "away")}, parameters, numerics)
    batches = defaultdict(list)
    for g in games:
        batches[g["date"]].append(g)
    latent = {t: 0. for t in engine.teams}; last = {}; selected = []; max_query_error = 0.
    draw_count = away_count = 0
    for day_index, (day, batch) in enumerate(sorted(batches.items())):
        batch = sorted(batch, key=lambda g: g["match_id"])
        pre = before_day(engine, day, batch)
        active = {g[k] for g in batch for k in ("home", "away")}
        if world == "latent_strength":
            for team in sorted(active):
                dt = (date.fromisoformat(day) - date.fromisoformat(last.get(team, day))).days / 365.2425
                latent[team] += rng.normal(0, math.sqrt(parameters["q"] * dt)) + rng.normal(0, parameters["jump_sd"] * math.sqrt(rng.poisson(parameters["jump_rate"] * dt)))
                last[team] = day
        if world == "score_conditional":
            eta = np.array([.15 * g["venue"] if small else .15 * g["venue"] - .12 * g["friendly"] + .02 * max(0, min(4, (int(day[:4]) - 1980) // 10)) for g in batch])
            p = Kernel(pre).evaluate(eta, .8)
            outcomes = [0 if rng.random() < value else 1 if rng.random() < .35 else 2 for value in p]
        else:
            shock = .08 * math.sin(2 * math.pi * int(day[:4]) / 12)
            outcomes = []
            for g in batch:
                performance = latent[g["home"]] - latent[g["away"]] + (.2 + shock) * g["venue"] + rng.normal()
                outcomes.append(0 if performance > .4 else 2 if performance < -.4 else 1)
        generated = [dict(g, outcome=int(y)) for g, y in zip(batch, outcomes)]
        scored = engine.day(day, generated)
        for g, r, prior in zip(generated, scored, pre):
            max_query_error = max(max_query_error, abs(r["difference"] - prior["strength_difference"]),
                                  abs(r["difference_variance"] - prior["strength_difference_variance"]))
            draw_count += g["outcome"] == 1; away_count += g["outcome"] == 2
            if g["study"]:
                row = dict(templates[g["match_id"]], **prior)
                row.update(home_win=int(g["outcome"] == 0), outcome=("home", "draw", "away")[g["outcome"]])
                selected.append(row)
        if day_index % 1200 == 0:
            print("JOINT_FEEDBACK", world, seed, day_index, day, len(selected), flush=True)
    return selected, dict(world=world, seed=seed, learning_matches=len(games), study_matches=len(selected),
        dates=len(batches), max_prequery_score_error=max_query_error, draws=draw_count, away_wins=away_count,
        all_same_day_outcomes_generated_before_learning=True, selection_repeated=False,
        probability_calibration_replayed=False, reason="joint input uses raw strength distribution, not calibrated forecast probabilities")


def small_feedback(cfg, numerical, score_parameters, score_numerics):
    from datetime import timedelta
    report = []
    for world in cfg["simulation"]["worlds"]:
        for seed in cfg["simulation"]["small_seeds"]:
            games = []; templates = {}
            for i in range(360):
                day = (date(1970, 1, 1) + timedelta(days=11 * i)).isoformat()
                h = str(i % 6); a = str((i % 6 + 1 + (i // 6) % 5) % 6)
                mid = "sim:" + str(i)
                games.append(dict(match_id=mid, date=day, home=h, away=a, friendly=i % 3 == 0, venue=1, outcome=0, study=True))
                templates[mid] = dict(match_id=mid, date=day, era="1980s", tournament_group="friendly" if i % 3 == 0 else "non_friendly",
                                      home_region="150", away_region="150", home_unit="154", away_unit="154")
            rows, meta = feedback_world(games, templates, score_parameters, score_numerics, seed, world, small=True)
            design = Design(rows)
            result = fit(rows, design, "M1_strength", numerical)
            meta.update(estimated_intercept=result["theta"][0], estimated_slope=math.exp(result["theta"][1]),
                        loss=result["loss"], numerical_fit_passed=result["numerical_fit_passed"],
                        interpretation="conditional world truth intercept .15/slope .8; latent world has a different target, not coefficient recovery test")
            report.append(meta)
    return report
