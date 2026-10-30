"""Frozen, outcome-free coding; legal parent/child geography scenarios."""
from collections import Counter, defaultdict
import numpy as np

ERAS = ["1980s", "1990s", "2000s", "2010s", "2020_2024"]
REGIONS = ["150", "142", "002", "019", "009", ""]
NESTED = {"M0_nested", "M3_nested", "M4_type_slope", "M5_relation", "M3_plugin", "M3_total_normal"}


def relation(r):
    if not r["home_region"] or not r["away_region"]:
        return "unknown"
    if r["home_region"] != r["away_region"]:
        return "cross_region"
    return "same_unit" if r["home_unit"] == r["away_unit"] else "same_region_other_unit"


class Design:
    def __init__(self, rows):
        self.parents = {}
        self.units = {}
        self.anchor = {}
        self.weights = {}
        for side in ("home", "away"):
            counts = Counter((r[side + "_region"], r[side + "_unit"]) for r in rows)
            for region in REGIONS:
                units = sorted(u for (g, u), n in counts.items() if g == region and n)
                self.units[side, region] = units
                if not units:
                    continue
                anchor = max(units, key=lambda u: (counts[region, u], u))
                self.anchor[side, region] = anchor
                total = sum(counts[region, u] for u in units)
                for u in units:
                    self.weights[side, region, u] = counts[region, u] / total
                    old = self.parents.setdefault(u, region)
                    if old != region:
                        raise ValueError("INPUT_VERSION_MISMATCH: conflicting unit parent")

    def matrix(self, rows, model):
        n = len(rows)
        columns = [np.ones(n)]
        names = ["intercept"]
        if model != "M1_strength":
            for era in ERAS[1:]:
                columns.append(np.array([r["era"] == era for r in rows], float)); names.append("era:" + era)
            columns.append(np.array([r["tournament_group"] == "friendly" for r in rows], float)); names.append("friendly")
            for side in ("home", "away"):
                for region in REGIONS[1:]:
                    columns.append(np.array([r[side + "_region"] == region for r in rows], float)); names.append(side + ":region:" + (region or "unknown"))
                if model in NESTED:
                    for region in REGIONS:
                        if (side, region) not in self.anchor:
                            continue
                        anchor = self.anchor[side, region]
                        for u in self.units[side, region]:
                            if u == anchor:
                                continue
                            ratio = self.weights[side, region, u] / self.weights[side, region, anchor]
                            col = [(1. if r[side + "_unit"] == u else -ratio if r[side + "_unit"] == anchor else 0.)
                                   if r[side + "_region"] == region else 0. for r in rows]
                            columns.append(np.array(col)); names.append(side + ":within:" + u)
            if model == "M5_relation":
                columns.extend([np.array([r["home_region"] == r["away_region"] and bool(r["home_region"]) for r in rows], float),
                                np.array([relation(r) == "same_unit" for r in rows], float)])
                names.extend(["same_region", "same_unit"])
        return np.column_stack(columns), names

    def audit(self, rows, model):
        x, names = self.matrix(rows, model)
        singular = np.linalg.svd(x, compute_uv=False)
        rank = int(np.sum(singular > singular[0] * 1e-10))
        return dict(model_id=model, rows=len(rows), columns=len(names), rank=rank,
                    full_rank=rank == len(names), condition=float(singular[0] / singular[-1]), names=names)

    def set_home_unit(self, r, unit):
        new = dict(r, home_unit=unit, home_region=self.parents[unit])
        new["relation"] = relation(new)
        return new

    def set_away_unit(self, r, unit):
        new = dict(r, away_unit=unit, away_region=self.parents[unit])
        new["relation"] = relation(new)
        return new


def group_matches(r, group):
    for label, field in (("home_regions", "home_region"), ("away_regions", "away_region"),
                         ("home_units", "home_unit"), ("away_units", "away_unit")):
        if group.get(label) and r[field] not in group[label]:
            return False
    return not group.get("relations") or relation(r) in group["relations"]


class Support:
    """Observed support, not propensity-based identification or proof of overlap."""
    def __init__(self, rows, bins, minimum=20):
        self.bins = bins
        self.minimum = minimum
        self.counts = Counter()
        self.ranges = defaultdict(list)
        for r in rows:
            key = self.key(r)
            self.counts[key] += 1
            self.ranges[key[:-1]].append(float(r["strength_difference"]))
        self.ranges = {k: (min(v), max(v)) for k, v in self.ranges.items()}

    def key(self, r):
        return (r["era"], r["tournament_group"], r["home_region"], r["home_unit"], r["away_region"],
                int(np.searchsorted(self.bins, float(r["strength_difference"]), side="right")))

    def flags(self, rows):
        zero = []; sparse = []; outside = []
        for r in rows:
            key = self.key(r); count = self.counts[key]
            zero.append(count == 0); sparse.append(count < self.minimum)
            low, high = self.ranges.get(key[:-1], (np.inf, -np.inf))
            outside.append(not low <= float(r["strength_difference"]) <= high)
        return np.array(zero), np.array(sparse), np.array(outside)
