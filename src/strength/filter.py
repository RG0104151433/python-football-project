"""Finite joint Gaussian-mixture pilot with exact single-game tilted moments.

Calendar units are years (365.2425 days). Poisson transitions are enumerated up
to a *joint* count cap, then normalized; omitted prior mass and posterior beam
loss are reported separately. Multi-game days use damped parallel EP. Neither
the Gaussian projection nor beam/EP approximation is claimed exact.
"""
from __future__ import annotations

import itertools
import math
import copy
from dataclasses import dataclass
from datetime import date

import numpy as np
from scipy.special import ndtr, logsumexp
from scipy.stats import poisson


class NumericalFailure(RuntimeError):
    pass


def outcome_moments(mean, variance, outcome, delta, kappa):
    """Exact evidence and first two moments of u~N(mean,variance), z=u+N(0,1)."""
    if variance <= 0 or not 0 < kappa <= 1 or delta <= 0:
        raise ValueError("Invalid scalar model")
    sd = math.sqrt(1 + variance)
    lower, upper = [(delta, math.inf), (-delta, delta), (-math.inf, -delta)][outcome]
    lo, hi = (lower - mean) / sd, (upper - mean) / sd
    if lo > 0:
        prob = float(ndtr(-lo) - ndtr(-hi))
    else:
        prob = float(ndtr(hi) - ndtr(lo))

    def phi(x):
        return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi) if math.isfinite(x) else 0.0

    pl, ph = phi(lo), phi(hi)
    evidence = kappa * prob + (1 - kappa) / 3
    if evidence <= 0 or not math.isfinite(evidence):
        raise NumericalFailure("Zero/nonfinite outcome evidence")
    g = kappa * (pl - ph) / sd / evidence
    d2 = kappa * ((lo * pl if math.isfinite(lo) else 0) -
                  (hi * ph if math.isfinite(hi) else 0)) / sd**2 / evidence
    curvature = d2 - g * g
    tilted_mean = mean + variance * g
    tilted_var = variance + variance * variance * curvature
    if tilted_var <= 0 or not math.isfinite(tilted_var):
        raise NumericalFailure("Invalid tilted variance")
    return evidence, tilted_mean, tilted_var, g, curvature


def probabilities(mean, variance, delta, kappa):
    return np.array([outcome_moments(mean, variance, y, delta, kappa)[0] for y in range(3)])


def _projected(prior_mean, root, tau, eta):
    precision = np.eye(root.shape[1]) + root.T @ (tau[:, None] * root)
    chol = np.linalg.cholesky(precision)
    post_cov = root @ np.linalg.solve(precision, root.T)
    b = eta - tau * prior_mean
    post_mean = prior_mean + post_cov @ b
    logdet = 2 * np.log(np.diag(chol)).sum()
    return post_mean, post_cov, logdet


