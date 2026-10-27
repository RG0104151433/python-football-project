"""Authoritative integer counts and complete two-role composition."""
from collections import Counter, defaultdict


def cells(config):
    return [(e["id"], t) for e in config["strata"]["eras"] for t in config["strata"]["tournament_groups"]]


def count(rows):
    n = len(rows)
    wins = sum(r["home_win"] for r in rows)
    draws = sum(r["outcome"] == "draw" for r in rows)
    return dict(n_matches=n, n_home_wins=wins, n_draws=draws, n_away_wins=n - wins - draws,
                home_win_rate=wins / n if n else None, draw_rate=draws / n if n else None,
                away_win_rate=(n - wins - draws) / n if n else None, status="ok" if n else "no_matches")


def build_counts(grouped, config, team_labels):
    summaries, strata, contributions, opponents = [], [], [], []
    for (tid, gid), rows in sorted(grouped.items()):
        summary = dict(target_id=tid, group_id=gid, group_label=config["groups"][gid]["label"], **count(rows))
        summary.update(n_home_teams=len({r["home_team_id"] for r in rows}),
                       n_away_teams=len({r["away_team_id"] for r in rows}))
        summaries.append(summary)
        by_cell = defaultdict(list)
        for r in rows:
            by_cell[r["era"], r["tournament_group"]].append(r)
        for era, kind in cells(config):
            subset = by_cell[era, kind]
            prefix = dict(target_id=tid, group_id=gid, era=era, tournament_group=kind)
            strata.append(dict(**prefix, **count(subset), group_share=len(subset) / len(rows) if rows else None))
            for role in ("home", "away"):
                counts = Counter(r[role + "_team_id"] for r in subset)
                contributions.extend(dict(**prefix, role=role, team_id=team, team_label=team_labels[team],
                                          n_matches=n, denominator=len(subset), share=n / len(subset))
                                     for team, n in sorted(counts.items()))
            counts = Counter((r["away_region"], r["away_unit"]) for r in subset)
            opponents.extend(dict(**prefix, away_region=region, away_unit=unit, n_matches=n,
                                  denominator=len(subset), share=n / len(subset))
                             for (region, unit), n in sorted(counts.items()))
    return dict(group_summary=summaries, stratum_counts=strata,
                team_contributions=contributions, opponent_composition=opponents)
