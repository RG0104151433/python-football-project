"""Same population and scenario functions for both methods and truth diagnostics."""
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize
from scipy.special import log_ndtr, ndtr
from src.strength_joint.model import Kernel, slopes
from src.strength_stage6_sensitivity import read, materialize
from src.strength.io import ROOT


def probability_and_gradient(result, rows, design):
    x, names = design.matrix(rows, result["model_id"])
    if names != result["names"]: raise ValueError("TARGET_COLUMN_MISMATCH")
    theta = np.asarray(result["theta"]); s = slopes(rows, result["model_id"])
    b = np.exp(s @ theta[x.shape[1]:]) if s.shape[1] else np.zeros(len(rows))
    lp, de, db = Kernel(rows).evaluate(x @ theta[:x.shape[1]], b, np.ones(len(rows)))
    p = np.exp(lp)
    gradient = np.column_stack((x*(p*de)[:, None], s*(p*db*b)[:, None]))
    return p, gradient


class Targets:
    def __init__(self, cfg, registry):
        self.registry = registry; self.members = defaultdict(list); self.pieces = defaultdict(list)
        prep = ROOT / cfg["preparation"]
        for r in read(prep / "reference_membership.csv.gz"): self.members[r["reference_id"]].append(r["match_id"])
        for r in read(prep / "scenario_mixtures.csv"): self.pieces[r["target_id"], r["reference_kind"], r["arm"]].append(r)

    def evaluate(self, models, rows, design):
        index = {r["match_id"]: r for r in rows}; cache = {}
        for item in self.registry:
            key = (item["target_id"], item["reference_kind"], item["reference_id"])
            if key in cache: continue
            ids = self.members[item["reference_id"]]; value = {}; gradients = {}
            for model_id in ("M0_nested", "M3_nested"):
                result = models[model_id]; total = 0.; grad = np.zeros(len(result["theta"]))
                for arm, sign in (("1", 1), ("2", -1)):
                    for weight, scenario in materialize(self.pieces[key[0], key[1], arm], ids, index):
                        p, g = probability_and_gradient(result, scenario, design)
                        total += sign*weight*float(p.mean()); grad += sign*weight*g.mean(axis=0)
                value[model_id] = 100*total; gradients[model_id] = 100*grad
            cache[key] = value, gradients
        values, jac = [], []
        p0 = len(models["M0_nested"]["theta"]); p3 = len(models["M3_nested"]["theta"])
        for item in self.registry:
            v, g = cache[item["target_id"], item["reference_kind"], item["reference_id"]]
            if item["effect_size_axis"] == "level":
                values.append(v["M3_nested"]); jac.append(np.r_[np.zeros(p0), g["M3_nested"]])
            else:
                values.append(v["M3_nested"]-v["M0_nested"]); jac.append(np.r_[-g["M0_nested"], g["M3_nested"]])
        return np.array(values), np.array(jac)


def soft_probit_projection(x, probabilities):
    """Cross-world mean soft probabilities on FIXED design; not one-path truth."""
    x = np.asarray(x, float); p = np.asarray(probabilities, float)
    if np.any((p <= 0) | (p >= 1)) or np.linalg.matrix_rank(x) < x.shape[1]:
        raise ValueError("INVALID_PROJECTION_INPUT")
    def objective(beta):
        eta = x @ beta; lp = log_ndtr(eta); lq = log_ndtr(-eta)
        phi = np.exp(-eta*eta/2)/np.sqrt(2*np.pi)
        gradient = x.T @ ((1-p)*np.exp(np.log(phi)-lq)-p*np.exp(np.log(phi)-lp)) / len(p)
        return -float(np.mean(p*lp+(1-p)*lq)), gradient
    result = minimize(objective, np.zeros(x.shape[1]), jac=True, method="BFGS", options={"gtol": 1e-10, "maxiter": 1000})
    loss, grad = objective(result.x)
    if max(abs(grad)) > 1e-7: raise ValueError("SOFT_PROJECTION_FAILED")
    return dict(theta=result.x.tolist(), loss=loss, gradient_max=float(max(abs(grad))),
                truth_precision_admitted=False, role="numerical_projection_only_precision_requires_world_batches")