def batch_update(mean, cov, design, outcomes, kappas, delta, numerics):
    """One joint daily posterior per component, including correlations and h."""
    pm = design @ mean
    cross = cov @ design.T
    pc = design @ cross
    if len(outcomes) == 1:
        z, _, _, g, curvature = outcome_moments(pm[0], pc[0, 0], outcomes[0], delta, kappas[0])
        m = mean + cross[:, 0] * g
        c = cov + np.outer(cross[:, 0], cross[:, 0]) * curvature
        return m, (c + c.T) / 2, math.log(z), {"iterations": 0, "method": "exact_single_match_moments"}
    eig, vectors = np.linalg.eigh((pc + pc.T) / 2)
    if eig.min() < -numerics["psd_tolerance"]:
        raise NumericalFailure("Prior projected covariance not PSD")
    keep = eig > numerics["rank_tolerance"]
    root = vectors[:, keep] * np.sqrt(eig[keep])
    if not keep.any():
        raise NumericalFailure("No uncertain performance dimension")
    tau, eta = np.zeros(len(outcomes)), np.zeros(len(outcomes))
    converged = False
    for iteration in range(1, numerics["ep_max_iter"] + 1):
        qm, qc, _ = _projected(pm, root, tau, eta)
        precision = 1 / np.diag(qc) - tau
        if np.any(precision <= 0):
            raise NumericalFailure("Nonpositive EP cavity precision")
        cv = 1 / precision
        cm = cv * (qm / np.diag(qc) - eta)
        target_tau, target_eta = [], []
        for k in range(len(outcomes)):
            _, tm, tv, _, _ = outcome_moments(cm[k], cv[k], outcomes[k], delta, kappas[k])
            target_tau.append(1 / tv - 1 / cv[k])
            target_eta.append(tm / tv - cm[k] / cv[k])
        dt, de = np.array(target_tau) - tau, np.array(target_eta) - eta
        damping = numerics["ep_damping"]
        for _ in range(15):
            nt, ne = tau + damping * dt, eta + damping * de
            try:
                nm, nc, _ = _projected(pm, root, nt, ne)
                if np.any(np.diag(nc) <= 0) or np.any(1 / np.diag(nc) - nt <= 0):
                    raise np.linalg.LinAlgError("Cavity failure")
                break
            except np.linalg.LinAlgError:
                damping *= 0.5
        else:
            raise NumericalFailure("EP damping failed")
        error = max(float(np.max(abs(nt - tau))), float(np.max(abs(ne - eta))))
        tau, eta = nt, ne
        if error < numerics["ep_tolerance"]:
            converged = True
            break
    if not converged:
        raise NumericalFailure("EP did not converge")
    qm, qc, logdet = _projected(pm, root, tau, eta)
    cv = 1 / (1 / np.diag(qc) - tau)
    cm = cv * (qm / np.diag(qc) - eta)
    constants = []
    for k in range(len(outcomes)):
        z, _, _, _, _ = outcome_moments(cm[k], cv[k], outcomes[k], delta, kappas[k])
        denom = 1 + tau[k] * cv[k]
        log_integral = (-0.5 * math.log(denom) + eta[k] * cm[k] - 0.5 * tau[k] * cm[k]**2 +
                        0.5 * cv[k] * (eta[k] - tau[k] * cm[k])**2 / denom)
        constants.append(math.log(z) - log_integral)
    b = eta - tau * pm
    logz = -0.5 * logdet + 0.5 * b @ qc @ b + eta @ pm - 0.5 * tau @ (pm * pm) + sum(constants)
    inverse = (vectors[:, keep] / eig[keep]) @ vectors[:, keep].T
    gain = cross @ inverse
    m = mean + gain @ (qm - pm)
    c = cov + gain @ (qc - pc) @ gain.T
    return m, (c + c.T) / 2, float(logz), {"iterations": iteration, "method": "parallel_EP"}


def joint_quadrature(mean, cov, design, outcomes, kappas, delta, order=35):
    """Independent low-rank Gauss-Hermite reference; max three projected dimensions."""
    pm, pc = design @ mean, design @ cov @ design.T
    eig, vec = np.linalg.eigh(pc)
    keep = eig > 1e-12
    rank = int(keep.sum())
    if rank > 3:
        raise ValueError("Reference limited to rank3")
    nodes, weights = np.polynomial.hermite.hermgauss(order)
    grid = np.array(list(itertools.product(range(order), repeat=rank)))
    points = math.sqrt(2) * nodes[grid] @ (vec[:, keep] * np.sqrt(eig[keep])).T + pm
    w = np.prod(weights[grid] / math.sqrt(math.pi), axis=1)
    for k, y in enumerate(outcomes):
        u = points[:, k]
        base = [ndtr(u - delta), ndtr(delta - u) - ndtr(-delta - u), ndtr(-delta - u)][y]
        w *= kappas[k] * base + (1 - kappas[k]) / 3
    z = float(w.sum())
    w /= z
    qm = w @ points
    centered = points - qm
    qc = (centered.T * w) @ centered
    gain = cov @ design.T @ np.linalg.pinv(pc, rcond=1e-12)
    return mean + gain @ (qm - pm), cov + gain @ (qc - pc) @ gain.T, math.log(z)


@dataclass
class Component:
    weight: float
    mean: np.ndarray
    cov: np.ndarray
    path: tuple


