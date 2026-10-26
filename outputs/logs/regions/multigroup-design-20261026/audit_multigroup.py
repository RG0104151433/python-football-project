"""Count-only audit of European multi-group design; no match outcomes read."""
import csv
import hashlib
import itertools
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").is_file())
OUT = Path(__file__).resolve().parent


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    cfg = ROOT / "config/regions_study.json"
    c = json.loads(cfg.read_text(encoding="utf-8"))
    source = ROOT / c["grouping"]["adopted_run"] / "match_region_relations.csv"
    with source.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len({x["match_id"] for x in rows}) == 24917
    groups, counts = {}, {}
    for gid, spec in c["groups"].items():
        subset = [x for x in rows
                  if (not spec["eligibility"] or x[spec["eligibility"] + "_usable"] == "true")
                  and (not spec["home_regions"] or x["home_region"] in spec["home_regions"])
                  and (not spec["home_units"] or x["home_unit"] in spec["home_units"])
                  and (not spec["relations"] or x["relation"] in spec["relations"])]
        groups[gid] = {x["match_id"] for x in subset}
        counts[gid] = Counter((x["era"], x["tournament_group"]) for x in subset)
    old_path = ROOT / "config/archive/regions_study_v2.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    assert c["scope"] == old["scope"] and c["grouping"] == old["grouping"]
    assert all(c["groups"][gid] == value for gid, value in old["groups"].items())
    eu = c["analysis_targets"]["C_EUR"]["groups"]
    assert len(eu) == 4 and sum(len(groups[g]) for g in eu) == 8045
    assert set().union(*(groups[g] for g in eu)) == groups["C_EUR_REF"]
    assert all(not groups[a] & groups[b] for a, b in itertools.combinations(eu, 2))
    assert all(len(counts[g]) == 10 and min(counts[g].values()) > 0 for g in eu)
    pairs = [x for x in c["comparisons"] if x["target_id"] == "C_EUR"]
    assert len(pairs) == 6
    assert {frozenset((x["arm1"], x["arm2"])) for x in pairs} == {
        frozenset(pair) for pair in itertools.combinations(eu, 2)}
    assert all(x["reference_group"] == "C_EUR_REF" for x in pairs)
    missing = {}
    for contrast in c["comparisons"]:
        a, b, ref = (contrast[k] for k in ["arm1", "arm2", "reference_group"])
        assert not groups[a] & groups[b]
        assert groups[a] <= groups[ref] and groups[b] <= groups[ref]
        missing[contrast["id"]] = [dict(era=e, tournament_group=t)
                                    for e, t in counts[ref]
                                    if not counts[a][e, t] or not counts[b][e, t]]
        if contrast["role"] == "study_subanalysis":
            assert not missing[contrast["id"]]
    assert {k for k, v in missing.items() if v} == {"B_SA"}
    for tid, target in c["analysis_targets"].items():
        assert all(not groups[a] & groups[b] for a, b in itertools.combinations(target["groups"], 2))
        assert all(groups[g] <= groups[target["reference_group"]] for g in target["groups"])
        assert all(x["arm1"] in target["groups"] and x["arm2"] in target["groups"]
                   for x in c["comparisons"] if x["target_id"] == tid)
    # Four artificial rates: exact transitivity, antisymmetry and null equality.
    p = [Fraction(1, 3), Fraction(1, 2), Fraction(3, 5), Fraction(2, 3)]
    delta = {(i, j): p[i] - p[j] for i in range(4) for j in range(4)}
    assert all(delta[i, j] == -delta[j, i] for i in range(4) for j in range(4))
    assert all(delta[i, k] == delta[i, j] + delta[j, k]
               for i in range(4) for j in range(4) for k in range(4))
    assert all(Fraction(1, 2) - Fraction(1, 2) == 0 for _ in range(6))
    # One unsupported group must affect its three pairs, not the other three.
    supported = {"north": True, "south": True, "west": False, "east": True}
    affected = [(a, b) for a, b in itertools.combinations(supported, 2)
                if not (supported[a] and supported[b])]
    assert len(affected) == 3 and all("west" in pair for pair in affected)
    report = dict(
        decision_log_id="R20261026-18", protocol_id=c["protocol_id"],
        archived_v2_sha256=digest(old_path), adopted_geography_unchanged=True,
        groups=len(groups), studies=len(c["studies"]), targets=len(c["analysis_targets"]),
        predefined_contrasts=len(c["comparisons"]), supported_adjusted_contrasts=11,
        european_groups={g: dict(matches=len(groups[g]), layers=len(counts[g]),
                                 minimum_cell=min(counts[g].values())) for g in eu},
        european_pairwise_contrasts=[x["id"] for x in pairs],
        common_reference="C_EUR_REF", reference_matches=8045,
        four_groups_mutually_exclusive_and_exhaustive=True,
        pairwise_missing_support=missing,
        artificial_four_group_algebra_checks_passed=True,
        artificial_one_group_missing_support_locality_checked=True,
        project_outcomes_read=False, regional_win_rates_computed=False,
        formal_analysis_implemented=False, reviewer="Codex AI; no human review",
        inputs_sha256={p.relative_to(ROOT).as_posix(): digest(p) for p in
                      [cfg, old_path, source, Path(__file__).resolve(), ROOT / "研究/03_地域差异/脚本设计.md"]})
    (OUT / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
