"""Integer counts at overall, era and year levels; no model or inference."""
from collections import Counter, defaultdict

from .data import GROUPS


def count(rows):
    counts = Counter(r["outcome"] for r in rows)
    n = len(rows)
    return dict(n_matches=n, n_home_wins=counts["home"], n_draws=counts["draw"], n_away_wins=counts["away"],
                home_win_rate=counts["home"] / n if n else None, draw_rate=counts["draw"] / n if n else None,
                away_win_rate=counts["away"] / n if n else None, status="ok" if n else "empty_group")


def periods(analysis):
    result = [dict(scope="overall", period_id="all", start_date=analysis["analysis_start"], end_date=analysis["analysis_end"],
                   n_calendar_years=int(analysis["analysis_end"][:4]) - int(analysis["analysis_start"][:4]) + 1)]
    result += [dict(scope="era", period_id=e["id"], start_date=e["start"], end_date=e["end"],
                    n_calendar_years=int(e["end"][:4]) - int(e["start"][:4]) + 1) for e in analysis["eras"]]
    result += [dict(scope="year", period_id=str(y), start_date=f"{y}-01-01", end_date=f"{y}-12-31", n_calendar_years=1)
               for y in range(int(analysis["analysis_start"][:4]), int(analysis["analysis_end"][:4]) + 1)]
    return result


def build_counts(rows, analysis):
    return [dict(p, tournament_group=g, **count([r for r in rows if p["start_date"] <= r["date"] <= p["end_date"]
                                                              and r["tournament_group"] == g]))
            for p in periods(analysis) for g in GROUPS]


def build_flow(context):
    from ..eras.data import upstream_flow
    result = upstream_flow(context["root"], context["data_manifest"])
    excluded = Counter(m["primary_exclusion_reason"] for m in context["membership"] if not m["included"])
    result.append(dict(flow_id="analysis", stage="included", parent_stage="processed_matches", reason="included",
                       n_records=len(context["selected"]), basis="processed_matches", status="ok"))
    result += [dict(flow_id="analysis", stage="excluded", parent_stage="processed_matches", reason=k,
                    n_records=v, basis="processed_matches", status="ok") for k, v in sorted(excluded.items())]
    return result
