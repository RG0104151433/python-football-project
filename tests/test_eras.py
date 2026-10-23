"""Analysis contracts on independent examples; no tests mutate the real snapshot."""
import copy
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.analyze_eras import run_analysis
from src.clean import run_cleaning
from src.data_contract import SCHEMAS, PrepError, atomic_bytes, csv_bytes, file_hash, paths, write_json
from src.eras.checks import run_sensitivity, validate_tables
from src.eras.data import boolean, load_analysis_config, select_samples
from src.eras.reporting import publish_outputs, table_artifacts, verify_run
from src.eras.standardize import build_reference, build_standardization, era_rates
from src.eras.statistics import build_statistics
from src.snapshot import register_snapshot

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    return json.loads((PROJECT / "config" / "eras.json").read_text(encoding="utf-8"))


def record(day, number, *, group="friendly", outcome="home", neutral=False, **changes):
    result = dict(match_id=f"match:{number}", source_record_id=f"source:{number}", date=day,
                  year=int(day[:4]), eligible_venue_analysis=True, eligible_tournament_analysis=group != "unknown",
                  is_neutral=neutral, tournament_group=group, outcome=outcome,
                  home_win=int(outcome == "home"), goal_difference=1 if outcome == "home" else -1 if outcome == "away" else 0,
                  home_team_id="A", away_team_id="B")
    result.update(changes)
    return result


def toy_rows():
    # Independent worked example: 58/100 -> 57/100, standardized 55% -> 60%.
    rows = []
    for year, group, n, wins in ((1980, "friendly", 80, 48), (1980, "non_friendly", 20, 10),
                                  (2010, "friendly", 20, 13), (2010, "non_friendly", 80, 44)):
        for i in range(n):
            rows.append(record(f"{year}-01-01", len(rows), group=group, outcome="home" if i < wins else "draw"))
    return rows


def test_venue_eligibility_does_not_admit_neutral_matches_and_unknown_classification_is_tracked(config):
    rows = [record("1980-01-01", 1), record("1980-01-02", 2, neutral=True),
            record("1980-01-03", 3, group="unknown"), record("1979-12-31", 4),
            record("2024-12-31", 5), record("2025-01-01", 6)]
    samples, membership = select_samples(rows, config)
    assert [r["match_id"] for r in samples["base_venue"]] == ["match:1", "match:3", "match:5"]
    assert [r["match_id"] for r in samples["classified_venue"]] == ["match:1", "match:5"]
    assert membership[2]["primary_exclusion_reason"] == "tournament_ineligible_or_unknown"
    assert boolean("false") is False
    with pytest.raises(PrepError):
        boolean("FALSE")


def test_independent_worked_example_and_pp_units(config):
    rows = toy_rows()
    tables, refs = build_standardization(rows, config)
    assert refs[0]["weight_friendly"] == .5
    rates = era_rates(rows, config, .5)
    assert rates["1980s"]["observed_rate"] == .58
    assert rates["2010s"]["observed_rate"] == .57
    assert rates["1980s"]["standardized_rate"] == .55
    assert rates["2010s"]["standardized_rate"] == pytest.approx(.6)
    contrasts = {r["estimand"]: r for r in tables["era_contrasts"]
                 if r["contrast_id"] == "2010s_minus_1980s" and r["reference_id"] == refs[0]["reference_id"]}
    assert contrasts["observed_difference"]["estimate"] == pytest.approx(-1)
    assert contrasts["standardized_difference"]["estimate"] == pytest.approx(5)
    assert contrasts["composition_adjustment_difference"]["estimate"] == pytest.approx(-6)
    assert all(r["standard_error"] is None and r["uncertainty_status"] == "not_run" for r in contrasts.values())


