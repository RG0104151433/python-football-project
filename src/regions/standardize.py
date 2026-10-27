"""Shared-reference rates, predeclared contrasts and fixed-design coefficients."""
import math
from collections import Counter, defaultdict
from itertools import combinations

from .describe import cells
from .io import require


def weighted_rate(layer_rows, weights):
    missing = [cell for cell, q in weights.items() if q > 0 and not layer_rows[cell]["n_matches"]]
    if missing:
        return None, "unsupported_positive_reference_layer", ";".join(e + "/" + t for e, t in missing)
    value = math.fsum(q * layer_rows[cell]["home_win_rate"] for cell, q in weights.items() if q > 0)
    return value, "ok", ""


def build_adjustments(tables, grouped, references, config):
    weights, reference_rows = {}, []
    for tid, rows in sorted(references.items()):
        counts = Counter((r["era"], r["tournament_group"]) for r in rows)
        total = len(rows)
        require(total > 0, "REG_EMPTY_REFERENCE", tid)
        weights[tid] = {}
        for era, kind in cells(config):
            n = counts[era, kind]
            q = n / total
            weights[tid][era, kind] = q
            reference_rows.append(dict(target_id=tid, reference_group=config["analysis_targets"][tid]["reference_group"],
                                       era=era, tournament_group=kind, n_reference_matches=n,
                                       n_reference_total=total, weight=q, status="ok" if n else "zero_weight"))
    strata = {(r["target_id"], r["group_id"], r["era"], r["tournament_group"]): r
              for r in tables["stratum_counts"]}
    summaries = {(r["target_id"], r["group_id"]): r for r in tables["group_summary"]}
    for (tid, gid), row in summaries.items():
        lookup = {cell: strata[tid, gid, *cell] for cell in cells(config)}
        value, status, reason = weighted_rate(lookup, weights[tid])
        row.update(reference_group=config["analysis_targets"][tid]["reference_group"],
                   standardized_home_win_rate=value, standardization_status=status, standardization_reason=reason)
    contrasts, layers, coefficients = [], [], []
    for spec in config["comparisons"]:
        cid, tid, a, b = (spec[k] for k in ("id", "target_id", "arm1", "arm2"))
        ra, rb = summaries[tid, a], summaries[tid, b]
        direct = ra["home_win_rate"] - rb["home_win_rate"] if ra["n_matches"] and rb["n_matches"] else None
        valid = ra["standardization_status"] == rb["standardization_status"] == "ok"
        reason = ";".join(x for x in (ra["standardization_reason"], rb["standardization_reason"]) if x)
        if spec.get("standardized_policy") == "unestimable_for_full_period_no_scope_change":
            valid, reason = False, reason or "full_period_standardization_not_authorized_for_this_descriptive_target"
        adjusted = ra["standardized_home_win_rate"] - rb["standardized_home_win_rate"] if valid else None
        contrasts.append(dict(contrast_id=cid, target_id=tid, study_id=spec["parent_study"], label=spec["label"],
                              arm1=a, arm2=b, reference_group=spec["reference_group"], n_arm1=ra["n_matches"],
                              n_arm2=rb["n_matches"], direct_arm1_rate=ra["home_win_rate"], direct_arm2_rate=rb["home_win_rate"],
                              adjusted_arm1_rate=ra["standardized_home_win_rate"], adjusted_arm2_rate=rb["standardized_home_win_rate"],
                              direct_difference=direct, direct_difference_pp=100 * direct if direct is not None else None,
                              adjusted_difference=adjusted, adjusted_difference_pp=100 * adjusted if adjusted is not None else None,
                              direct_minus_adjusted_pp=100 * (direct - adjusted) if direct is not None and adjusted is not None else None,
                              direct_status="ok" if direct is not None else "no_matches",
                              adjusted_status="ok" if valid else "unsupported_positive_reference_layer", reason=reason))
        for era, kind in cells(config):
            x, y = strata[tid, a, era, kind], strata[tid, b, era, kind]
            q = weights[tid][era, kind]
            d = x["home_win_rate"] - y["home_win_rate"] if x["n_matches"] and y["n_matches"] else None
            contribution = q * d if q and d is not None else 0.0 if not q else None
            layers.append(dict(contrast_id=cid, target_id=tid, era=era, tournament_group=kind,
                               n_arm1=x["n_matches"], wins_arm1=x["n_home_wins"], n_arm2=y["n_matches"],
                               wins_arm2=y["n_home_wins"], arm1_rate=x["home_win_rate"], arm2_rate=y["home_win_rate"],
                               weight=q, layer_difference=d, contribution=contribution,
                               status="zero_weight" if not q else "ok" if d is not None else "unsupported_positive_reference_layer"))
        for method in ("direct", "standardized"):
            if (method == "direct" and direct is None) or (method == "standardized" and adjusted is None):
                continue
            for gid, sign in ((a, 1), (b, -1)):
                for match in grouped[tid, gid]:
                    cell = match["era"], match["tournament_group"]
                    q = 1.0 if method == "direct" else weights[tid][cell]
                    n = summaries[tid, gid]["n_matches"] if method == "direct" else strata[tid, gid, *cell]["n_matches"]
                    coef = sign * q / n
                    if coef:
                        coefficients.append(dict(contrast_id=cid, target_id=tid, method=method,
                                                 match_id=match["match_id"], group_id=gid, era=cell[0], tournament_group=cell[1],
                                                 denominator=n, weight=q, coefficient=coef))
    tables.update(reference_weights=reference_rows, contrast_results=contrasts,
                  layer_contributions=layers, match_coefficients=coefficients)
    return tables


