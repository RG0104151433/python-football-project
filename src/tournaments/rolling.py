"""Trailing calendar windows; keep explicit many-to-many match membership."""
from .data import GROUPS, require
from .standardize import reference, targets
from .statistics import count


def make_windows(analysis):
    first, last = int(analysis["analysis_start"][:4]), int(analysis["analysis_end"][:4])
    return [dict(window_id=f"{y}_{y+9}", start_date=f"{y}-01-01", end_date=f"{y+9}-12-31", label_year=y+9,
                 n_calendar_years=10) for y in range(first, last-8)]


def enumerate_membership(rows, windows):
    result = [dict(window_id=w["window_id"], match_id=r["match_id"]) for w in windows for r in rows
              if w["start_date"] <= r["date"] <= w["end_date"]]
    keys = [(r["window_id"], r["match_id"]) for r in result]
    require(len(keys) == len(set(keys)), "TQ_WINDOW_DUPLICATE", "Repeated match ID within a window")
    return result


def build_rolling(rows, grouped_counts, analysis, sid):
    windows = make_windows(analysis)
    membership = enumerate_membership(rows, windows)
    years = {(r["period_id"], r["tournament_group"]): r for r in grouped_counts if r["scope"] == "year"}
    tables = dict(rolling_windows=[], rolling_counts=[], window_membership=membership,
                  reference_weights=[], type_estimates=[], type_differences=[])
    definitions = []
    for w in windows:
        wid = w["window_id"]
        selected = [r for r in rows if w["start_date"] <= r["date"] <= w["end_date"]]
        strata = [str(y) for y in range(int(w["start_date"][:4]), int(w["end_date"][:4])+1)]
        missing = [y for y in strata if sum(years[(y, g)]["n_matches"] for g in GROUPS) == 0]
        tables["rolling_windows"].append(dict(w, n_observed_years=len(strata)-len(missing), n_matches=len(selected),
                                               missing_years=[int(y) for y in missing], status="ok" if selected else "empty_group"))
        counts = {g: count([r for r in selected if r["tournament_group"] == g]) for g in GROUPS}
        tables["rolling_counts"] += [dict(window_id=wid, tournament_group=g, **counts[g]) for g in GROUPS]
        weights = reference("rolling", wid, years, strata, "year")
        tables["reference_weights"] += weights
        for ref in (None, weights):
            e, d, t = targets("rolling", wid, counts, sid, ref, years)
            tables["type_estimates"] += e; tables["type_differences"] += d; definitions += t
    return tables, definitions
