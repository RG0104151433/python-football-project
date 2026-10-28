"""Independent standard-library audit of Q4 design recipes; imports no analysis code."""
import argparse
from collections import Counter, defaultdict
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select_component_indices(facts, ids, recipe):
    if recipe.get("scope") == "rolling":
        begin, end = map(int, recipe["period_id"].split("_"))
        ids = [i for i in ids if begin <= int(facts[i]["year"]) <= end]
    elif recipe.get("scope") == "era":
        ids = [i for i in ids if facts[i]["era"] == recipe["period_id"]]
    return [i for i in ids if all(not recipe.get(k) or facts[i][k] == recipe[k] for k in ("era", "year", "tournament_group"))]


def audit(manifest_path, output_path, root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root / manifest_path).read_text(encoding="utf-8"))
    checks = Counter()

    def check(ok, topic, detail=""):
        if not ok:
            raise ValueError(topic + ":" + detail)
        checks[topic] += 1

    for group in ("inputs", "code", "outputs", "parent_outputs_unchanged"):
        for p, expected in manifest[group].items():
            check(digest(root / p) == expected, "sha_" + group, p)
    directory = next((root / p).parent for p in manifest["outputs"] if p.endswith("/target_catalogue.csv"))
    fact_path = next(p for p in manifest["inputs"] if "/regions/" in p and p.endswith("/analysis_matches.csv"))
    facts = sorted(read_rows(root / fact_path), key=lambda r: r["match_id"])
    fact_by_id = {r["match_id"]: i for i, r in enumerate(facts)}
    membership = defaultdict(set)
    with (root / fact_path).with_name("analysis_membership.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["included"] == "true":
                membership[row["target_id"], row["group_id"]].add(fact_by_id[row["match_id"]])
    recipes = defaultdict(list)
    for row in read_rows(directory / "coefficient_recipes.csv"):
        recipes[row["target_id"]].append(row)
    catalogue = read_rows(directory / "target_catalogue.csv")
    supports = {r["target_id"]: r for r in read_rows(directory / "target_support.csv")}
    team_exposure, year_exposure = defaultdict(list), defaultdict(list)
    for r in read_rows(directory / "team_exposure.csv"):
        team_exposure[r["target_id"]].append(r)
    for r in read_rows(directory / "year_exposure.csv"):
        year_exposure[r["target_id"]].append(r)
    bits, team_sets, year_sets = {}, {}, {}
    family = Counter()
    for target in catalogue:
        tid = target["target_id"]
        total, missing, combined = Fraction(0), False, defaultdict(float)
        for recipe in recipes[tid]:
            if recipe.get("region_group"):
                ids = membership[recipe["region_target"], recipe["region_group"]]
            else:
                ids = range(len(facts))
            ids = select_component_indices(facts, ids, recipe)
            n, wins = len(ids), sum(int(facts[i]["home_win"]) for i in ids)
            check(n == int(recipe["n_matches"]) and wins == int(recipe["n_home_wins"]), "component_members_and_counts", tid)
            q = Fraction(int(recipe["q_numerator"]), int(recipe["q_denominator"]))
            sign = int(recipe["multiplier"])
            if q and sign:
                if not n:
                    missing = True
                else:
                    exact_coefficient = sign * q / n
                    check(abs(float(exact_coefficient) - float(recipe["coefficient"])) < 1e-15, "component_coefficient", tid)
                    total += exact_coefficient * wins
                    for i in ids:
                        combined[i] += float(exact_coefficient)
        check((target["status"] == "supported_point_target") == (not missing), "target_support_state", tid)
        if missing:
            check(target["estimate_probability"] == "", "unsupported_no_estimate", tid)
            continue
        check(abs(float(total) - float(target["estimate_probability"])) < 1e-12, "exact_fraction_estimate", tid)
        combined = {i: a for i, a in combined.items() if a != 0}
        check(abs(sum(a * int(facts[i]["home_win"]) for i, a in combined.items()) - float(total)) < 1e-11, "match_coefficient_estimate", tid)
        check(abs(sum(combined.values()) - (1 if target["kind"] == "rate" else 0)) < 1e-11, "merged_mass_and_scale", tid)
        check(len(combined) == int(supports[tid]["n_nonzero_match_coefficients"]), "merged_coefficient_support", tid)
        l1 = sum(abs(a) for a in combined.values())
        check(abs(max(map(abs, combined.values())) - float(supports[tid]["maximum_absolute_match_coefficient"])) < 1e-12
              and abs(sum(a*a for a in combined.values()) - float(supports[tid]["l2_coefficient_squared"])) < 1e-12,
              "single_match_and_squared_weight", tid)
        exposures = team_exposure[tid]
        check(all(sum(int(r[role + "_matches"]) for r in exposures) == len(combined)
                  and abs(sum(float(r[role + "_abs"]) for r in exposures) - l1) < 1e-10 for role in ("home", "away"))
              and abs(max(float(r["incident_absolute_mass_share"]) for r in exposures)
                      - float(supports[tid]["max_team_incident_mass_share"])) < 1e-12,
              "both_role_exposure_mass", tid)
        yearly = year_exposure[tid]
        check(sum(int(r["n_matches"]) for r in yearly) == len(combined)
              and abs(sum(float(r["absolute_coefficient"]) for r in yearly) - l1) < 1e-10
              and abs(max(float(r["absolute_coefficient"]) for r in yearly) / l1
                      - float(supports[tid]["max_year_absolute_mass_share"])) < 1e-12,
              "year_exposure_mass", tid)
        family[target["family"]] += 1
        bits[tid] = sum(1 << i for i in combined)
        team_sets[tid] = {facts[i][role + "_team_id"] for i in combined for role in ("home", "away")}
        year_sets[tid] = {facts[i]["year"] for i in combined}
    check(len(catalogue) == 292 and len(bits) == 198, "full_catalogue_and_supported_count")
    check(dict(family) == dict(manifest["summary"]["families"]), "four_family_counts")
    for row in read_rows(directory / "target_overlap.csv"):
        a, b = row["target_1"], row["target_2"]
        check(int(row["shared_matches"]) == (bits[a] & bits[b]).bit_count()
              and int(row["shared_teams"]) == len(team_sets[a] & team_sets[b])
              and int(row["shared_years"]) == len(year_sets[a] & year_sets[b]), "target_overlap", a + "/" + b)
    # Independently count each match's neighbours with bit-set unions; no count-of-counts identity.
    team_bits, year_bits = defaultdict(int), defaultdict(int)
    for i, row in enumerate(facts):
        for role in ("home", "away"):
            team_bits[row[role + "_team_id"]] |= 1 << i
        year_bits[row["year"]] |= 1 << i
    degree_sum = same_year_shared_twice = max_degree = 0
    for i, row in enumerate(facts):
        neighbours = (team_bits[row["home_team_id"]] | team_bits[row["away_team_id"]]) & ~(1 << i)
        degree = neighbours.bit_count()
        degree_sum += degree
        max_degree = max(max_degree, degree)
        same_year_shared_twice += (neighbours & year_bits[row["year"]]).bit_count()
    schedule = manifest["summary"]["global_schedule"]
    check(degree_sum // 2 == schedule["sharing_any_team_pairs"] and degree_sum % 2 == 0, "global_shared_team_pairs")
    check(max_degree == schedule["max_match_dependency_degree"], "global_dependency_degree")
    same_year_all = sum(n * (n - 1) // 2 for n in Counter(r["year"] for r in facts).values())
    check(same_year_all - same_year_shared_twice // 2 == schedule["same_year_nonshared_team_pairs"], "same_year_nonshared_pairs")
    raw_path = "data/raw/international_results/results.csv"
    raw = read_rows(root / raw_path)
    for row in read_rows(directory / "competition_context.csv"):
        number = int(row["source_record_id"].rsplit(":", 1)[1])
        check(row["tournament_name"] == raw[number - 1]["tournament"].strip()
              and row["edition_id"] == row["round_id"] == "", "competition_label_provenance", row["match_id"])
    result = dict(status="passed_design_only", analysis_id=manifest["analysis_id"],
                  n_checks=sum(checks.values()), checks_by_topic=dict(checks),
                  audited_manifest=manifest_path, audited_manifest_sha256=digest(root / manifest_path),
                  auditor_sha256=digest(Path(__file__)), imports_analysis_code=False,
                  covariance_estimated=False, simulation_run=False, formal_inference="not_run", human_review="not_performed")
    path = (root / output_path).resolve()
    if not path.is_relative_to(root) or path.exists():
        raise ValueError("Audit output must be a new file inside repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    audit(args.manifest, args.output)