def test_equal_years_is_a_different_reference_and_missing_years_are_visible(config):
    rows = [record("1980-01-01", i) for i in range(3)] + [record("2010-01-01", 9, group="non_friendly")]
    pooled, _ = build_reference(rows, config, "pooled_matches")
    annual, _ = build_reference(rows, config, "equal_years")
    assert pooled["weight_friendly"] == .75 and annual["weight_friendly"] == .5
    assert 1981 in annual["missing_years"]


def test_missing_stratum_and_empty_era_are_not_zero(config):
    rows = [record("1980-01-01", 1)]
    rates = era_rates(rows, config, .5)
    assert rates["1980s"]["standardized_rate"] is None and rates["1980s"]["status"] == "missing_stratum"
    assert rates["1990s"]["observed_rate"] is None and rates["1990s"]["status"] == "empty_group"
    assert era_rates(rows, config, 1)["1980s"]["standardized_rate"] == 1


def test_role_swap_uses_same_team_and_unordered_pair(config):
    rows = [record("1980-01-01", 1), record("1980-01-02", 2, home_team_id="B", away_team_id="A")]
    samples, _ = select_samples(rows, config)
    tables = build_statistics(samples, config, outcomes=False)
    teams = [r for r in tables["team_schedule"] if r["tournament_group"] == "all"]
    assert len(teams) == 2 and all(r["n_home"] == 1 and r["n_away"] == 1 for r in teams)
    diag = {r["metric"]: r["value"] for r in tables["schedule_diagnostics"] if r["analysis_era_id"] == "1980s" and r["tournament_group"] == "all"}
    assert diag["n_distinct_pairs"] == 1 and diag["max_pair_repeats"] == 2


def test_leave_year_out_keeps_reference_fixed_and_empty_variants_explicit(config):
    rows = toy_rows()
    _, refs = build_standardization(rows, config)
    variants = run_sensitivity(rows, config, refs)
    deleted = [r for r in variants if r["check_type"] == "leave_one_year_out"]
    assert deleted and all(r["reference_id"] == refs[0]["reference_id"] for r in deleted)
    assert all(r["estimate_pp"] is None and r["status"] == "not_estimable" for r in deleted)


def test_weight_flip_point_and_endpoints(config):
    rows = [record("1980-01-01", 1, outcome="draw"), record("1980-01-02", 2, group="non_friendly"),
            record("2010-01-01", 3), record("2010-01-02", 4, group="non_friendly", outcome="draw")]
    tables, _ = build_standardization(rows, config)
    grid = [r for r in tables["weight_sensitivity"] if r["contrast_id"] == "2010s_minus_1980s"]
    assert next(r for r in grid if r["weight_friendly"] == 0)["difference_pp"] == -100
    assert next(r for r in grid if r["weight_friendly"] == 1)["difference_pp"] == 100
    assert next(r for r in grid if r["weight_friendly"] == .5)["difference_pp"] == 0
    assert all(r["flip_weight"] == .5 for r in grid)


@pytest.mark.parametrize("change,code", [
    (lambda c: c["eras"][1].update(start="1989-12-31"), "ANALYSIS_CONFIG_INVALID"),
    (lambda c: c.update(analysis_end="2025-01-01"), "ANALYSIS_CONFIG_INVALID"),
    (lambda c: c["inference"].update(mode="wilson"), "INFERENCE_NOT_IMPLEMENTED"),
    (lambda c: c.update(reference_scheme="best_p_value"), "ANALYSIS_CONFIG_INVALID"),
])
def test_config_rejects_unsupported_or_ambiguous_protocols(config, tmp_path, change, code):
    change(config)
    path = tmp_path / "eras.json"
    write_json(path, config)
    with pytest.raises(PrepError) as exc:
        load_analysis_config(path, "2024-12-31")
    assert exc.value.code == code


