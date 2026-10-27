"""Q3 worked examples: multi-group references, missing support and safe publication."""
import copy
import itertools
import json

import pytest

from scripts.analyze_regions import run_analysis
from src.regions.describe import build_counts
from src.regions.export import csv_content, publish, scalar, verify_run
from src.regions.groups import build_groups
from src.regions.io import RegionError, era_for, json_bytes, project_path, read_rows, sha, strict_bool
from src.regions.standardize import build_adjustments, weighted_rate


def example():
    config = dict(groups={"REF": dict(label="all", eligibility=None, home_regions=[], home_units=[], relations=[])},
                  analysis_targets={}, comparisons=[], strata=dict(eras=[dict(id="era", start="1980-01-01", end="1989-12-31")],
                                                                   tournament_groups=["friendly", "non_friendly"]))
    facts = []
    # All four groups are computed. A/B have different schedules; all share REF.
    patterns = {"A": [(8, 4), (2, 2)], "B": [(2, 0), (8, 4)],
                "C": [(5, 2), (5, 3)], "D": [(5, 0), (5, 0)]}
    for group, items in patterns.items():
        config["groups"][group] = dict(label=group, eligibility=None, home_regions=[], home_units=[group], relations=[])
        for kind, (n, wins) in zip(config["strata"]["tournament_groups"], items):
            for i in range(n):
                facts.append(dict(match_id=f"{group}-{kind}-{i}", era="era", tournament_group=kind,
                                  home_unit=group, home_region="150", away_region="150", away_unit="X",
                                  home_team_id=group, away_team_id="X", home_win=int(i < wins),
                                  outcome="home" if i < wins else "draw", relation="same_region_diff_unit"))
    config["analysis_targets"]["MULTI"] = dict(groups=list(patterns), reference_group="REF")
    for a, b in itertools.combinations(patterns, 2):
        config["comparisons"].append(dict(id=a+b, target_id="MULTI", arm1=a, arm2=b, label=a+" minus "+b,
                                          reference_group="REF", parent_study="EUROPE"))
    labels = {g: g for g in [*patterns, "X"]}
    return config, facts, labels


def calculate(config, facts, labels):
    membership, groups, refs = build_groups(facts, config)
    tables = dict(analysis_matches=facts, analysis_membership=membership, **build_counts(groups, config, labels))
    return build_adjustments(tables, groups, refs, config)


def test_four_groups_use_one_reference_and_six_contrasts():
    config, facts, labels = example()
    tables = calculate(config, facts, labels)
    summary = {r["group_id"]: r for r in tables["group_summary"]}
    assert len(summary) == 4 and len(tables["contrast_results"]) == 6
    assert len(tables["analysis_membership"]) == len(facts) == 40
    assert [r["weight"] for r in tables["reference_weights"]] == [.5, .5]
    assert summary["A"]["home_win_rate"] == .6
    assert summary["A"]["standardized_home_win_rate"] == .75
    assert summary["B"]["standardized_home_win_rate"] == .25
    assert summary["C"]["standardized_home_win_rate"] == .5
    assert summary["D"]["standardized_home_win_rate"] == 0
    contrasts = {r["contrast_id"]: r for r in tables["contrast_results"]}
    assert contrasts["AB"]["adjusted_difference"] == .5
    assert contrasts["AB"]["adjusted_difference"] + contrasts["BC"]["adjusted_difference"] == contrasts["AC"]["adjusted_difference"]


def test_one_group_missing_cell_does_not_invalidate_other_pairs():
    c, facts, labels = example()
    facts = [r for r in facts if not (r["home_unit"] == "D" and r["tournament_group"] == "friendly")]
    tables = calculate(c, facts, labels)
    for row in tables["contrast_results"]:
        assert (row["adjusted_difference"] is None) == ("D" in (row["arm1"], row["arm2"]))
    assert all(r["contrast_id"] not in {"AD", "BD", "CD"} or r["method"] == "direct"
               for r in tables["match_coefficients"])


def test_reference_includes_groups_outside_compared_pair():
    c, facts, labels = example()
    c["analysis_targets"]["MULTI"]["groups"] = ["A", "B"]
    c["comparisons"] = [c["comparisons"][0]]
    tables = calculate(c, facts, labels)
    assert sum(r["in_reference"] for r in tables["analysis_membership"]) == 40
    assert sum(r["included"] for r in tables["analysis_membership"]) == 20
    assert sum(r["reason"] == "reference_only" for r in tables["analysis_membership"]) == 20


