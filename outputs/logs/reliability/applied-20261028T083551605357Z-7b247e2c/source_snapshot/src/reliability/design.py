"""Reconstruct conditional linear targets without estimating covariance.

Sources are the pinned, independently checked descriptive tables. Components
retain exact integer reference fractions. Dense coefficient vectors live only
in memory; small recipes and design diagnostics are the reproducible artifacts.
"""
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np


class DesignError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DesignError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def group_matches(row, spec):
    """Independent selection from persisted both-role facts, not source helpers."""
    if spec["eligibility"] and row[spec["eligibility"] + "_usable"] != "true":
        return False
    for key, field in (("home_regions", "home_region"), ("home_units", "home_unit"),
                       ("away_regions", "away_region"), ("away_units", "away_unit"),
                       ("relations", "relation")):
        if spec.get(key) and row[field] not in spec[key]:
            return False
    return True


def compile_components(facts, components):
    """Return coefficients, exact observed statistic and missing positive layers.

    A component is a signed weighted mean on explicitly indexed observations.
    Zero-reference empty layers are harmless; positive-reference empty layers
    invalidate the whole target. Components may overlap and must be added.
    """
    vector = np.zeros(len(facts), dtype=float)
    exact = Fraction(0)
    missing = []
    for part in components:
        weight = Fraction(part["q_numerator"], part["q_denominator"])
        sign = part["multiplier"]
        indices = part["indices"]
        if not weight or not sign:
            continue
        if not indices:
            missing.append(part["cell_id"])
            continue
        amount = weight * sign / len(indices)
        vector[indices] += float(amount)
        exact += amount * sum(int(facts[i]["home_win"]) for i in indices)
    if missing:
        return None, None, sorted(set(missing))
    return vector, exact, []


def shared_pair_counts(facts):
    """Potential dependency opportunities, not measured correlations."""
    home = Counter(r["home_team_id"] for r in facts)
    away = Counter(r["away_team_id"] for r in facts)
    both = home + away
    pair = Counter(tuple(sorted((r["home_team_id"], r["away_team_id"]))) for r in facts)
    c2 = lambda n: n * (n - 1) // 2
    shared = sum(c2(n) for n in both.values()) - sum(c2(n) for n in pair.values())
    return dict(n_matches=len(facts), n_teams=len(both), n_unordered_pairs=len(pair),
                all_match_pairs=c2(len(facts)), sharing_any_team_pairs=shared,
                same_home_pairs=sum(c2(n) for n in home.values()),
                same_away_pairs=sum(c2(n) for n in away.values()),
                cross_role_shared_team_incidents=sum(home[t] * away[t] for t in both),
                repeated_unordered_pair_match_pairs=sum(c2(n) for n in pair.values()),
                max_match_dependency_degree=max((both[h] + both[a] - pair[tuple(sorted((h, a)))] - 1
                                               for h, a in ((r["home_team_id"], r["away_team_id"]) for r in facts)), default=0))


def numerical_row_rank(matrix):
    if not len(matrix):
        return 0
    norms = np.linalg.norm(matrix, axis=1)
    nonzero = matrix[norms > 0] / norms[norms > 0, None]
    # This is coefficient-row algebra, not covariance/effective-sample rank.
    return int(np.linalg.matrix_rank(nonzero, tol=1e-10)) if len(nonzero) else 0


def competition_context(facts, raw, raw_sha):
    """Recover a descriptive label; name x year is NOT a true edition ID."""
    result = []
    for row in facts:
        prefix, file_sha, number = row["source_record_id"].split(":")
        require(prefix == "results" and file_sha == raw_sha, "Raw source identity mismatch")
        require(1 <= int(number) <= len(raw), "Raw source record number out of range")
        record = raw[int(number) - 1]
        require(all(record[k] == row[k] for k in ("date", "home_score", "away_score", "city", "country")),
                "Raw competition join failed on source fields:" + row["match_id"])
        require(record["neutral"].strip().lower() == "false", "Raw neutral status mismatch")
        require((record["tournament"].strip().lower() == "friendly") == (row["tournament_group"] == "friendly"),
                "Raw tournament type mismatch")
        result.append(dict(match_id=row["match_id"], source_record_id=row["source_record_id"],
                           tournament_name=record["tournament"].strip(), year=row["year"],
                           edition_id="", round_id="", label_status="name_and_year_only_not_true_edition"))
    return result


