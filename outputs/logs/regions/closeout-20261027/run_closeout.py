"""Reproduce the rendering correction and validate unchanged descriptive tables."""
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pytest
from scripts.analyze_regions import run_analysis
from scripts.audit_region_support import run as audit_support
from scripts.verify_region_analysis import audit, compare_statistics
from src.regions.export import verify_run
from src.regions.io import json_bytes, read_json, sha


def main():
    out = Path(__file__).resolve().parent
    code = pytest.main(["-q", "-p", "no:cacheprovider", "--junitxml=" + str(out / "tests.xml")])
    if code:
        raise SystemExit(code)
    first = run_analysis(ROOT, run_root="outputs/logs/regions/closeout-20261027")
    second = run_analysis(ROOT, run_root="outputs/logs/regions/closeout-20261027")
    a1 = audit(ROOT, first["run_manifest"])
    (out / "independent_audit_first.json").write_bytes(json_bytes(a1))
    a2 = audit(ROOT, second["run_manifest"], first["run_manifest"])
    (out / "independent_audit_repeat.json").write_bytes(json_bytes(a2))
    old = "outputs/logs/regions/expanded-20261027/regions-20261027T015835582785Z-28a5b4de/run_manifest.json"
    old_integrity = verify_run(ROOT, old)
    old_v3 = verify_run(ROOT, "outputs/logs/regions/regions-20261026T135956693371Z-182ec8a6/run_manifest.json")
    statistics = compare_statistics(ROOT, read_json(ROOT / first["run_manifest"]), old)
    support = audit_support(ROOT, first["run_manifest"], "outputs/logs/regions/closeout-20261027/support")
    xml = ET.parse(out / "tests.xml").getroot()
    tests = sum(int(s.get("tests", 0)) for s in xml.iter("testsuite"))
    result = dict(status="passed", decision_log_id="R20261027-03", reference=first, repeat=second,
                  tests_passed=tests, independent_audit=a2, old_v4_integrity=old_integrity,
                  old_v3_integrity=old_v3, unchanged_statistics=statistics, support=support,
                  orchestration_sha256=sha(Path(__file__)), inference="not_run", sensitivity="not_run",
                  human_review="not_performed")
    (out / "review.json").write_bytes(json_bytes(result))
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