def validate_tables(facts, tables, config):
    checks = []

    def check(value, message):
        require(value, "REG_RECONCILIATION", message)
        checks.append(message)

    summary = {(r["target_id"], r["group_id"]): r for r in tables["group_summary"]}
    strata = defaultdict(list)
    for r in tables["stratum_counts"]:
        strata[r["target_id"], r["group_id"]].append(r)
        check(r["n_matches"] == r["n_home_wins"] + r["n_draws"] + r["n_away_wins"], "WDL:" + str((r["target_id"], r["group_id"], r["era"], r["tournament_group"])))
    for key, row in summary.items():
        check(len(strata[key]) == len(cells(config)) and all(sum(x[k] for x in strata[key]) == row[k]
              for k in ("n_matches", "n_home_wins", "n_draws", "n_away_wins")), "Layer totals:" + str(key))
        check(row["standardized_home_win_rate"] is None or 0 <= row["standardized_home_win_rate"] <= 1, "Rate bounds:" + str(key))
    refs = defaultdict(list)
    for r in tables["reference_weights"]:
        refs[r["target_id"]].append(r)
    for tid, rows in refs.items():
        check(abs(math.fsum(r["weight"] for r in rows) - 1) < 1e-12
              and sum(r["n_reference_matches"] for r in rows) == rows[0]["n_reference_total"], "Reference:" + tid)
    roles = Counter()
    for r in tables["team_contributions"]:
        roles[r["target_id"], r["group_id"], r["era"], r["tournament_group"], r["role"]] += r["n_matches"]
    opponents = Counter()
    for r in tables["opponent_composition"]:
        opponents[r["target_id"], r["group_id"], r["era"], r["tournament_group"]] += r["n_matches"]
    for r in tables["stratum_counts"]:
        key = tuple(r[k] for k in ("target_id", "group_id", "era", "tournament_group"))
        for role in ("home", "away"):
            check(roles[*key, role] == r["n_matches"], "Role total:" + str((*key, role)))
        check(opponents[key] == r["n_matches"], "Opponent total:" + str(key))
    home_wins = {r["match_id"]: r["home_win"] for r in facts}
    coefs = defaultdict(list)
    for r in tables["match_coefficients"]:
        coefs[r["contrast_id"], r["method"]].append(r)
    layer_map = defaultdict(list)
    for r in tables["layer_contributions"]:
        layer_map[r["contrast_id"]].append(r)
    for r in tables["contrast_results"]:
        for method, field in (("direct", "direct_difference"), ("standardized", "adjusted_difference")):
            rows = coefs[r["contrast_id"], method]
            if r[field] is None:
                check(not rows, "No false coefficients:" + r["contrast_id"] + method)
                continue
            estimate = math.fsum(x["coefficient"] * home_wins[x["match_id"]] for x in rows)
            check(abs(estimate - r[field]) < 1e-12, "Coefficient reconstruction:" + r["contrast_id"] + method)
            for gid, total in ((r["arm1"], 1), (r["arm2"], -1)):
                check(abs(math.fsum(x["coefficient"] for x in rows if x["group_id"] == gid) - total) < 1e-12,
                      "Coefficient sum:" + r["contrast_id"] + method + gid)
        if r["adjusted_difference"] is not None:
            check(abs(math.fsum(x["contribution"] for x in layer_map[r["contrast_id"]]) - r["adjusted_difference"]) < 1e-12,
                  "Layer difference reconstruction:" + r["contrast_id"])
    eu = config["analysis_targets"]["C_EUR"]["groups"]
    check(sum(summary["C_EUR", g]["n_matches"] for g in eu) == 8045, "European four-group coverage")
    for a, b, c in combinations(eu, 3):
        pa, pb, pc = [summary["C_EUR", g]["standardized_home_win_rate"] for g in (a, b, c)]
        if all(x is not None for x in (pa, pb, pc)):
            check(abs((pa - pb) + (pb - pc) - (pa - pc)) < 1e-12, "European transitivity:" + a + b + c)
    check(len(tables["analysis_membership"]) == len(config["analysis_targets"]) * len(facts), "Complete target flow")
    return dict(status="passed", n_checks=len(checks), checks=checks,
                inference="not_run", sensitivity="not_run", human_review="not_performed")
