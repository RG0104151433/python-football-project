"""Stable Poisson-normal probit and analytic scores; no unvalidated SE/CI."""
import math
import numpy as np
from scipy.optimize import minimize
from scipy.special import log_ndtr, logsumexp
from scipy.stats import poisson
from .contract import distribution


class Kernel:
    def __init__(self, rows=None, data=None, tail=1e-12, mode="mixture"):
        d = distribution(rows) if data is None else data
        self.mu = d["mu"]
        nu = d["nu_h"] + d["nu_a"]
        if mode == "plugin":
            self.v = np.zeros((len(nu), 1)); self.logw = np.zeros_like(self.v)
        elif mode == "total_normal":
            self.v = (d["base"] + nu * d["sd"] ** 2)[:, None]; self.logw = np.zeros_like(self.v)
        else:
            cap = int(poisson.isf(tail, float(nu.max()))) if nu.max() > 0 else 0
            while poisson.sf(cap, float(nu.max())) > tail:
                cap += 1
            if cap > 150:
                raise ValueError("NUMERIC_GATE_FAILED: Poisson budget")
            counts = np.arange(cap + 1)
            self.v = d["base"][:, None] + d["sd"][:, None] ** 2 * counts
            logw = poisson.logpmf(counts[None, :], nu[:, None])
            self.logw = logw - logsumexp(logw, axis=1)[:, None]
        self.max_omitted_mass = float(poisson.sf(self.v.shape[1] - 1, float(nu.max()))) if mode == "mixture" else 0.

    def evaluate(self, eta, b, labels=None):
        b = np.broadcast_to(b, self.mu.shape)
        scale = np.sqrt(1 + b[:, None] ** 2 * self.v)
        t = eta + b * self.mu
        z = t[:, None] / scale
        if labels is None:
            return np.exp(logsumexp(self.logw + log_ndtr(z), axis=1))
        sign = (2 * labels - 1)[:, None]
        logprob = logsumexp(self.logw + log_ndtr(sign * z), axis=1)
        # Derivative of log(sum w Phi(sign*z)), avoiding p-clipping.
        normalized_density = np.exp(self.logw - z * z / 2 - .5 * math.log(2 * math.pi) - logprob[:, None]) * sign
        d_eta = np.sum(normalized_density / scale, axis=1)
        d_b = np.sum(normalized_density * (self.mu[:, None] / scale - t[:, None] * b[:, None] * self.v / scale ** 3), axis=1)
        return logprob, d_eta, d_b


def objective(theta, x, kernel, y, slope_design):
    p = x.shape[1]
    b = np.exp(slope_design @ theta[p:]) if slope_design.shape[1] else np.zeros(len(y))
    logp, ge, gb = kernel.evaluate(x @ theta[:p], b, y)
    gradient = np.r_[-x.T @ ge, -slope_design.T @ (gb * b)] / len(y)
    return -float(np.mean(logp)), gradient


def slopes(rows, model):
    if model.startswith("M0"):
        return np.empty((len(rows), 0))
    if model == "M4_type_slope":
        friendly = np.array([r["tournament_group"] == "friendly" for r in rows], float)
        return np.column_stack((1 - friendly, friendly))
    return np.ones((len(rows), 1))


def fit(rows, design, model, numerics, starts=None):
    x, names = design.matrix(rows, model)
    audit = design.audit(rows, model)
    if not audit["full_rank"]:
        raise ValueError("RANK_DEFICIENT: " + model)
    y = np.array([int(r["home_win"]) for r in rows], float)
    mode = "plugin" if model == "M3_plugin" else "total_normal" if model == "M3_total_normal" else "mixture"
    kernel = Kernel(rows, tail=numerics["poisson_tail"], mode=mode)
    s = slopes(rows, model)
    lo, hi = map(math.log, numerics["slope_bounds"])
    bound = numerics["coefficient_bound"]
    bounds = [(-bound, bound)] * x.shape[1] + [(lo, hi)] * s.shape[1]
    trials = []
    for b0 in (starts or numerics["starts"]):
        theta = np.r_[np.zeros(x.shape[1]), np.full(s.shape[1], math.log(b0))]
        result = minimize(objective, theta, args=(x, kernel, y, s), jac=True, method="L-BFGS-B", bounds=bounds,
                          options=dict(maxiter=numerics["maxiter"], gtol=numerics["gtol"], ftol=1e-14, maxls=40, maxcor=30))
        loss, grad = objective(result.x, x, kernel, y, s)
        trials.append(dict(start=b0, loss=loss, gradient=float(np.max(abs(grad))), iterations=int(result.nit),
                           solver_success=bool(result.success), message=str(result.message), theta=result.x.tolist()))
    best = min(trials, key=lambda t: t["loss"])
    theta = np.array(best["theta"])
    boundary = [i for i, (a, b) in enumerate(bounds) if min(abs(theta[i] - a), abs(theta[i] - b)) < 1e-4]
    spread = max(t["loss"] for t in trials) - best["loss"]
    passed = best["solver_success"] and best["gradient"] < numerics["gradient_gate"] and spread < numerics["multistart_loss_gate"] and not boundary
    if not passed:
        raise ValueError("OPTIMIZER_FAILED: " + repr(dict(model=model, trials=trials, boundary=boundary)))
    # Finite-difference objective gradient curvature; diagnostic, never a CI.
    step = 1e-4; hessian = []
    for j in range(len(theta)):
        delta = np.zeros(len(theta)); delta[j] = step
        hessian.append((objective(theta + delta, x, kernel, y, s)[1] - objective(theta - delta, x, kernel, y, s)[1]) / (2 * step))
    hessian = np.column_stack(hessian)
    curvature = np.linalg.eigvalsh((hessian + hessian.T) / 2)
    if curvature.min() <= 0:
        raise ValueError("OPTIMIZER_FAILED: nonpositive local curvature " + model)
    result = dict(model_id=model, mode=mode, theta=theta.tolist(), names=names,
                  slope_names=[] if not s.shape[1] else ["log_b_nonfriendly", "log_b_friendly"] if s.shape[1] == 2 else ["log_b"],
                  loss=best["loss"], gradient=best["gradient"], multistart_loss_spread=spread, trials=trials,
                  curvature_min=float(curvature.min()), curvature_max=float(curvature.max()), design=audit,
                  rank=audit["rank"], parameters=len(theta), rows=len(rows), max_poisson_tail=kernel.max_omitted_mass,
                  boundary_parameters=boundary, numerical_fit_passed=True, inference_status="INFERENCE_NOT_ADMITTED")
    return result


def predict(result, rows, design, tail=1e-12):
    x, names = design.matrix(rows, result["model_id"])
    if names != result["names"]:
        raise ValueError("INPUT_VERSION_MISMATCH: design columns")
    theta = np.array(result["theta"]); s = slopes(rows, result["model_id"])
    b = np.exp(s @ theta[x.shape[1]:]) if s.shape[1] else np.zeros(len(rows))
    return Kernel(rows, tail=tail, mode=result["mode"]).evaluate(x @ theta[:x.shape[1]], b)
