"""A full-history refits; B paired calendar-score linearization. No formal CIs."""
from datetime import date
import numpy as np
from scipy.linalg import block_diag
from src.strength_joint.model import Kernel, objective, slopes, fit


def refit_pair(rows, design, numerics):
    return {m: fit(rows, design, m, numerics) for m in ("M0_nested", "M3_nested")}


def score_geometry(result, rows, design):
    x, _ = design.matrix(rows, result["model_id"]); y = np.array([int(r["home_win"]) for r in rows])
    kernel = Kernel(rows); s = slopes(rows, result["model_id"]); theta = np.asarray(result["theta"])
    b = np.exp(s @ theta[x.shape[1]:]) if s.shape[1] else np.zeros(len(rows))
    _, de, db = kernel.evaluate(x @ theta[:x.shape[1]], b, y)
    score = np.column_stack((x*de[:, None], s*(db*b)[:, None]))
    columns = []
    for j in range(len(theta)):
        step = np.zeros(len(theta)); step[j] = 1e-4
        columns.append((objective(theta+step, x, kernel, y, s)[1]-objective(theta-step, x, kernel, y, s)[1])/(2e-4))
    h = np.column_stack(columns)*len(rows); h = (h+h.T)/2
    eig = np.linalg.eigvalsh(h)
    if eig.min() <= 0: raise ValueError("NONPOSITIVE_SCORE_BREAD")
    return score, h, dict(min_eigenvalue=float(eig.min()), condition=float(eig.max()/eig.min()),
        score_balance_max=float(np.max(abs(score.sum(axis=0)))/len(rows)))


def calendar_influence(models, rows, design, target_jacobian):
    scores, breads, diagnostics = [], [], {}
    for m in ("M0_nested", "M3_nested"):
        g, h, report = score_geometry(models[m], rows, design); scores.append(g); breads.append(h); diagnostics[m] = report
    score = np.column_stack(scores); h = block_diag(*breads)
    # Total-score bread and total-score sums: no missing or duplicated N factor.
    individual = score @ np.linalg.solve(h, target_jacobian.T)
    start = date.fromisoformat(min(r["date"] for r in rows)).toordinal()
    offsets = np.array([date.fromisoformat(r["date"]).toordinal()-start for r in rows])
    calendar = np.zeros((int(offsets.max())+1, individual.shape[1])); np.add.at(calendar, offsets, individual)
    return calendar, diagnostics, individual


def bartlett_weights(rng, repetitions, length, bandwidth):
    if min(repetitions, length, bandwidth) < 1: raise ValueError("INVALID_MULTIPLIER_DIMENSIONS")
    noise = rng.normal(size=(repetitions, length+bandwidth-1))
    cumulative = np.pad(np.cumsum(noise, axis=1), ((0, 0), (1, 0)))
    return (cumulative[:, bandwidth:]-cumulative[:, :-bandwidth])/np.sqrt(bandwidth)


def multiplier_draws(calendar, repetitions, bandwidth, seed, centering="raw_score"):
    # raw_score is deliberately a named diagnostic, not an assertion of centering validity.
    if centering != "raw_score": raise ValueError("UNVALIDATED_CENTERING_MODE")
    rng = np.random.default_rng(seed); draws = []
    for first in range(0, repetitions, 64):
        w = bartlett_weights(rng, min(64, repetitions-first), len(calendar), bandwidth)
        draws.append(w @ calendar)
    return np.vstack(draws)


def summarize_draws(draws, nominal=.95):
    if len(draws) < 3: return dict(status="INSUFFICIENT_DRAWS", count=len(draws))
    se = draws.std(axis=0, ddof=1)
    if np.any(se <= 0) or not np.isfinite(se).all(): raise ValueError("DEGENERATE_TARGET_VARIANCE")
    critical = float(np.quantile(np.max(abs(draws/se), axis=1), nominal))
    return dict(status="DEVELOPMENT_ONLY_NOT_ADMITTED", count=len(draws), standard_errors_pp=se.tolist(),
                max_t_critical=critical, half_widths_pp=(critical*se).tolist(), nominal=nominal,
                centering="raw_score_for_B; no oracle bootstrap centering claimed for_A")