def build_design(root, config_path="config/reliability_design.json"):
    root = Path(root).resolve()
    cfg = read_json(root / config_path)
    protocol = read_json(root / cfg["estimand_protocol"])
    inputs, parent_outputs, checks = {}, {}, []

    def read(path):
        inputs[path] = sha(root / path)
        return read_json(root / path) if path.endswith(".json") else list(rows(root / path))

    def check(ok, label):
        require(ok, label)
        checks.append(label)

    inputs[config_path] = sha(root / config_path)
    inputs[cfg["estimand_protocol"]] = sha(root / cfg["estimand_protocol"])
    manifests = {key: read(path) for key, path in cfg["parent_manifests"].items()}
    for key, manifest in manifests.items():
        check(manifest["analysis_id"] == protocol["scope"]["analysis_ids"]["question_" + key[-1]], "analysis identity:" + key)
        for path, expected in manifest["outputs"].items():
            check(sha(root / path) == expected, "parent output:" + path)
            parent_outputs[path] = expected
    roots = {q: f"outputs/tables/{kind}/{manifests[q]['analysis_id']}"
             for q, kind in (("Q1", "eras"), ("Q2", "tournaments"), ("Q3", "regions"))}
    q1, q2, q3 = (read(cfg[k]) for k in ("q1_config", "q2_config", "q3_config"))
    facts = read(roots["Q3"] + "/analysis_matches.csv")
    facts.sort(key=lambda r: r["match_id"])
    lookup = {r["match_id"]: i for i, r in enumerate(facts)}
    check(len(facts) == len(lookup) == protocol["scope"]["n_parent_matches"], "unique parent match ids")
    for q, field in (("Q1", "in_base_venue"), ("Q2", "included")):
        members = read(roots[q] + "/analysis_membership.csv")
        included = [r["match_id"] for r in members if r[field] == "true"]
        check(len(included) == len(set(included)) and set(included) == set(lookup), "same included parent:" + q)
    check(all(r["home_team_id"] != r["away_team_id"] and r["is_neutral"] == "false"
              and r["result_basis"] == protocol["scope"]["result_basis"]
              and int(r["home_win"]) == int(int(r["home_score"]) > int(r["away_score"])) for r in facts), "outcome and role integrity")
    dates = [r["date"] for r in facts]
    check(min(dates) >= protocol["scope"]["date_start"] and max(dates) <= protocol["scope"]["date_end"], "date scope")
    raw = read(cfg["raw_results"])
    check(inputs[cfg["raw_results"]] == cfg["raw_results_sha256"], "raw competition source hash")
    competition = competition_context(facts, raw, cfg["raw_results_sha256"])
    check(len(competition) == len(facts), "all raw competition labels joined by original record, not fuzzy team/date matching")
    sources = {
        "Q1": read(roots["Q1"] + "/era_contrasts.csv"),
        "Q2": read(roots["Q2"] + "/type_differences.csv"),
        "Q3": read(roots["Q3"] + "/contrast_results.csv"),
        "MATRIX": read(roots["Q3"] + "/matchup_rates.csv"),
    }
    # Current Q1 main reference is pooled-match composition, exactly reconstructed.
    refs1 = read(roots["Q1"] + "/reference_weights.csv")
    refs2 = read(roots["Q2"] + "/reference_weights.csv")
    refs3 = read(roots["Q3"] + "/reference_weights.csv")
    friendly = sum(r["tournament_group"] == "friendly" for r in facts)
    w = Fraction(friendly, len(facts))
    main_ref = next(r for r in refs1 if r["scheme"] == "pooled_matches" and r["tournament_group"] == "friendly")
    check(q1["reference_scheme"] == "pooled_matches" and abs(float(w) - float(main_ref["weight"])) < 5e-11, "Q1 exact main reference")

    catalogue, components_out, vectors = [], [], {}

    def part(indices, weight=Fraction(1), sign=1, cell="all", **selector):
        return dict(indices=sorted(indices), q_numerator=weight.numerator, q_denominator=weight.denominator,
                    multiplier=sign, cell_id=cell, **selector)

    def add(tid, question, family, kind, components, source_path, source_key, source_field, source_value,
            label, source_scale=100, parent_target="", reference=""):
        check(tid not in {r["target_id"] for r in catalogue}, "unique target:" + tid)
        vec, exact, missing = compile_components(facts, components)
        check((source_value == "") == (vec is None), "availability:" + tid)
        if vec is not None:
            check(abs(float(exact) - float(source_value) / source_scale) < 1e-11, "source estimate:" + tid)
            y = np.array([int(r["home_win"]) for r in facts])
            check(abs(float(vec @ y) - float(exact)) < 1e-12, "per-match reconstruction:" + tid)
            expected_sum = 1 if kind == "rate" else 0
            check(abs(float(vec.sum()) - expected_sum) < 1e-12, "coefficient sum:" + tid)
            vectors[tid] = vec
        else:
            check(bool(missing), "unsupported reason:" + tid)
        catalogue.append(dict(target_id=tid, question=question, family=family, kind=kind, label=label,
                              status="supported_point_target" if vec is not None else "unsupported_positive_reference_layer",
                              missing_cells=";".join(missing), estimate_probability=float(exact) if exact is not None else None,
                              display_unit="percent" if kind == "rate" else "percentage_points", display_multiplier=100,
                              source_table=source_path, source_row_key=source_key, source_field=source_field,
                              source_unit="probability" if source_scale == 1 else "percentage_points",
                              source_estimate=source_value, reference_id=reference, parent_target=parent_target,
                              uncertainty_status="not_run", method_eligibility="pending_step_3" if vec is not None else "unsupported"))
        for number, p in enumerate(components):
            n = len(p["indices"])
            components_out.append(dict(target_id=tid, component_no=number, **{k: v for k, v in p.items() if k != "indices"},
                                       n_matches=n, n_home_wins=sum(int(facts[i]["home_win"]) for i in p["indices"]),
                                       coefficient=None if not n and p["q_numerator"] else float(Fraction(p["multiplier"] * p["q_numerator"], p["q_denominator"]) / n) if n else 0,
                                       selector_contract="Q1/Q2: era/year/type filters; Q3: persisted target/group membership, with optional era/type"))

    def q1_parts(era, sign, adjusted):
        ids = [i for i, r in enumerate(facts) if r["era"] == era]
        if not adjusted:
            return [part(ids, sign=sign, cell=era + "/all", era=era)]
        return [part([i for i in ids if facts[i]["tournament_group"] == g], q, sign, era + "/" + g,
                     era=era, tournament_group=g) for g, q in (("friendly", w), ("non_friendly", 1 - w))]

    for spec in q1["primary_contrasts"]:
        raw = q1_parts(spec["later"], 1, False) + q1_parts(spec["earlier"], -1, False)
        adj = q1_parts(spec["later"], 1, True) + q1_parts(spec["earlier"], -1, True)
        change = raw + [dict(p, multiplier=-p["multiplier"]) for p in adj]
        for method, comps, field, family in (("adjusted", adj, "standardized_difference", "CORE"),
                                              ("raw", raw, "observed_difference", "AUX"),
                                              ("change", change, "composition_adjustment_difference", "AUX")):
            row = next(r for r in sources["Q1"] if r["contrast_id"] == spec["id"] and r["reference_id"] == main_ref["reference_id"] and r["estimand"] == field)
            add("Q1:" + spec["id"] + ":" + method, "Q1", family, "difference", comps,
                roots["Q1"] + "/era_contrasts.csv", spec["id"] + "/" + field + "/" + main_ref["reference_id"],
                "estimate", row["estimate"], spec["id"] + " " + method, reference=main_ref["reference_id"])

    def q2_parts(row):
        scope, period = row["scope"], row["period_id"]
        if scope == "overall":
            ids = list(range(len(facts)))
        elif scope == "era":
            ids = [i for i, r in enumerate(facts) if r["era"] == period]
        else:
            begin, end = map(int, period.split("_"))
            ids = [i for i, r in enumerate(facts) if begin <= int(r["year"]) <= end]
        if row["estimand"] == "raw":
            return [part([i for i in ids if facts[i]["tournament_group"] == g], sign=sign,
                         cell=period + "/" + g, scope=scope, period_id=period, tournament_group=g)
                    for g, sign in (("friendly", 1), ("non_friendly", -1))]
        refs = [r for r in refs2 if r["reference_id"] == row["reference_id"]]
        result = []
        for ref in refs:
            weight = Fraction(int(ref["n_reference_matches"]), int(ref["n_reference_total"]))
            selected = [i for i in ids if facts[i][ref["stratum_kind"]] == ref["stratum_id"]]
            check(len(selected) == int(ref["n_reference_matches"]), "Q2 reference stratum:" + row["contrast_id"] + ref["stratum_id"])
            for g, sign in (("friendly", 1), ("non_friendly", -1)):
                result.append(part([i for i in selected if facts[i]["tournament_group"] == g], weight, sign,
                                   ref["stratum_id"] + "/" + g, scope=scope, period_id=period,
                                   tournament_group=g, **{ref["stratum_kind"]: ref["stratum_id"]}))
        return result

    for row in sources["Q2"]:
        if row["scope"] == "rolling" and row["estimand"] == "raw":
            continue
        family = "ROLLING" if row["scope"] == "rolling" else "CORE" if row["estimand"] == "era_standardized" else "AUX"
        add("Q2:" + row["contrast_id"], "Q2", family, "difference", q2_parts(row), roots["Q2"] + "/type_differences.csv",
            row["contrast_id"], "estimate", row["estimate"], row["contrast_id"], reference=row["reference_id"])
    raw2 = next(r for r in sources["Q2"] if r["scope"] == "overall" and r["estimand"] == "raw")
    adj2 = next(r for r in sources["Q2"] if r["scope"] == "overall" and r["estimand"] == "era_standardized")
    add("Q2:overall:raw_minus_adjusted", "Q2", "AUX", "difference",
        q2_parts(raw2) + [dict(p, multiplier=-p["multiplier"]) for p in q2_parts(adj2)],
        roots["Q2"] + "/type_differences.csv", raw2["contrast_id"] + " minus " + adj2["contrast_id"],
        "estimate(raw)-estimate(adjusted)", str(float(raw2["estimate"]) - float(adj2["estimate"])),
        "全期赛事直接差减共同年代差", reference=adj2["reference_id"])

    masks = {gid: [i for i, r in enumerate(facts) if group_matches(r, spec)] for gid, spec in q3["groups"].items()}
    masks_set = {gid: set(ids) for gid, ids in masks.items()}
    target_groups = q3["analysis_targets"]
    membership_path = roots["Q3"] + "/analysis_membership.csv"
    inputs[membership_path] = sha(root / membership_path)
    seen = set()
    for row in rows(root / membership_path):
        tid, mid = row["target_id"], row["match_id"]
        check_key = (tid, mid)
        require(check_key not in seen, "Duplicate Q3 membership:" + str(check_key))
        seen.add(check_key)
        i = lookup[mid]
        matches = [g for g in target_groups[tid]["groups"] if i in masks_set[g]]
        require(len(matches) <= 1 and (matches[0] if matches else "") == row["group_id"], "Q3 membership mismatch")
        require((row["included"] == "true") == bool(matches), "Q3 included flag")
        require((row["in_reference"] == "true") == (i in masks_set[target_groups[tid]["reference_group"]]), "Q3 reference membership")
    check(len(seen) == len(facts) * len(target_groups), "all Q3 target/member/reference rules independently reconstructed")
    del seen
    for ref in refs3:
        ref_ids = masks[target_groups[ref["target_id"]]["reference_group"]]
        counted = sum(facts[i]["era"] == ref["era"] and facts[i]["tournament_group"] == ref["tournament_group"] for i in ref_ids)
        check(counted == int(ref["n_reference_matches"]) and len(ref_ids) == int(ref["n_reference_total"]),
              "Q3 reference stratum:" + ref["target_id"] + ref["era"] + ref["tournament_group"])

    def q3_parts(tid, gid, sign=1, adjusted=True):
        ids = masks[gid]
        if not adjusted:
            return [part(ids, sign=sign, cell=gid + "/all", region_target=tid, region_group=gid)]
        result = []
        for ref in (r for r in refs3 if r["target_id"] == tid):
            era, kind = ref["era"], ref["tournament_group"]
            weight = Fraction(int(ref["n_reference_matches"]), int(ref["n_reference_total"]))
            result.append(part([i for i in ids if facts[i]["era"] == era and facts[i]["tournament_group"] == kind],
                               weight, sign, gid + "/" + era + "/" + kind, region_target=tid, region_group=gid,
                               era=era, tournament_group=kind))
        return result

    for row in sources["Q3"]:
        tid, cid = row["target_id"], row["contrast_id"]
        raw = q3_parts(tid, row["arm1"], 1, False) + q3_parts(tid, row["arm2"], -1, False)
        adj = q3_parts(tid, row["arm1"]) + q3_parts(tid, row["arm2"], -1)
        change = raw + [dict(p, multiplier=-p["multiplier"]) for p in adj]
        for method, comps, field, family in (("adjusted", adj, "adjusted_difference", "CORE"),
                                              ("raw", raw, "direct_difference", "AUX"),
                                              ("change", change, "direct_minus_adjusted_pp", "AUX")):
            add("Q3:" + cid + ":" + method, "Q3", family, "difference", comps,
                roots["Q3"] + "/contrast_results.csv", cid, field, row[field], row["label"] + " " + method,
                source_scale=100 if method == "change" else 1, parent_target=tid, reference=row["reference_group"])
    for row in sources["MATRIX"]:
        add("Q3:rate:" + row["group_id"], "Q3", "CONDITIONAL", "rate",
            q3_parts(row["target_id"], row["group_id"]), roots["Q3"] + "/matchup_rates.csv", row["group_id"],
            "standardized_home_win_rate", row["standardized_home_win_rate"], row["label"], source_scale=1,
            parent_target=row["target_id"], reference=row["reference_group"])

    original_coef_path = roots["Q3"] + "/match_coefficients.csv"
    inputs[original_coef_path] = sha(root / original_coef_path)
    coefficient_count = 0
    for row in rows(root / original_coef_path):
        method = "raw" if row["method"] == "direct" else "adjusted"
        tid = "Q3:" + row["contrast_id"] + ":" + method
        require(tid in vectors and abs(vectors[tid][lookup[row["match_id"]]] - float(row["coefficient"])) < 1e-14,
                "Existing Q3 coefficient mismatch:" + tid)
        coefficient_count += 1
    check(coefficient_count == 165055, "all 165055 original Q3 nonzero coefficients agree")
    check(len(catalogue) == cfg["expected_catalogue_rows"], "complete 292-target catalogue")
    for family, spec in cfg["families"].items():
        check(sum(t["family"] == family and t["target_id"] in vectors for t in catalogue) == spec["expected_supported"], "fixed supported family size:" + family)
    return dict(config=cfg, facts=facts, catalogue=catalogue, components=components_out,
                vectors=vectors, inputs=inputs, parent_outputs=parent_outputs, checks=checks, competition_context=competition)


