"""Authoritative integer counts and complete two-role composition."""
from collections import Counter, defaultdict

from .io import study_labels


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


def build_study_outputs(context, tables):
    config = context["config"]
    if config["protocol_id"] != "regions-study-v4":
        return tables
    classification = config["study_classification"]
    role_counts = Counter((role, r[role + "_team_id"], r[role + "_rule_id"])
                          for r in context["facts"] for role in ("home", "away"))
    registry = []
    reasons = {r["rule_id"]: r["reason"] for r in classification["overrides"] + classification["merges"]}
    for row in context["base_roster"]:
        start = max(row["date_start"], config["scope"]["start"])
        end = min(row["date_end"], config["scope"]["end"])
        if start > end:
            continue
        region, unit, rule = study_labels(row["team_id"], start, row["region_code"], row["partition_code"], row["rule_id"], classification)
        registry.append(dict(team_id=row["team_id"], team_label=row["team_name_zh"], source_team_label=row["source_team_label"],
                             base_rule_id=row["rule_id"], base_region=row["region_code"], base_unit=row["partition_code"],
                             study_region=region, study_unit=unit, study_rule_id=rule, date_start=start, date_end=end,
                             home_matches=role_counts["home", row["team_id"], row["rule_id"]],
                             away_matches=role_counts["away", row["team_id"], row["rule_id"]],
                             change_reason=next((reason for rid, reason in reasons.items() if rule.startswith(rid)), "沿用原M49-based项目规则"),
                             status="known" if region and unit else "unknown"))
    lookups = {(r["target_id"], r["group_id"]): r for r in tables["group_summary"]}
    matchups = []
    for tid, target in config["analysis_targets"].items():
        if not target["type"].startswith("matchup_"):
            continue
        for gid in target["groups"]:
            spec, result = config["groups"][gid], lookups[tid, gid]
            hu = spec["home_units"][0] if spec["home_units"] else ""
            au = spec["away_units"][0] if spec["away_units"] else ""
            level = "macro_to_macro" if tid == "M_MACRO" else "within_partition" if au else "outside_macro"
            matchups.append(dict(target_id=tid, group_id=gid, level=level, label=spec["label"],
                                 home_region=spec["home_regions"][0], home_unit=hu,
                                 away_region=spec["away_regions"][0], away_unit=au,
                                 **{k: result[k] for k in ("n_matches", "n_home_wins", "n_draws", "n_away_wins", "home_win_rate",
                                                          "standardized_home_win_rate", "reference_group", "status",
                                                          "standardization_status", "standardization_reason")}))
    tables.update(study_team_registry=registry, matchup_rates=matchups)
    return tables
