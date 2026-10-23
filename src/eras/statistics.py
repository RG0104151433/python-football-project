"""Deterministic counts and schedule diagnostics, without inferential intervals."""
from collections import Counter, defaultdict
from math import fsum

from .data import GROUPS, era_for, sample_id


def summarize(rows):
    n = len(rows)
    outcomes = Counter(r["outcome"] for r in rows)
    return dict(n_matches=n, n_home_wins=outcomes["home"], n_draws=outcomes["draw"],
                n_away_wins=outcomes["away"], home_win_rate=outcomes["home"] / n if n else None,
                draw_rate=outcomes["draw"] / n if n else None, away_win_rate=outcomes["away"] / n if n else None,
                mean_goal_difference=fsum(r["goal_difference"] for r in rows) / n if n else None,
                status="ok" if n else "empty_group")


def team_set(rows):
    return {r[field] for r in rows for field in ("home_team_id", "away_team_id")}


def schedule_rows(rows, sid, era_id, group):
    home, away, opponents, pairs = Counter(), Counter(), defaultdict(set), Counter()
    for row in rows:
        a, b = row["home_team_id"], row["away_team_id"]
        home[a] += 1
        away[b] += 1
        opponents[a].add(b)
        opponents[b].add(a)
        pairs[tuple(sorted((a, b)))] += 1
    teams = sorted(opponents)
    base = dict(sample_id=sid, analysis_era_id=era_id, tournament_group=group)
    team_rows = [dict(base, team_id=t, n_home=home[t], n_away=away[t],
                      n_matches=home[t] + away[t], n_distinct_opponents=len(opponents[t])) for t in teams]
    appearances = sorted((home[t] + away[t] for t in teams), reverse=True)
    possible = len(teams) * (len(teams) - 1) // 2
    dates = Counter(r["date"] for r in rows)
    metrics = {
        "n_teams": (len(teams), "teams"), "n_distinct_pairs": (len(pairs), "pairs"),
        "pair_coverage": (len(pairs) / possible if possible else None, "proportion"),
        "max_pair_repeats": (max(pairs.values(), default=0), "matches"),
        "max_team_appearances": (max(appearances, default=0), "appearances"),
        "top_5_appearance_share": (sum(appearances[:5]) / (2 * len(rows)) if rows else None, "proportion"),
        "n_dates": (len(dates), "dates"), "max_matches_same_date": (max(dates.values(), default=0), "matches"),
    }
    diagnostics = [dict(base, metric=k, value=v, unit=unit, status="ok" if rows else "empty_group")
                   for k, (v, unit) in metrics.items()]
    return team_rows, diagnostics


def build_statistics(samples, config, *, outcomes=True):
    tables = {k: [] for k in ("era_summary", "year_summary", "era_tournament_summary", "team_schedule", "schedule_diagnostics")}
    for name, rows in samples.items():
        sid = sample_id(rows, config["data_version"])
        if outcomes:
            periods = [(e["id"], e["start"], e["end"]) for e in config["eras"]]
            years = [(str(y), max(f"{y}-01-01", config["analysis_start"]),
                      min(f"{y}-12-31", config["analysis_end"]))
                     for y in range(int(config["analysis_start"][:4]), int(config["analysis_end"][:4]) + 1)]
            for table, definitions in (("era_summary", periods), ("year_summary", years)):
                for period_id, start, end in definitions:
                    selected = [r for r in rows if start <= r["date"] <= end]
                    tables[table].append(dict(sample_id=sid, sample_name=name, period_id=period_id,
                                              start_date=start, end_date=end,
                                              n_years=int(end[:4]) - int(start[:4]) + 1, **summarize(selected)))
        # Base/all is useful for unknown-classification diagnostics; do not double count these rows as strata.
        groups = ("all",) if name == "base_venue" else GROUPS
        for era in config["eras"]:
            for group in groups:
                selected = [r for r in rows if era_for(r["date"], config) == era["id"] and
                            (group == "all" or r["tournament_group"] == group)]
                teams, diagnostics = schedule_rows(selected, sid, era["id"], group)
                tables["team_schedule"].extend(teams)
                tables["schedule_diagnostics"].extend(diagnostics)
                if outcomes and name == "classified_venue":
                    tables["era_tournament_summary"].append(dict(sample_id=sid, analysis_era_id=era["id"],
                                                                  tournament_group=group, **summarize(selected)))
    if not outcomes:
        tables = {k: v for k, v in tables.items() if k in {"team_schedule", "schedule_diagnostics"}}
    return tables
