"""Independent, read-only audit of the submitted Q3 candidate preparation run."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUN = ROOT / "outputs/logs/regions/preparation-20261026T040745Z-52745246"
PKG = ROOT / "data/external/geography_preparation/geo-prep-v1"
OUT = Path(__file__).parent


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    manifest = json.loads((RUN / "manifest.json").read_text(encoding="utf-8"))
    inputs = json.loads((RUN / "inputs_used.json").read_text(encoding="utf-8"))
    fingerprints = {str((RUN / "manifest.json").relative_to(ROOT)): digest(RUN / "manifest.json")}
    hash_checks = []
    for section, base in (("files", RUN), ("package_files", PKG)):
        for name, expected in manifest[section].items():
            path = base / name
            actual = digest(path)
            fingerprints[str(path.relative_to(ROOT))] = actual
            hash_checks.append(actual == expected)
    for item in inputs.values():
        path = ROOT / item["path"]
        actual = digest(path)
        fingerprints[str(path.relative_to(ROOT))] = actual
        hash_checks.append(actual == item["sha256"])
    check("registered_fingerprints", all(hash_checks), {"checked": len(hash_checks)})

    members = read_csv(ROOT / inputs["q2_membership"]["path"])
    clean = read_csv(ROOT / inputs["matches_clean"]["path"])
    selected = [r for r in members if r["included"] == "true"]
    by_clean = {r["match_id"]: r for r in clean}
    rel = read_csv(RUN / "match_region_relations.csv")
    rel_by_id = {r["match_id"]: r for r in rel}
    check("explicit_bool_values", {r["included"] for r in members} == {"true", "false"})
    check("clean_unique_ids", len(by_clean) == len(clean))
    check("q2_included_unique_ids", len({r["match_id"] for r in selected}) == len(selected))
    check("same_24917_ids", len(rel) == len(rel_by_id) == len(selected) == 24917
          and set(rel_by_id) == {r["match_id"] for r in selected})

    rules = read_csv(RUN / "team_geography_rules.csv")
    by_team = defaultdict(list)
    for rule in rules:
        by_team[rule["team_id"]].append(rule)
    areas = read_csv(RUN / "m49_areas.csv")
    area_by_code = {r["m49_code"]: r for r in areas}
    unit_parent = {r["project_unit_code"]: r["project_region_code"] for r in areas}
    known_units = {r["project_unit_code"] for r in areas if r["project_unit_code"]}
    check("22_unique_nonempty_fine_units", len(known_units) == 22)
    check("rule_fine_parent_consistency", all(not r["project_unit_code"]
          or unit_parent.get(r["project_unit_code"]) == r["project_region_code"] for r in rules))
    mapping_code_conflicts = []
    for rule in rules:
        code = rule["m49_code"]
        if code in area_by_code:
            area = area_by_code[code]
            if (rule["project_region_code"], rule["project_unit_code"]) != (
                    area["project_region_code"], area["project_unit_code"]):
                mapping_code_conflicts.append(rule["rule_id"])
    check("rules_match_submitted_m49_carrier_codes", not mapping_code_conflicts, mapping_code_conflicts)

    per_match_errors = []
    role_counts = {role: Counter() for role in ("home", "away")}
    for member in selected:
        match = by_clean[member["match_id"]]
        row = rel_by_id[member["match_id"]]
        expected = {k: member[k] for k in ("data_version", "identity_version", "sample_id")}
        expected.update(date=match["date"], era=member["analysis_era_id"],
                        tournament_group=member["tournament_group"])
        for role in ("home", "away"):
            tid = match[f"{role}_team_id"]
            role_counts[role][tid] += 1
            applicable = [r for r in by_team[tid] if r["date_start"] <= match["date"] <= r["date_end"]]
            if len(applicable) != 1:
                per_match_errors.append({"match_id": member["match_id"], "role": role, "rule_count": len(applicable)})
                continue
            rule = applicable[0]
            expected.update({f"{role}_team_id": tid, f"{role}_rule_id": rule["rule_id"],
                             f"{role}_region": rule["project_region_code"],
                             f"{role}_unit": rule["project_unit_code"], f"{role}_status": rule["status"]})
        hr, ar = expected.get("home_region", ""), expected.get("away_region", "")
        hu, au = expected.get("home_unit", ""), expected.get("away_unit", "")
        if not hr or not ar:
            relation = "unknown_region"
        elif hr != ar:
            relation = "cross_region"
        elif not hu or not au:
            relation = "unknown_same_region"
        else:
            relation = "same_unit" if hu == au else "same_region_diff_unit"
        expected.update(relation=relation, direction=f"{hr}>{ar}" if hr and ar else "",
                        A_usable=str(bool(hr)).lower(), C_usable=str(bool(hu)).lower(),
                        B_usable=str(relation in {"cross_region", "same_unit", "same_region_diff_unit"}).lower())
        mismatched = [k for k, value in expected.items() if row[k] != value]
        if match["date"] != member["date"] or match["tournament_group"] != member["tournament_group"]:
            mismatched.append("input_join")
        if match["source_record_id"] != member["source_record_id"]:
            mismatched.append("input_source_record")
        if match["is_neutral"] != "false" or not "1980-01-01" <= match["date"] <= "2024-12-31":
            mismatched.append("parent_scope")
        if mismatched:
            per_match_errors.append({"match_id": member["match_id"], "fields": mismatched})
    check("all_match_assignments_independently_rebuilt", not per_match_errors,
          {"checked": len(selected), "errors": per_match_errors[:10]})
    check("team_inventory_counts", all(
        int(r["home_matches"]) == role_counts["home"][r["team_id"]]
        and int(r["away_matches"]) == role_counts["away"][r["team_id"]]
        and int(r["total_matches"]) == role_counts["home"][r["team_id"]] + role_counts["away"][r["team_id"]]
        for r in read_csv(RUN / "team_inventory.csv")))

    zero_cells = {}
    definitions = [
        ("counts_home_region_era_tournament.csv", ("home_region", "era", "tournament_group")),
        ("counts_home_unit_era_tournament.csv", ("home_unit", "era", "tournament_group")),
        ("counts_relation_era_tournament.csv", ("home_region", "relation", "era", "tournament_group")),
        ("counts_direction_matrix.csv", ("home_region", "away_region")),
    ]
    for name, keys in definitions:
        def key(row):
            return tuple((row[k] or "UNKNOWN") if k in {"home_region", "away_region", "home_unit"}
                         else row[k] for k in keys)
        actual = Counter(key(r) for r in rel)
        table = read_csv(RUN / name)
        observed = {tuple(r[k] for k in keys): int(r["matches"]) for r in table}
        check(name + ":cellwise_counts", len(table) == len(observed)
              and all(observed.get(k) == n for k, n in actual.items())
              and all(n == actual.get(k, 0) for k, n in observed.items()))
        if "n_teams" in table[0]:
            team_sets = defaultdict(set)
            for r in rel:
                team_sets[key(r)].add(r["home_team_id"])
            check(name + ":home_team_counts", all(int(r["n_teams"]) == len(team_sets[tuple(r[k] for k in keys)]) for r in table))
        zero_cells[name] = {
            "all_zero_cells": sum(int(r["matches"]) == 0 for r in table),
            "known_category_zero_cells": [dict(zip(keys, k)) for k, n in observed.items()
                                          if n == 0 and "UNKNOWN" not in k],
        }
    unknown = read_csv(RUN / "unknown_distribution.csv")
    check("unknown_distribution_cellwise", all(
        int(r["usable"]) == sum(x["era"] == r["era"] and x["tournament_group"] == r["tournament_group"]
                                and x[r["target"] + "_usable"] == "true" for x in rel)
        and int(r["unusable"]) == sum(x["era"] == r["era"] and x["tournament_group"] == r["tournament_group"]
                                     and x[r["target"] + "_usable"] == "false" for x in rel) for r in unknown))

    dictionary = read_csv(PKG / "region_dictionary.csv")
    missing_raw_parents = [r["area_code"] for r in dictionary if r["original_level"] in {"subregion", "intermediate"}
                           and not r["parent_code"]]
    known_refs = {r["source_id"] for r in read_csv(PKG / "sources.csv")}
    check("rule_source_ids_resolve", all(r["source_id"] in known_refs for r in rules))
    rel_cells = Counter((r["home_region"], r["relation"], r["era"], r["tournament_group"]) for r in rel)
    layers = [(e, t) for e in ("1980s", "1990s", "2000s", "2010s", "2020_2024")
              for t in ("friendly", "non_friendly")]
    relation_support = {reg: {relation: [{"era": e, "tournament_group": t}
                        for e, t in layers if rel_cells[(reg, relation, e, t)] == 0]
                        for relation in ("cross_region", "same_unit", "same_region_diff_unit")}
                        for reg in ("002", "019", "142", "150", "009")}
    output = {
        "schema_version": "q3-preparation-independent-review-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "executor": "Codex (AI)",
        "source_run": str(RUN.relative_to(ROOT)), "scope": "Arithmetic and interface audit plus code/provenance review; no regional outcomes or inference",
        "checks": checks, "check_count": len(checks),
        "all_performed_arithmetic_checks_passed": all(c["passed"] for c in checks),
        "source_fingerprints": fingerprints,
        "audit_script_sha256": digest(Path(__file__)),
        "target_counts": {k: sum(r[k + "_usable"] == "true" for r in rel) for k in "ABC"},
        "known_and_unknown_zero_cells": zero_cells,
        "relation_support_zero_cells": relation_support,
        "raw_dictionary_nodes_missing_parents": missing_raw_parents,
        "findings": [
            "reference_support.csv checks pooled reference cells, not positive-reference support in each comparison arm",
            "candidate B uses vague relation-versus-rest; exact arms, unknown exclusion and subtraction are not machine-readable; C is similarly vague",
            "historical carrier codes and Russian cutoff point only to current M49; entity facts, project assumptions and supporting records require separation",
            "raw dictionary parent_code is blank for subregion/intermediate nodes",
            "coverage tables count home teams only; away team counts and per-cell home/away composition not delivered",
            "handoff claims six region zero cells as absent schedule, but all six are UNKNOWN category cells",
            "micro direction check compares literal strings; full-period continuity and adverse-input checks incomplete",
            "script writes into fixed package version; source and code state need reproducible run snapshots before revisions",
        ],
        "adoption_status": "needs_targeted_revision_not_accepted_as_complete",
        "production_outputs_modified": False, "regional_outcomes_computed": False,
        "human_review": "not_performed",
        "environment": "Default tool access denied for clean directory and venv launch; approved normal-local execution read original clean SHA and Python 3.14.8 successfully. No deletion inferred.",
    }
    (OUT / "review.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"arithmetic_checks": len(checks), "arithmetic_passed": output["all_performed_arithmetic_checks_passed"],
                      "hash_checks": len(hash_checks), "target_counts": output["target_counts"],
                      "raw_parent_gaps": len(missing_raw_parents), "relation_support_zero_cells": relation_support,
                      "review": str((OUT / "review.json").relative_to(ROOT))}, ensure_ascii=True))


if __name__ == "__main__":
    main()
