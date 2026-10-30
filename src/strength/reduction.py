"""Moment-preserving mixture reduction. History labels become representative.

Runnalls pair cost bounds KL between the *current Gaussian mixtures* before and
after reduction, not error relative to true filtering or accumulated time error.
The scalable cluster route uses a descriptor surrogate and claims no KL bound.
"""
from __future__ import annotations

import math
import heapq
import numpy as np

from .filter import Component, StrengthFilter, NumericalFailure


def moments(components):
    weights = np.array([c.weight for c in components])
    weights /= weights.sum()
    mean = sum(w * c.mean for w, c in zip(weights, components))
    cov = sum(w * (c.cov + np.outer(c.mean - mean, c.mean - mean)) for w, c in zip(weights, components))
    return mean, cov


def merge(components):
    total = sum(c.weight for c in components)
    if total <= 0:
        raise NumericalFailure("Nonpositive merged mass")
    mean, cov = moments(components)
    representative = max(components, key=lambda c: c.weight).path
    return Component(total, mean, (cov + cov.T) / 2, representative)


def runnalls(components, target):
    """Deterministic greedy KL-bound pair merges with exact full covariance."""
    active = {k: c for k, c in enumerate(components)}
    if len(active)*(len(active)-1)//2 > 500000:
        raise NumericalFailure("Runnalls pair-memory budget exceeded")
    logs = {}
    for k, c in active.items():
        sign, value = np.linalg.slogdet(c.cov)
        if sign <= 0:
            raise NumericalFailure("Nonpositive component determinant")
        logs[k] = float(value)
    original_term = sum(c.weight * logs[k] for k, c in active.items())
    costs = []

    def add_pairs(index, others):
        a = active[index]
        other_ids = sorted(others)
        if not other_ids:
            return
        weights = np.array([active[j].weight for j in other_ids])
        total = a.weight + weights
        ratio = a.weight / total
        means = np.stack([active[j].mean for j in other_ids])
        diff = means - a.mean
        covs = ratio[:, None, None] * a.cov + (1-ratio)[:, None, None] * np.stack([active[j].cov for j in other_ids])
        covs += (ratio*(1-ratio))[:, None, None] * diff[:, :, None] * diff[:, None, :]
        signs, dets = np.linalg.slogdet(covs)
        if np.any(signs <= 0):
            raise NumericalFailure("Merged determinant nonpositive")
        values = .5 * (total * dets - a.weight * logs[index] -
                       weights * np.array([logs[j] for j in other_ids]))
        for j, v in zip(other_ids, values):
            a_id, b_id = sorted((index, j))
            heapq.heappush(costs, (max(0.0, float(v)), a_id, b_id))

    for k in sorted(active):
        add_pairs(k, [j for j in active if j < k])
    next_id = len(active)
    while len(active) > target:
        while True:
            _, a, b = heapq.heappop(costs)
            if a in active and b in active:
                break
        child = merge([active[a], active[b]])
        del active[a], active[b]
        active[next_id] = child
        logs[next_id] = float(np.linalg.slogdet(child.cov)[1])
        add_pairs(next_id, [j for j in active if j != next_id])
        next_id += 1
    result = [active[k] for k in sorted(active)]
    bound = .5 * (sum(c.weight * logs[k] for k, c in active.items()) - original_term)
    return result, max(0.0, float(bound))


def cluster(components, target, max_iter=30):
    """Weighted deterministic Lloyd reduction using mean/variance/h-correlation.

All cluster moments use the FULL covariance even though assignment descriptors
are compressed. Unknown future-team coordinates constant across components have
no effect on centered descriptor distances.
"""
    if len(components) <= target:
        return components, 0
    weights = np.array([c.weight for c in components])
    means = np.stack([c.mean for c in components])
    variances = np.stack([np.diag(c.cov) for c in components])
    scale = np.sqrt(np.maximum(weights @ variances, 1e-12))
    hcov = np.stack([c.cov[:, -1] for c in components])
    features = np.concatenate((means / scale, .5*np.log(np.maximum(variances, 1e-12)),
                               hcov / np.sqrt(np.maximum(variances * variances[:, -1:], 1e-24))), axis=1)
    features -= weights @ features
    first = int(np.argmax(weights))
    centers = [features[first]]
    distances = np.sum((features-centers[0])**2, axis=1)
    for _ in range(1, target):
        best = int(np.argmax(weights * distances))
        if distances[best] < 1e-20:
            break
        centers.append(features[best])
        distances = np.minimum(distances, np.sum((features-features[best])**2, axis=1))
    centers = np.array(centers)
    previous = None
    for iteration in range(max_iter):
        distances = np.maximum(0, np.sum(features*features, axis=1)[:, None] +
                               np.sum(centers*centers, axis=1)[None, :] - 2*features@centers.T)
        labels = np.argmin(distances, axis=1)
        if previous is not None and np.array_equal(labels, previous):
            break
        previous = labels.copy()
        for k in range(len(centers)):
            selected = labels == k
            if selected.any():
                centers[k] = weights[selected] @ features[selected] / weights[selected].sum()
    result = [merge([components[j] for j in np.flatnonzero(labels == k)])
              for k in range(len(centers)) if np.any(labels == k)]
    return result, iteration + 1


class ReducedStrengthFilter(StrengthFilter):
    def reduce_components(self, updated, posterior):
        for c, w in zip(updated, posterior):
            c.weight = float(w)
        # Remove only exact floating-point-zero weights, not a tuned probability cutoff.
        original = [c for c in updated if c.weight > 0]
        before_m, before_c = moments(original)
        method = self.numerics.get("reducer", "cluster")
        if len(original) <= self.numerics["max_components"]:
            result, bound, iterations = original, 0.0, 0
        elif method == "runnalls":
            result, bound = runnalls(original, self.numerics["max_components"])
            iterations = 0
        elif method == "cluster":
            result, iterations = cluster(original, self.numerics["max_components"],
                                          self.numerics.get("cluster_iterations", 30))
            bound = None
        elif method == "hybrid":
            # Nested, moment-preserving partitions: a bounded coarse grouping
            # followed by full-covariance pair selection. No branch mass deleted.
            coarse, iterations = cluster(original, 2*self.numerics["max_components"],
                                           self.numerics.get("cluster_iterations", 30))
            result, _ = runnalls(coarse, self.numerics["max_components"])
            original_logdet=sum(c.weight*np.linalg.slogdet(c.cov)[1] for c in original)
            final_logdet=sum(c.weight*np.linalg.slogdet(c.cov)[1] for c in result)
            bound=max(0.0,float(.5*(final_logdet-original_logdet)))
        else:
            raise ValueError("Unknown reducer")
        total = sum(c.weight for c in result)
        for c in result:
            c.weight /= total
        after_m, after_c = moments(result)
        error = max(float(np.max(abs(after_m-before_m))), float(np.max(abs(after_c-before_c))))
        if error > 1e-8:
            raise NumericalFailure("Mixture moments not preserved")
        return result, {"approximate_posterior_pruned_mass": 0.0, "pruning_warning": False,
                        "reducer": method, "moment_error": error,
                        "current_gaussian_mixture_KL_bound": bound, "cluster_iterations": iterations,
                        "path_semantics": "representative_history_only_after_merge; no_exact_change_attribution"}
