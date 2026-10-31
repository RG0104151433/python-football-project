"""Calendar boundaries, past-only selection and paired bounded-loss mathematics."""
from datetime import date
import math
import numpy as np


def anniversary(day, years):
    d = date.fromisoformat(day)
    if not isinstance(years, int) or isinstance(years, bool) or years <= 0:
        raise ValueError("WINDOW_INVALID")
    try:
        return d.replace(year=d.year-years).isoformat()
    except ValueError:
        if d.month == 2 and d.day == 29:
            return date(d.year-years, 2, 28).isoformat()
        raise


def bounds(day, years, start):
    date.fromisoformat(day); date.fromisoformat(start)
    left = start if years is None else max(start, anniversary(day, years))
    if left >= day:
        raise ValueError("WINDOW_EMPTY_CALENDAR")
    return left, day


def training_slice(rows, year, years, start="1980-01-01"):
    left, right = bounds(f"{year}-01-01", years, start)
    selected = sorted((r for r in rows if left <= r['date'] < right), key=lambda r: (r['date'], r['match_id']))
    if not selected:
        raise ValueError("NO_TRAINING_ROWS")
    if len({r['match_id'] for r in selected}) != len(selected):
        raise ValueError("DUPLICATE_MATCH")
    return selected, dict(left_inclusive=left, right_exclusive=right, rows=len(selected),
                          actual_min=selected[0]['date'], actual_max=selected[-1]['date'])


def label(years):
    return "cumulative" if years is None else f"{years}y"


def log_losses(probabilities, outcomes, epsilon=1e-6):
    p, y = np.asarray(probabilities, float), np.asarray(outcomes, int)
    if p.shape != y.shape or not p.size or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)) or not np.isin(y, [0, 1]).all():
        raise ValueError("INVALID_FORECAST_OR_TARGET")
    q = np.clip(p, epsilon, 1-epsilon)
    return -(y*np.log(q)+(1-y)*np.log1p(-q))


def select_past(annual, year, candidates):
    """Only prior-year losses, identical match sets and complete candidate support."""
    past = [r for r in annual if int(r['year']) < year and int(r['year']) >= 2000]
    expected = set(range(2000, year)); result = []
    for w in candidates:
        rr = [r for r in past if r['window'] == label(w)]
        if {int(r['year']) for r in rr} != expected or len(rr) != len(expected):
            raise ValueError("SELECTION_PAST_INCOMPLETE")
        for r in rr:
            peers = [s for s in past if int(s['year']) == int(r['year'])]
            if len({(int(s['matches']), s['id_set_sha256']) for s in peers}) != 1:
                raise ValueError("SELECTION_SAMPLE_MISMATCH")
        n = sum(int(r['matches']) for r in rr)
        if n == 0:
            raise ValueError("SELECTION_EMPTY")
        loss = sum(float(r['loss_sum']) for r in rr)/n
        result.append((loss, -(w if w is not None else 100000), label(w)))
    return min(result)[2]


def paired_radius(day_counts, epsilon=1e-6, alpha=.05, pairs=60, powers=range(-18, 1)):
    """Ville+Hoeffding union over fixed lambda/sign/pairs. See project proof.

    Target: accumulated *conditional expected* paired clipped loss divided by
    realised N, with batch membership known before same-date results. Not an
    unconditional future-population effect or retrospective post-selection proof.
    """
    ns = np.asarray(day_counts, float)
    if not ns.size or np.any(ns <= 0) or not np.isfinite(ns).all() or not 0 < epsilon < .5 or not 0 < alpha < 1 or pairs < 1:
        raise ValueError("INVALID_BOUND_INPUT")
    lambdas = np.exp2(np.asarray(list(powers), float))
    if not lambdas.size or not np.isfinite(lambdas).all() or np.any(lambdas <= 0):
        raise ValueError("INVALID_LAMBDA_GRID")
    b = math.log((1-epsilon)/epsilon)
    v = b*b*float(ns@ns)
    c = math.log(2*pairs*len(lambdas)/alpha)
    return float(np.min(c/lambdas+lambdas*v/2)/ns.sum())
