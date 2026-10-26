"""Audit design inputs and source retention; never calculate project win rates."""
import csv
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").is_file())
OUT = Path(__file__).resolve().parent / "review.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config_path = ROOT / "config/regions_study.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    run = ROOT / config["grouping"]["adopted_run"]
    relation_path = run / "match_region_relations.csv"
    with relation_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len({r["match_id"] for r in rows}) == 24917
    assert all(r["data_version"] == config["scope"]["data_version"] for r in rows)
    assert all(r["identity_version"] == config["scope"]["identity_version"] for r in rows)
    assert all(r["sample_id"] == config["scope"]["sample_id"] for r in rows)
    cells = [(e["id"], t) for e in config["strata"]["eras"]
             for t in config["strata"]["tournament_groups"]]
    assert len(cells) == 10
    counts, masks = {}, {}
    for gid, spec in config["groups"].items():
        selected = []
        for row in rows:
            eligibility = spec["eligibility"]
            if eligibility and row[f"{eligibility}_usable"] != "true":
                continue
            if spec["home_regions"] and row["home_region"] not in spec["home_regions"]:
                continue
            if spec["home_units"] and row["home_unit"] not in spec["home_units"]:
                continue
            if spec["relations"] and row["relation"] not in spec["relations"]:
                continue
            selected.append(row)
        masks[gid] = {r["match_id"] for r in selected}
        counts[gid] = Counter((r["era"], r["tournament_group"]) for r in selected)
        assert all(cell in cells for cell in counts[gid])
    old = json.loads((run.parent / "scope_counts.json").read_text(encoding="utf-8"))
    assert {g: len(v) for g, v in masks.items()} == old["group_counts"]
    unsupported = {}
    for target in config["comparisons"]:
        a, b, ref = (target[x] for x in ["arm1", "arm2", "reference_group"])
        assert not masks[a] & masks[b]
        assert masks[a] <= masks[ref] and masks[b] <= masks[ref]
        assert sum(counts[ref].values()) > 0
        missing = [dict(era=e, tournament_group=t, reference=counts[ref][e, t],
                        arm1=counts[a][e, t], arm2=counts[b][e, t])
                   for e, t in cells if counts[ref][e, t] > 0
                   and (counts[a][e, t] == 0 or counts[b][e, t] == 0)]
        unsupported[target["id"]] = missing
        if target["role"] == "study_subanalysis":
            assert not missing
    assert set(k for k, v in unsupported.items() if v) == {"B_SA"}
    assert len(config["studies"]) == 4
    assert len([c for c in config["comparisons"] if c["role"] == "study_subanalysis"]) == 6

    # Artificial integers only: no project scores are read.
    q = [Fraction(2, 5), Fraction(3, 5)]
    na, wa, nb, wb = [10, 20], [6, 8], [5, 10], [2, 6]
    pa = sum(q[i] * Fraction(wa[i], na[i]) for i in range(2))
    pb = sum(q[i] * Fraction(wb[i], nb[i]) for i in range(2))
    contributions = [q[i] * (Fraction(wa[i], na[i]) - Fraction(wb[i], nb[i]))
                     for i in range(2)]
    assert sum(contributions) == pa - pb
    coefficients = (sum(q[i] / na[i] * wa[i] for i in range(2))
                    - sum(q[i] / nb[i] * wb[i] for i in range(2)))
    assert coefficients == pa - pb
    assert sum(q[i] / na[i] * na[i] for i in range(2)) == 1
    assert sum(-q[i] / nb[i] * nb[i] for i in range(2)) == -1
    zero_weight_terms = [(Fraction(1), 1, 2), (Fraction(0), 0, 0)]
    assert sum(weight * Fraction(w, n) for weight, w, n in zero_weight_terms if weight) == Fraction(1, 2)

    report = json.loads(OUT.read_text(encoding="utf-8"))
    for item in report["html_files"]:
        path = ROOT / item["path"]
        assert sha(path) == item["sha256"]
        if item["records"]:
            assert any(r.get("sha256") == item["sha256"] for r in item["records"])
    report["design_checks"] = dict(
        group_counts_rebuilt=True, group_count=len(masks), parent_matches=24917,
        current_group_counts={g: len(v) for g, v in masks.items()},
        common_reference_arm_disjointness_and_containment=True,
        unsupported_positive_layers=unsupported,
        artificial_exact_fraction_identities_passed=True,
        project_scores_read=False, formal_analysis_implemented=False,
        required_before_implementation=[],
        deferred=["question_4_inference_and_sensitivity", "question_5_strength",
                  "human_replication", "final_HTML_and_paper"],
    )
    inputs = [config_path, relation_path, ROOT / "研究/03_地域差异/脚本设计.md",
              ROOT / "data/external/geography_sources/m49-20261026/sources.csv",
              Path(__file__).resolve()]
    report["design_input_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(json.dumps(report["design_checks"], ensure_ascii=True))


if __name__ == "__main__":
    main()