def test_validation_detects_changed_counts_and_serialization_is_explicit(config):
    samples, membership = select_samples(toy_rows(), config)
    tables = build_statistics(samples, config)
    standardized, _ = build_standardization(samples["classified_venue"], config)
    tables.update(standardized)
    assert validate_tables(tables, samples, membership, config)["passed"]
    artifacts = table_artifacts({"era_estimates": tables["era_estimates"]}, "fixture")
    payload = artifacts["outputs/tables/eras/fixture/era_estimates.csv"]
    assert payload.startswith(b"\xef\xbb\xbf") and b"\r\n" not in payload and b"NaN" not in payload
    assert b",,,,,,,not_run," in payload
    tables["era_summary"][0]["n_home_wins"] += 1
    with pytest.raises(PrepError, match="outcome_counts"):
        validate_tables(tables, samples, membership, config)


def test_conflicting_outputs_are_not_overwritten(tmp_path):
    destination = tmp_path / "outputs" / "result.csv"
    destination.parent.mkdir()
    destination.write_bytes(b"old")
    with pytest.raises(PrepError) as exc:
        publish_outputs(tmp_path, {"outputs/new.csv": b"new", "outputs/result.csv": b"conflict"})
    assert exc.value.code == "REPRODUCIBILITY_MISMATCH"
    assert destination.read_bytes() == b"old" and not (destination.parent / "new.csv").exists()


def test_full_pipeline_repeatability_verifier_and_failed_run_record(config, tmp_path):
    root = tmp_path
    shutil.copytree(PROJECT / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__"))
    prep = json.loads((PROJECT / "config.json").read_text(encoding="utf-8"))
    write_json(root / "config.json", prep)
    raw = paths(root, prep)["input"]
    games = []
    for i, (day, tournament, score) in enumerate((("1980-01-01", "Friendly", "1"), ("1980-01-02", "Cup", "0"),
                                                   ("2010-01-01", "Friendly", "0"), ("2010-01-02", "Cup", "1"))):
        games.append(dict(zip(SCHEMAS["results.csv"], [day, "Alpha", "Beta", score, "0", tournament, "City", "Alpha", "FALSE"])))
    for name, fields in SCHEMAS.items():
        atomic_bytes(raw / name, csv_bytes(fields, games if name == "results.csv" else []))
    atomic_bytes(raw / "README.md", b"synthetic\n")
    atomic_bytes(raw / "LICENSE", b"synthetic\n")
    register_snapshot(root, prep)
    folder, _, _ = run_cleaning(root, prep)
    config["data_version"] = folder.name
    write_json(root / "config" / "eras.json", config)
    original_hash = file_hash(folder / "matches_clean.csv")
    manifest1, run1 = run_analysis(root / "config.json", "config/eras.json", "all")
    manifest2, run2 = run_analysis(root / "config.json", "config/eras.json", "all")
    assert manifest1["analysis_id"] == manifest2["analysis_id"] and run1 != run2
    core1 = {k: v for k, v in manifest1["outputs"].items() if "/tables/" in k or "/figures/" in k}
    assert core1 == {k: v for k, v in manifest2["outputs"].items() if k in core1}
    assert verify_run(root, (run2 / "run_manifest.json").relative_to(root).as_posix())["passed"]
    assert file_hash(folder / "matches_clean.csv") == original_hash
    diagnostic, diagnostic_run = run_analysis(root / "config.json", "config/eras.json", "diagnose")
    assert diagnostic["stages"]["description"] == "not_run"
    assert not any("era_estimates.csv" in path or "/figures/" in path for path in diagnostic["outputs"])
    assert verify_run(root, (diagnostic_run / "run_manifest.json").relative_to(root).as_posix())["passed"]
    config["inference"]["mode"] = "unapproved"
    write_json(root / "config" / "eras.json", config)
    with pytest.raises(PrepError):
        run_analysis(root / "config.json", "config/eras.json", "all")
    runs = list((root / "outputs" / "logs" / "eras").glob("*/run_manifest.json"))
    assert any(json.loads(p.read_text(encoding="utf-8"))["status"] == "failed" for p in runs)
    with pytest.raises(PrepError):
        verify_run(root, (run2 / "run_manifest.json").relative_to(root).as_posix())
