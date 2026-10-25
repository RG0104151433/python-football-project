"""Identity inventory tests use synthetic records, never edit the project baseline."""
import copy
import json
from pathlib import Path
import shutil
import zipfile

import pytest

from scripts.audit_team_identity import (CODE_FILES, collect_inventory, digest, json_bytes,
                                         load_inputs, run_inventory, safe, verify_baseline, verify_run)
from src.clean import run_cleaning
from src.data_contract import SCHEMAS, PrepError, atomic_bytes, csv_bytes, fingerprint
from src.snapshot import register_snapshot

PROJECT = Path(__file__).resolve().parents[1]


def records():
    raw = [dict(date="1980-01-01", home_team="Alpha", away_team="Beta", home_score="1",
                away_score="0", tournament="Friendly", city="Town", country="Beta", neutral="FALSE"),
           dict(date="1970-01-01", home_team="Alpha", away_team="Oldland", home_score="0",
                away_score="0", tournament="Friendly", city="Town", country="Oldland", neutral="TRUE"),
           dict(date="1981-01-01", home_team="Beta", away_team="Alpha", home_score="0",
                away_score="0", tournament="Cup", city="Town", country="Beta", neutral="FALSE")]
    registry = [dict(team_id="team:" + n.lower(), canonical_name=n, registry_version="v1", source_name=n)
                for n in ("Alpha", "Beta", "Oldland")]
    clean = []
    for i, row in enumerate(raw, 1):
        clean.append(dict(match_id="results:" + fingerprint([row[k] for k in SCHEMAS["results.csv"]]),
                          source_record_id=f"results:rawsha:{i}", date=row["date"],
                          home_team=row["home_team"], away_team=row["away_team"],
                          home_team_id="team:" + row["home_team"].lower(),
                          away_team_id="team:" + row["away_team"].lower(),
                          country=row["country"], city=row["city"],
                          is_neutral="true" if row["neutral"] == "TRUE" else "false",
                          eligible_venue_analysis="true", eligible_tournament_analysis="true",
                          tournament_group="friendly" if row["tournament"] == "Friendly" else "non_friendly"))
    former = [dict(current="Alpha", former="Earlier Alpha", start_date="1970-01-01", end_date="1980-01-01")]
    return dict(raw=raw, clean=clean, registry=registry, former=former,
                scope={"start": "1980-01-01", "end": "2024-12-31"}, results_sha="rawsha",
                former_source={"path": "former.csv", "sha256": "formersha"})


def test_counts_clues_and_priority_are_not_identity_decisions():
    data = records()
    original = copy.deepcopy(data)
    tables, counts, checks = collect_inventory(**data)
    assert data == original
    assert counts["raw_labels"] == 3 and counts["study_labels"] == 2
    assert counts["study_matches"] == 2
    assert counts["study_matches_with_historical_clues"] == 1
    assert counts["study_literal_venue_flags"] == 1
    assert all(checks.values())
    assert {r["identity_classification"] for r in tables["team_inventory"]} == {"unreviewed"}
    assert {r["review_status"] for r in tables["review_queue"]} == {"pending"}
    assert all(not r["scope_decision"] and not r["checked_by"] for r in tables["review_queue"])
    assert next(r for r in tables["team_inventory"] if r["source_team_label"] == "Oldland")["review_priority"] == "3_outside_study"
    # Both sides are queued for a literal venue relation, never swapped or excluded.
    assert [r["source_team_label"] for r in tables["review_queue"][:2]] == ["Alpha", "Beta"]


def test_historical_intervals_include_both_endpoints_and_excluded_raw_records():
    data = records()
    data["clean"] = data["clean"][:1] + data["clean"][2:]
    tables, counts, _ = collect_inventory(**data)
    assert len(tables["historical_name_clues"]) == 2
    outside = next(r for r in tables["historical_name_clues"] if r["date"] == "1970-01-01")
    assert outside["in_clean"] is False and outside["in_study"] is False
    assert counts["study_matches_with_historical_clues"] == 1


@pytest.mark.parametrize("change,code", [
    ("registry_collision", "IDENTITY_REGISTRY_INVALID"),
    ("unregistered", "IDENTITY_TEAM_UNREGISTERED"),
    ("interval", "IDENTITY_FORMER_RULE_INVALID"),
    ("clean_id", "IDENTITY_CLEAN_TEAM_MISMATCH"),
    ("source_content", "IDENTITY_SOURCE_CONTENT_MISMATCH"),
])
def test_invalid_sources_and_rules_fail_explicitly(change, code):
    data = records()
    if change == "registry_collision":
        data["registry"][1]["team_id"] = data["registry"][0]["team_id"]
    elif change == "unregistered":
        data["registry"] = [r for r in data["registry"] if r["canonical_name"] != "Oldland"]
    elif change == "interval":
        data["former"][0]["end_date"] = "1969-01-01"
    elif change == "clean_id":
        data["clean"][0]["home_team_id"] = "wrong"
    else:
        data["clean"][0]["match_id"] = "results:wrong"
    with pytest.raises(PrepError) as exc:
        collect_inventory(**data)
    assert exc.value.code == code


def test_scope_does_not_treat_unknown_or_neutral_venue_as_home():
    data = records()
    data["clean"][0]["is_neutral"] = ""
    tables, counts, _ = collect_inventory(**data)
    assert counts["study_matches"] == 1
    assert tables["venue_name_flags"] == []
    data["clean"][0]["is_neutral"] = "true"
    assert collect_inventory(**data)[1]["study_matches"] == 1


