"""End-to-end tests with synthetic files, never the real research snapshot."""
import json

import pytest

from src.clean import run_cleaning
from src.data_contract import (SCHEMAS, PrepError, atomic_bytes, csv_bytes, file_hash,
                               load_config, paths, read_csv, write_json, GROUP_FIELDS)
from src.snapshot import register_snapshot, verify_snapshot
from src.validate import validate_dataset, validate_rows


def match(day="2018-01-01", **changes):
    value = dict(zip(SCHEMAS["results.csv"], [day, "Alpha", "Beta", "1", "0", "Friendly", "City", "Alpha", "FALSE"]))
    value.update(changes)
    return value


@pytest.fixture
def project(tmp_path):
    config = {"data": {"cutoff_date": "2024-12-31", "raw_dir": "data/raw", "processed_dir": "data/processed"},
              "time_split": {"warmup_end": "1979-12-31", "train_end": "2014-12-31", "valid_end": "2019-12-31", "test_end": "2024-12-31"}}
    write_json(tmp_path / "config.json", config)
    raw = paths(tmp_path, config)["input"]
    for name, fields in SCHEMAS.items():
        atomic_bytes(raw / name, csv_bytes(fields, [match()] if name == "results.csv" else []))
    atomic_bytes(raw / "README.md", b"synthetic test input\n")
    atomic_bytes(raw / "LICENSE", b"synthetic test fixture\n")
    return tmp_path, config


def set_matches(root, config, rows):
    atomic_bytes(paths(root, config)["input"] / "results.csv", csv_bytes(SCHEMAS["results.csv"], rows))


def test_snapshot_registration_is_explicit_and_never_refreshes_changes(project):
    root, config = project
    with pytest.raises(PrepError) as exc:
        verify_snapshot(root, config)
    assert exc.value.code == "SNAPSHOT_NOT_REGISTERED"
    manifest = register_snapshot(root, config)
    before = file_hash(paths(root, config)["snapshot"])
    assert register_snapshot(root, config) == manifest
    assert file_hash(paths(root, config)["snapshot"]) == before
    set_matches(root, config, [match(home_score="9")])
    with pytest.raises(PrepError) as exc:
        register_snapshot(root, config)
    assert exc.value.code == "SNAPSHOT_MISMATCH"
    assert file_hash(paths(root, config)["snapshot"]) == before


def test_pipeline_is_reproducible_and_preserves_raw(project):
    root, config = project
    register_snapshot(root, config)
    raw = paths(root, config)["input"] / "results.csv"
    before = file_hash(raw)
    target, run, report = run_cleaning(root, config)
    first = file_hash(target / "matches_clean.csv")
    target2, run2, report2 = run_cleaning(root, config)
    assert target == target2 and run != run2
    assert report2["reused_identical_dataset"]
    assert first == file_hash(target2 / "matches_clean.csv")
    assert file_hash(run / "row_lineage.csv") == file_hash(run2 / "row_lineage.csv")
    assert before == file_hash(raw)
    assert validate_dataset(root, config, target.name)["passed"]


def test_conflicts_isolated_unknown_venue_limited_and_future_kept_outside(project):
    root, config = project
    rows = [match(), match(home_score="2"), match("2018-01-02", neutral="unknown"),
            match("2025-01-01"), match("2018-01-03", home_score="")]
    set_matches(root, config, rows)
    register_snapshot(root, config)
    target, run, report = run_cleaning(root, config)
    assert report["counts"]["states"] == {"included": 1, "outside_window": 1, "quarantined": 3}
    _, result = read_csv(target / "matches_clean.csv")
    assert result[0]["is_neutral"] == "" and result[0]["eligible_elo"] == "true"
    assert result[0]["eligible_venue_analysis"] == "false"
    _, lineage = read_csv(run / "row_lineage.csv")
    assert len(lineage) == 5 and len({r["source_record_id"] for r in lineage}) == 5


def test_shootout_winner_does_not_change_draw_target(project):
    root, config = project
    set_matches(root, config, [match(home_score="3", away_score="3")])
    raw = paths(root, config)["input"]
    values = dict(zip(SCHEMAS["shootouts.csv"], ["2018-01-01", "Alpha", "Beta", "Beta", ""]))
    atomic_bytes(raw / "shootouts.csv", csv_bytes(SCHEMAS["shootouts.csv"], [values]))
    register_snapshot(root, config)
    target, _, _ = run_cleaning(root, config)
    row = read_csv(target / "matches_clean.csv")[1][0]
    assert row["outcome"] == "draw" and row["shootout_winner_id"] == "team:beta"