class StrengthFilter:
    def __init__(self, teams, params, numerics, team_variance=1.0, home_variance=0.25):
        self.teams = sorted(teams)
        if not self.teams or len(self.teams) != len(set(self.teams)) or min(team_variance, home_variance) <= 0:
            raise ValueError("Invalid teams or initial variances")
        self.index = {t: i for i, t in enumerate(self.teams)}
        self.params, self.numerics = dict(params), dict(numerics)
        if params["q"] < 0 or params["jump_rate"] < 0 or params["jump_sd"] < 0:
            raise ValueError("Invalid calendar transition")
        if not 0 < params["alpha"] < 1 or not 0 <= params["epsilon"] < 1:
            raise ValueError("Invalid outcome mixture")
        n = len(self.teams) + 1
        covariance = np.diag([team_variance] * len(self.teams) + [home_variance])
        self.components = [Component(1.0, np.zeros(n), covariance, ())]
        self.last = {}
        self.last_day = None
        self.counts = {t: 0 for t in self.teams}
        self.diagnostics = []

    def reduce_components(self, updated, posterior):
        indices = sorted(range(len(posterior)), key=lambda k: (-posterior[k], k))[:self.numerics["max_components"]]
        kept_mass = float(posterior[indices].sum())
        kept = []
        for k in indices:
            c = updated[k]
            c.weight = float(posterior[k] / kept_mass)
            kept.append(c)
        return kept, {"approximate_posterior_pruned_mass": max(0.0, 1 - kept_mass),
                      "pruning_warning": 1 - kept_mass > self.numerics["pruned_weight_warning"]}

    def design(self, games):
        a = np.zeros((len(games), len(self.teams) + 1))
        for k, g in enumerate(games):
            if g["home"] == g["away"]:
                raise ValueError("Self match")
            a[k, self.index[g["home"]]], a[k, self.index[g["away"]]] = 1, -1
            a[k, -1] = g.get("venue", 1)
        return a

    def advance(self, day, active):
        active = sorted(active)
        elapsed = np.array([(date.fromisoformat(day) - date.fromisoformat(self.last.get(t, day))).days / 365.2425
                            for t in active])
        mu = self.params["jump_rate"] * elapsed
        total = float(mu.sum())
        cap = self.numerics["jump_total_cap"]
        tail = float(poisson.sf(cap, total))
        if tail > self.numerics["max_transition_prior_tail"]:
            raise NumericalFailure(f"Poisson prior tail {tail:.6g} exceeds gate")
        counts = []
        for count in range(cap + 1 if total else 1):
            for choices in itertools.combinations_with_replacement(range(len(active)), count):
                v = np.bincount(choices, minlength=len(active))
                if np.any((mu == 0) & (v > 0)):
                    continue
                logp = -total + sum(int(k) * math.log(m) - math.lgamma(int(k) + 1)
                                    for k, m in zip(v, mu) if m > 0)
                counts.append((v, math.exp(logp) / (1 - tail)))
        if len(counts) > self.numerics["max_children_per_parent"]:
            raise NumericalFailure("Transition enumeration budget exceeded")
        memory = len(counts)*len(self.components)*(len(self.teams)+1)**2*8
        if memory > self.numerics.get("max_child_bytes", math.inf):
            raise NumericalFailure(f"Transition covariance memory estimate {memory} exceeds budget")
        children = []
        for parent in self.components:
            for v, prob in counts:
                cov = parent.cov.copy()
                jumps = []
                for k, t in enumerate(active):
                    j = self.index[t]
                    cov[j, j] += self.params["q"] * elapsed[k] + int(v[k]) * self.params["jump_sd"]**2
                    if v[k]:
                        jumps.append((day, t, int(v[k])))
                children.append(Component(parent.weight * prob, parent.mean.copy(), cov, parent.path + tuple(jumps)))
        return children, tail

    def day(self, day, games):
        if not games:
            raise ValueError("Empty day")
        if any(g.get("venue", 1) not in {-1, 0, 1} or g["outcome"] not in {0, 1, 2} for g in games):
            raise ValueError("Invalid outcome/venue")
        if self.last_day is not None and day <= self.last_day:
            raise ValueError("Dates must strictly increase; one complete batch per day")
        games = sorted(games, key=lambda r: r["match_id"])
        if len({g["match_id"] for g in games}) != len(games):
            raise ValueError("Duplicate game ID in day")
        active = {g[k] for g in games for k in ("home", "away")}
        if not active.issubset(self.index):
            raise ValueError("Unknown team")
        children, tail = self.advance(day, active)
        design = self.design(games)
        kappas = [(1 - self.params["epsilon"]) * (self.params["alpha"] if g["friendly"] else 1)
                  for g in games]
        rows = []
        weights = np.array([c.weight for c in children])
        total_mean = sum(c.weight * c.mean for c in children)
        total_cov = sum(c.weight * (c.cov + np.outer(c.mean - total_mean, c.mean - total_mean)) for c in children)
        for k, g in enumerate(games):
            a = design[k]
            p = sum(c.weight * probabilities(a @ c.mean, a @ c.cov @ a,
                                             self.params["delta"], kappas[k]) for c in children)
            i, j = self.index[g["home"]], self.index[g["away"]]
            d = np.zeros(len(total_mean))
            d[i], d[j] = 1, -1
            rows.append({"match_id": g["match_id"], "date": day, "home": g["home"], "away": g["away"],
                         "home_mean": float(total_mean[i]), "away_mean": float(total_mean[j]),
                         "home_variance": float(total_cov[i, i]), "away_variance": float(total_cov[j, j]),
                         "home_away_covariance": float(total_cov[i, j]),
                         "difference": float(d @ total_mean), "difference_variance": float(d @ total_cov @ d),
                         "home_term": float(total_mean[-1]), "p_home": float(p[0]), "p_draw": float(p[1]),
                         "p_away": float(p[2]), "home_history": self.counts[g["home"]],
                         "away_history": self.counts[g["away"]], "outcome_index": int(g["outcome"]),
                         "prediction_cutoff": self.last_day or "initial_prior",
                         "prediction_basis": "pre_day_only_fixed_pilot_rule"})
        outcomes = [g["outcome"] for g in games]
        logweights, updated, iterations = [], [], []
        for c in children:
            m, cov, logz, diag = batch_update(c.mean, c.cov, design, outcomes, kappas,
                                             self.params["delta"], self.numerics)
            if not np.isfinite(cov).all() or np.diag(cov).min() <= 0:
                raise NumericalFailure("Invalid posterior covariance")
            if self.numerics.get("full_child_psd_check", True) and np.linalg.eigvalsh(cov).min() < -self.numerics["psd_tolerance"]:
                raise NumericalFailure("Posterior covariance not PSD")
            updated.append(Component(0, m, cov, c.path))
            logweights.append(math.log(c.weight) + logz)
            iterations.append(diag["iterations"])
        posterior = np.exp(np.array(logweights) - logsumexp(logweights))
        self.components, reduction = self.reduce_components(updated, posterior)
        if not self.numerics.get("full_child_psd_check", True) and (len(self.diagnostics)+1)%self.numerics.get("retained_psd_check_every",25)==0:
            if any(np.linalg.eigvalsh(c.cov).min() < -self.numerics["psd_tolerance"] for c in self.components):
                raise NumericalFailure("Retained posterior covariance not PSD")
        for t in active:
            self.last[t] = day
        for g in games:
            self.counts[g["home"]] += 1
            self.counts[g["away"]] += 1
        self.last_day = day
        self.diagnostics.append({"date": day, "matches": len(games), "candidate_components": len(children),
                                 "retained_components": len(self.components), "transition_prior_tail": tail,
                                 "approximate_posterior_pruned_mass": reduction["approximate_posterior_pruned_mass"],
                                 "pruning_warning": reduction["pruning_warning"],
                                 "max_ep_iterations": max(iterations), **reduction})
        return rows

    def state(self):
        return {"schema_version": "strength-filter-pilot-v1", "teams": list(self.teams), "params": copy.deepcopy(self.params),
                "numerics": copy.deepcopy(self.numerics), "last": self.last.copy(), "last_day": self.last_day, "counts": self.counts.copy(),
                "components": [{"weight": c.weight, "mean": c.mean.tolist(), "cov": c.cov.tolist(), "path": c.path}
                               for c in self.components]}

    @classmethod
    def restore(cls, state):
        if state["schema_version"] != "strength-filter-pilot-v1":
            raise ValueError("Unknown checkpoint")
        obj = cls(state["teams"], state["params"], state["numerics"])
        obj.last, obj.last_day, obj.counts = state["last"].copy(), state["last_day"], state["counts"].copy()
        obj.components = [Component(c["weight"], np.array(c["mean"]), np.array(c["cov"]),
                                    tuple(tuple(e) for e in c["path"])) for c in state["components"]]
        n = len(obj.teams) + 1
        if not obj.components or abs(sum(c.weight for c in obj.components) - 1) > 1e-10:
            raise ValueError("Invalid checkpoint weights")
        for c in obj.components:
            if c.weight <= 0 or c.mean.shape != (n,) or c.cov.shape != (n, n):
                raise ValueError("Invalid checkpoint shape")
            if not np.isfinite(c.mean).all() or not np.isfinite(c.cov).all():
                raise ValueError("Nonfinite checkpoint")
            if np.max(abs(c.cov - c.cov.T)) > 1e-9 or np.linalg.eigvalsh(c.cov).min() < -obj.numerics["psd_tolerance"]:
                raise ValueError("Invalid checkpoint covariance")
        return obj