def test_path_escape_is_rejected(tmp_path):
    with pytest.raises(PrepError) as exc:
        safe(tmp_path, "../outside.csv")
    assert exc.value.code == "IDENTITY_PATH_OUTSIDE_PROJECT"
    with pytest.raises(PrepError) as exc:
        safe(tmp_path, str(tmp_path / "absolute.csv"))
    assert exc.value.code == "IDENTITY_PATH_INVALID"


@pytest.fixture
def prepared_project(tmp_path):
    for p in CODE_FILES:
        target = tmp_path / p
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / p, target)
    prep = json.loads((PROJECT / "config.json").read_text(encoding="utf-8"))
    atomic_bytes(tmp_path / "config.json", json_bytes(prep))
    sample = records()["raw"]
    input_dir = tmp_path / "data/raw/international_results"
    for name, fields in SCHEMAS.items():
        rows = sample if name == "results.csv" else []
        if name == "former_names.csv":
            rows = records()["former"]
        atomic_bytes(input_dir / name, csv_bytes(fields, rows))
    atomic_bytes(input_dir / "README.md", b"Synthetic test source\n")
    atomic_bytes(input_dir / "LICENSE", b"Synthetic fixture\n")
    register_snapshot(tmp_path, prep)
    cleaned_folder, _, _ = run_cleaning(tmp_path, prep)
    version = cleaned_folder.name
    analysis = json.loads((PROJECT / "config/eras.json").read_text(encoding="utf-8"))
    analysis["data_version"] = version
    atomic_bytes(tmp_path / "config/eras.json", json_bytes(analysis))
    dm = json.loads((tmp_path / f"data/processed/{version}/dataset_manifest.json").read_text(encoding="utf-8"))
    relatives = {"config.json", "config/eras.json", "data/raw/manifest.json",
                 f"data/processed/{version}/dataset_manifest.json", dm["lineage_path"],
                 "data/external/team_registry.csv"}
    relatives.update(e["path"] for e in dm["input_files"])
    relatives.update(f"data/processed/{version}/{n}" for n in dm["output_hashes"])
    entries = [{"path": p, "sha256": digest((tmp_path / p).read_bytes())} for p in sorted(relatives)]
    archive = tmp_path / "baseline.zip"
    with zipfile.ZipFile(archive, "x") as z:
        for p in relatives:
            z.writestr(p, (tmp_path / p).read_bytes())
    baseline = dict(schema_version="identity-baseline-v1", baseline_id="toy-baseline", data_version=version,
                    files=entries, archive={"path": "baseline.zip", "sha256": digest(archive.read_bytes())})
    atomic_bytes(tmp_path / "baseline.json", json_bytes(baseline))
    config = dict(schema_version="team-identity-inventory-config-v1", data_version=version,
                  baseline_manifest="baseline.json", baseline_manifest_sha256=digest(json_bytes(baseline)),
                  prep_config="config.json", analysis_config="config/eras.json")
    atomic_bytes(tmp_path / "config/team_identity.json", json_bytes(config))
    return tmp_path, config, baseline


def test_end_to_end_repeats_without_overwrite_and_detects_output_tampering(prepared_project):
    root, _, _ = prepared_project
    first = run_inventory(root, "config/team_identity.json")
    second = run_inventory(root, "config/team_identity.json")
    assert first["inventory_id"] == second["inventory_id"]
    assert first["run_manifest"] != second["run_manifest"]
    m1 = json.loads((root / first["run_manifest"]).read_text(encoding="utf-8"))
    m2 = json.loads((root / second["run_manifest"]).read_text(encoding="utf-8"))
    assert {Path(p).name: h for p, h in m1["outputs"].items()} == {Path(p).name: h for p, h in m2["outputs"].items()}
    assert verify_run(root, first["run_manifest"])["passed"] is True
    target = root / next(p for p in m1["outputs"] if p.endswith("team_inventory.csv"))
    content = target.read_bytes()
    assert content.startswith(b"\xef\xbb\xbf") and b"\r\n" not in content
    target.write_bytes(content + b"tampered")
    with pytest.raises(PrepError) as exc:
        verify_run(root, first["run_manifest"])
    assert exc.value.code == "IDENTITY_RUN_HASH_MISMATCH"
    assert verify_run(root, second["run_manifest"])["passed"] is True


def test_registered_input_changes_fail_before_outputs_are_created(prepared_project):
    root, _, _ = prepared_project
    target = root / "data/external/team_registry.csv"
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(PrepError) as exc:
        run_inventory(root, "config/team_identity.json")
    assert exc.value.code == "IDENTITY_INPUT_BASELINE_MISMATCH"
    assert not (root / "outputs/logs/team_identity").exists()


def test_archive_and_config_integrity_are_checked(prepared_project):
    root, config, baseline = prepared_project
    (root / "baseline.zip").write_bytes(b"not the registered archive")
    with pytest.raises(PrepError) as exc:
        verify_baseline(root, baseline)
    assert exc.value.code == "IDENTITY_BASELINE_ARCHIVE_MISMATCH"
    (root / "baseline.json").write_bytes(json_bytes({**baseline, "baseline_id": "changed"}))
    with pytest.raises(PrepError) as exc:
        load_inputs(root, "config/team_identity.json")
    assert exc.value.code == "IDENTITY_BASELINE_MANIFEST_MISMATCH"