def test_failed_external_change_cannot_overwrite_existing_dataset(project):
    root, config = project
    register_snapshot(root, config)
    target, _, _ = run_cleaning(root, config)
    before = file_hash(target / "matches_clean.csv")
    atomic_bytes(paths(root, config)["external"] / "amendments.jsonl", b'{"status":"approved"}\n')
    with pytest.raises(PrepError) as exc:
        run_cleaning(root, config)
    assert exc.value.code == "AMENDMENTS_NOT_IMPLEMENTED"
    assert file_hash(target / "matches_clean.csv") == before


def test_empty_dataset_fails_without_publishing(project):
    root, config = project
    set_matches(root, config, [match(home_score="invalid")])
    register_snapshot(root, config)
    with pytest.raises(PrepError) as exc:
        run_cleaning(root, config)
    assert exc.value.code == "VALIDATION_FAILED"
    assert not paths(root, config)["processed"].exists()


def test_validate_detects_saved_file_tampering(project):
    root, config = project
    register_snapshot(root, config)
    target, _, _ = run_cleaning(root, config)
    with (target / "matches_clean.csv").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(PrepError) as exc:
        validate_dataset(root, config, target.name)
    assert exc.value.code == "OUTPUT_HASH_MISMATCH"


def test_required_schema_and_invalid_config_fail_early(project):
    root, config = project
    atomic_bytes(paths(root, config)["input"] / "results.csv", b"date,home_team\n2018-01-01,Alpha\n")
    with pytest.raises(PrepError) as exc:
        register_snapshot(root, config)
    assert exc.value.code == "SCHEMA_MISSING"
    config["data"]["processed_dir"] = "data/raw/processed"
    write_json(root / "config.json", config)
    with pytest.raises(PrepError):
        load_config(root / "config.json")


def test_validation_rejects_relabelled_score(project):
    root, config = project
    register_snapshot(root, config)
    target, run, _ = run_cleaning(root, config)
    rows = read_csv(target / "matches_clean.csv")[1]
    lineage = read_csv(run / "row_lineage.csv")[1]
    rows[0]["outcome"] = "away"
    ids = {r["source_record_id"] for r in lineage}
    assert not validate_rows(rows, lineage, ids, config["data"]["cutoff_date"])["passed"]


def test_tournament_exception_requires_approval_and_registered_evidence(project):
    root, config = project
    register_snapshot(root, config)
    run_cleaning(root, config)
    external = paths(root, config)["external"]
    path = external / "tournament_groups.csv"
    rows = read_csv(path)[1]
    rows[0]["group"] = "non_friendly"
    atomic_bytes(path, csv_bytes(GROUP_FIELDS, rows))
    with pytest.raises(PrepError) as exc:
        run_cleaning(root, config)
    assert exc.value.code == "TOURNAMENT_OVERRIDE_UNAPPROVED"
    rows[0].update(review_status="approved", rationale="synthetic exception", evidence_id="test-evidence")
    atomic_bytes(path, csv_bytes(GROUP_FIELDS, rows))
    with pytest.raises(PrepError) as exc:
        run_cleaning(root, config)
    assert exc.value.code == "EVIDENCE_MISSING"
    atomic_bytes(external / "evidence.csv", csv_bytes(["evidence_id", "url"], [{"evidence_id": "test-evidence", "url": "https://example.invalid/synthetic"}]))
    target, _, _ = run_cleaning(root, config)
    assert read_csv(target / "matches_clean.csv")[1][0]["tournament_group"] == "non_friendly"


def test_windows_console_does_not_crash_on_non_gbk_team_name():
    import os
    import subprocess
    import sys
    env = {**os.environ, "PYTHONIOENCODING": "gbk"}
    code = "from src.data_contract import run_cli; run_cli(lambda: print('Cura\\u00e7ao'))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env)
    assert result.returncode == 0
    assert result.stdout.decode("utf-8").strip() == "Curaçao"
