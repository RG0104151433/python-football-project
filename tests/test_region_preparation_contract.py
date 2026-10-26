"""Exercise real CLI, provenance and cross-file contracts of geography preparation."""
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/prepare_region_mapping.py"
PACKAGE = ROOT / "data/external/geography_preparation/geo-prep-v3"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("region_contract_subject", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_selftest_cli_works_outside_repository(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "selftest", "--root", str(ROOT), "--package", str(PACKAGE)],
        cwd=tmp_path, text=True, capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    output = json.loads(result.stdout)
    assert output["passed"] == output["total"] == 14


def test_finalize_cli_refuses_failed_run_without_attribute_error(tmp_path):
    (tmp_path / "validation_report.json").write_text('{"status":"failed"}', encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "finalize", str(tmp_path)],
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 2
    assert json.loads(result.stdout)["error_type"] == "InputError"
    assert not (tmp_path / "manifest.json").exists()


def test_replay_refuses_changed_input_before_running_child(tool, tmp_path):
    (tmp_path / "inputs").mkdir()
    data = tmp_path / "inputs/rules.csv"
    data.write_text("original", encoding="utf-8")
    manifest = {"items": {"package_seed": {"snapshot_path": "inputs/rules.csv", "sha256": tool.sha256(data)}}}
    (tmp_path / "inputs/inputs_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    data.write_text("changed", encoding="utf-8")
    with pytest.raises(tool.InputError, match="输入快照与登记指纹不一致"):
        tool.replay(SimpleNamespace(root=str(ROOT), run=str(tmp_path), run_root=str(tmp_path / "unused")))
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize("field", ["data_version", "source_record_id"])
def test_join_rejects_mismatched_lineage_before_grouping(tool, tmp_path, field):
    member = {"match_id": "m1", "included": "true", "data_version": "d1", "identity_version": "i1",
              "sample_id": "s1", "date": "2000-01-01", "tournament_group": "friendly", "source_record_id": "r1"}
    clean = {k: member[k] for k in ("match_id", "data_version", "date", "tournament_group", "source_record_id")}
    clean[field] = "conflicting"
    membership_path, clean_path = tmp_path / "members.csv", tmp_path / "clean.csv"
    tool.write_csv(str(membership_path), [member], list(member))
    tool.write_csv(str(clean_path), [clean], list(clean))
    with pytest.raises(tool.InputError, match="关联后字段不一致"):
        tool.run_core(str(tmp_path), {"q2_membership":str(membership_path), "matches_clean":str(clean_path)},
                      "fixture", str(ROOT), [], {})
    assert not (tmp_path / "match_region_relations.csv").exists()


def test_exported_boolean_is_canonical(tool, tmp_path):
    path = tmp_path / "flags.csv"
    tool.write_csv(str(path), [{"flag": True}, {"flag": False}], ["flag"])
    with path.open(encoding="utf-8-sig", newline="") as f:
        assert [r["flag"] for r in csv.DictReader(f)] == ["true", "false"]


def test_partial_geography_does_not_discard_determinable_relation(tool):
    def rule(key, region, unit):
        return {"rule_id":key, "project_region_code":region, "project_unit_code":unit,
                "date_start":"1980-01-01", "date_end":"2024-12-31"}
    rules = {"a":[rule("a", "150", "")], "b":[rule("b", "142", "")],
             "c":[rule("c", "150", "151")]}
    cross, same = tool.process_relations(
        [("cross", "2000-01-01", "a", "b"), ("same", "2000-01-01", "a", "c")], rules)
    assert cross["B_usable"] and cross["relation"] == "cross_region"
    assert same["A_usable"] and not same["B_usable"] and same["relation"] == "unknown_same_region"