def design_diagnostics(context):
    facts, vectors = context["facts"], context["vectors"]
    supports, teams_out, years_out = [], [], []
    components = defaultdict(list)
    for p in context["components"]:
        components[p["target_id"]].append(p)
    masks, team_masks, year_masks = {}, {}, {}
    for target in context["catalogue"]:
        tid = target["target_id"]
        if tid not in vectors:
            supports.append(dict(target_id=tid, status=target["status"], missing_cells=target["missing_cells"]))
            continue
        a = vectors[tid]
        ids = np.flatnonzero(a != 0).tolist()
        selected = [facts[i] for i in ids]
        positive_layers = [p for p in components[tid] if p["q_numerator"] and p["multiplier"]]
        team = defaultdict(lambda: dict(home_matches=0, away_matches=0, home_signed=0., away_signed=0., home_abs=0., away_abs=0.))
        years = defaultdict(lambda: dict(n_matches=0, signed_coefficient=0., absolute_coefficient=0.))
        l1 = float(np.abs(a).sum())
        for i in ids:
            r, value = facts[i], float(a[i])
            for role in ("home", "away"):
                t = team[r[role + "_team_id"]]
                t[role + "_matches"] += 1
                t[role + "_signed"] += value
                t[role + "_abs"] += abs(value)
            years[r["year"]]["n_matches"] += 1
            years[r["year"]]["signed_coefficient"] += value
            years[r["year"]]["absolute_coefficient"] += abs(value)
        for name, values in sorted(team.items()):
            teams_out.append(dict(target_id=tid, team_id=name, **values,
                                  incident_absolute_mass_share=(values["home_abs"] + values["away_abs"]) / l1 if l1 else None))
        for year, values in sorted(years.items()):
            years_out.append(dict(target_id=tid, year=year, **values))
        schedule = shared_pair_counts(selected)
        supports.append(dict(target_id=tid, status=target["status"], n_nonzero_match_coefficients=len(ids),
                             n_unique_teams=len(team), n_years=len(years),
                             min_positive_component_n=min(p["n_matches"] for p in positive_layers),
                             components_with_one_match=sum(p["n_matches"] == 1 for p in positive_layers),
                             components_with_two_matches=sum(p["n_matches"] == 2 for p in positive_layers),
                             maximum_absolute_match_coefficient=float(np.max(np.abs(a))), l1_coefficient_mass=l1,
                             l2_coefficient_squared=float(a @ a),
                             max_team_incident_mass_share=max((v["home_abs"] + v["away_abs"] for v in team.values()), default=0) / l1 if l1 else None,
                             max_year_absolute_mass_share=max((v["absolute_coefficient"] for v in years.values()), default=0) / l1 if l1 else None,
                             n_unordered_pairs=schedule["n_unordered_pairs"], max_match_dependency_degree=schedule["max_match_dependency_degree"],
                             missing_cells=""))
        masks[tid] = sum(1 << i for i in ids)
        team_masks[tid] = set(team)
        year_masks[tid] = set(years)
    overlap = [dict(target_1=a, target_2=b, shared_matches=(masks[a] & masks[b]).bit_count(),
                    shared_teams=len(team_masks[a] & team_masks[b]), shared_years=len(year_masks[a] & year_masks[b]))
               for a, b in combinations(sorted(vectors), 2)]
    global_schedule = shared_pair_counts(facts)
    by_year = defaultdict(list)
    for r in facts:
        by_year[r["year"]].append(r)
    global_schedule["same_year_nonshared_team_pairs"] = sum(s["all_match_pairs"] - s["sharing_any_team_pairs"]
                                                            for s in map(shared_pair_counts, by_year.values()))
    global_schedule["same_date_same_directed_pair_extra_records"] = sum(n - 1 for n in Counter((r["date"], r["home_team_id"], r["away_team_id"]) for r in facts).values() if n > 1)
    degree, pair_rows = defaultdict(set), []
    pair_counts = Counter(tuple(sorted((r["home_team_id"], r["away_team_id"]))) for r in facts)
    for (a, b), n in sorted(pair_counts.items()):
        degree[a].add(b)
        degree[b].add(a)
        pair_rows.append(dict(team_1=a, team_2=b, n_matches=n))
    left, sizes = set(degree), []
    while left:
        stack, found = [min(left)], set()
        while stack:
            node = stack.pop()
            if node not in found:
                found.add(node)
                stack.extend(degree[node] - found)
        left -= found
        sizes.append(len(found))
    counts = Counter(r["home_team_id"] for r in facts) + Counter(r["away_team_id"] for r in facts)
    global_schedule.update(connected_team_component_sizes=sorted(sizes, reverse=True),
                           min_team_match_appearances=min(counts.values()), max_team_match_appearances=max(counts.values()),
                           min_distinct_opponents=min(map(len, degree.values())), max_distinct_opponents=max(map(len, degree.values())),
                           max_unordered_pair_repetitions=max(pair_counts.values()),
                           repeated_unordered_pairs=sum(n > 1 for n in pair_counts.values()),
                           unordered_pair_density=len(pair_counts) / math.comb(len(counts), 2),
                           note="Schedule facts and potential dependency opportunities, not measured residual correlation or proof of a dependence assumption")
    ranks = {}
    for family in context["config"]["families"]:
        ids = [t["target_id"] for t in context["catalogue"] if t["family"] == family and t["target_id"] in vectors]
        ranks[family] = dict(n_targets=len(ids), coefficient_row_numerical_rank=numerical_row_rank(np.array([vectors[t] for t in ids])),
                             tolerance=1e-10, interpretation="Normalized coefficient algebra only; not covariance rank or independent information")
    calendar = Counter((r["year"], r["date"][:7], r["tournament_group"]) for r in facts)
    calendar_rows = [dict(year=y, month=m, tournament_group=t, n_matches=n) for (y, m, t), n in sorted(calendar.items())]
    return dict(target_support=supports, team_exposure=teams_out, year_exposure=years_out, target_overlap=overlap,
                dyad_schedule=pair_rows, calendar_counts=calendar_rows, global_schedule=global_schedule, family_ranks=ranks)