def test_zero_weight_skips_undefined_rate_but_positive_weight_rejects():
    rows = {("a", "f"): dict(n_matches=2, home_win_rate=.5), ("b", "f"): dict(n_matches=0, home_win_rate=None)}
    assert weighted_rate(rows, {("a", "f"): 1, ("b", "f"): 0}) == (.5, "ok", "")
    assert weighted_rate(rows, {("a", "f"): .5, ("b", "f"): .5})[0] is None


def test_zero_wins_and_no_matches_are_distinct():
    c, facts, labels = example()
    tables = calculate(c, [r for r in facts if r["home_unit"] != "D"], labels)
    d = next(r for r in tables["group_summary"] if r["group_id"] == "D")
    assert d["n_matches"] == 0 and d["home_win_rate"] is None
    tables = calculate(c, facts, labels)
    d = next(r for r in tables["group_summary"] if r["group_id"] == "D")
    assert d["n_matches"] == 10 and d["home_win_rate"] == 0


def test_coefficients_reconstruct_each_pair_from_scores():
    c, facts, labels = example()
    tables = calculate(c, facts, labels)
    wins = {r["match_id"]: r["home_win"] for r in facts}
    for contrast in tables["contrast_results"]:
        for method, field in (("direct", "direct_difference"), ("standardized", "adjusted_difference")):
            rows = [r for r in tables["match_coefficients"] if r["contrast_id"] == contrast["contrast_id"] and r["method"] == method]
            assert sum(r["coefficient"] * wins[r["match_id"]] for r in rows) == pytest.approx(contrast[field], abs=1e-12)
            assert sum(r["coefficient"] for r in rows) == pytest.approx(0, abs=1e-12)


def test_overlapping_multigroup_definitions_fail():
    c, facts, _ = example()
    c["groups"]["B"] = copy.deepcopy(c["groups"]["A"])
    with pytest.raises(RegionError, match="Overlapping"):
        build_groups(facts, c)


@pytest.mark.parametrize("value", ["True", "FALSE", " true", "", "0"])
def test_boolean_contract_rejects_ambiguous_values(value):
    with pytest.raises(RegionError):
        strict_bool(value)


def test_paths_are_portable_and_cannot_escape_project(tmp_path):
    assert project_path(tmp_path, r"data\file.csv") == tmp_path / "data/file.csv"
    with pytest.raises(RegionError):
        project_path(tmp_path, "../outside")


def test_date_boundary_is_inclusive_and_requires_unique_era():
    c, _, _ = example()
    assert era_for("1980-01-01", c) == era_for("1989-12-31", c) == "era"
    with pytest.raises(RegionError):
        era_for("1990-01-01", c)


def test_duplicate_input_ids_are_rejected(tmp_path):
    p = tmp_path / "rows.csv"
    p.write_text("match_id\na\na\n", encoding="utf-8")
    with pytest.raises(RegionError):
        read_rows(p, "match_id")


def test_csv_bom_lf_and_stable_order():
    rows = [dict(target_id="B", match_id="2", group_id="A", included=True, in_reference=True, reason="included"),
            dict(target_id="A", match_id="1", group_id="", included=False, in_reference=True, reason="reference_only")]
    data = csv_content("analysis_membership", rows, "test")
    assert data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data
    assert csv_content("analysis_membership", rows[::-1], "test") == data
    assert b"false" in data and scalar(1/3) == format(1/3, ".17g")
    with pytest.raises(RegionError):
        scalar(float("nan"))


def test_publish_collision_preserves_existing_files(tmp_path):
    (tmp_path / "existing.txt").write_bytes(b"keep")
    run = tmp_path / "run"
    run.mkdir()
    with pytest.raises(RegionError):
        publish(tmp_path, run, {"new.txt": b"new", "existing.txt": b"changed"})
    assert (tmp_path / "existing.txt").read_bytes() == b"keep"
    assert not (tmp_path / "new.txt").exists()


def test_failed_run_records_error_without_success_manifest(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_analysis(root=tmp_path)
    runs = list((tmp_path / "outputs/logs/regions").iterdir())
    assert len(runs) == 1 and (runs[0] / "failure_report.json").is_file()
    assert not (runs[0] / "run_manifest.json").exists()


def test_verify_run_detects_modified_output(tmp_path):
    p = tmp_path / "output.txt"
    p.write_bytes(b"original")
    m = dict(status="success", analysis_id="test", inputs={}, code={}, run_artifacts={}, outputs={"output.txt": sha(p)})
    (tmp_path / "run.json").write_bytes(json_bytes(m))
    assert verify_run(tmp_path, "run.json")["fingerprint_checks"] == 1
    p.write_bytes(b"changed")
    with pytest.raises(RegionError):
        verify_run(tmp_path, "run.json")
