"""Verify the recorded first strength pilot without rerunning model selection."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/logs/strength"
CURRENT = BASE / "pilot-0999a6bb24baf024e03f"
FIRST = BASE / "pilot-a41a495cc63d6120327a"
BUDGET = BASE / "budget-b6687cb39711461cf7b0"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def main():
    checks = []

    def check(name, ok):
        checks.append({"name": name, "passed": bool(ok)})

    reports = {}
    for folder in [CURRENT, FIRST, BUDGET]:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["outputs"].items():
            check(folder.name + ":" + name, sha(folder / name) == expected)
        reports[folder.name] = manifest
    current = json.loads((CURRENT / "report.json").read_text(encoding="utf-8"))
    old = json.loads((FIRST / "report.json").read_text(encoding="utf-8"))
    learning, old_learning = ROOT / current["stage1_learning"], ROOT / old["stage1_learning"]
    check("included_learning_bytes_unchanged_by_disposition_refinement",
          sha(learning / "learning_matches.csv") == sha(old_learning / "learning_matches.csv"))
    for name in ("simulation_metrics.csv", "simulation_trajectories.csv", "historical_metrics.csv",
                 "pilot_predictions.csv", "daily_diagnostics.csv", "calibration.csv", "sensitivity.csv"):
        check("first_and_current_statistical_file:" + name, sha(FIRST / name) == sha(CURRENT / name))
    for n, expected in reports[CURRENT.name]["identity"]["code"].items():
        check("current_source:" + n, canonical((ROOT / n).read_text(encoding="utf-8").replace("\r\n", "\n")) == expected)
    audit = json.loads((CURRENT / "independent_audit.json").read_text(encoding="utf-8"))
    check("independent_audit_passed", audit["passed"])
    check("failed_numerical_gate_not_hidden", current["numerical_acceptance"] is False and current["production_ready"] is False)
    # Reconstruct an exact source archive for the historical budget run from the
    # retained execution snapshots. Every file must match its recorded fingerprint.
    archives = [zipfile.ZipFile(FIRST / "source_snapshot.zip"), zipfile.ZipFile(CURRENT / "source_snapshot.zip")]
    content = {}
    for n, expected in reports[BUDGET.name]["identity"]["code"].items():
        found = None
        for z in archives:
            if n in z.namelist():
                data = z.read(n).decode("utf-8").replace("\r\n", "\n")
                if canonical(data) == expected:
                    found = data.encode("utf-8")
                    break
        check("historical_budget_source_recoverable:" + n, found is not None)
        if found is not None:
            content[n] = found
    for z in archives:
        z.close()
    if len(content) == len(reports[BUDGET.name]["identity"]["code"]):
        with zipfile.ZipFile(BUDGET / "verified_source_snapshot.zip", "w", compression=zipfile.ZIP_STORED) as z:
            for n, value in sorted(content.items()):
                z.writestr(zipfile.ZipInfo(n, (1980, 1, 1, 0, 0, 0)), value)
    timings = []
    for p in BASE.glob("execution-*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r["stage_id"] == CURRENT.name:
            timings.append(r)
    check("current_pilot_repeated_same_immutable_stage", len(timings) >= 2)
    check("raw_source_unchanged", sha(ROOT / "data/raw/international_results/results.csv") ==
          "5dcefd1aa0483979ea8378cef5be448d2005609d39945ea162378561a30a6767")
    check("clean_source_unchanged", sha(ROOT / "data/processed/prep-3fab808178cf8ad71d88/matches_clean.csv") ==
          "69ba00073970fe011a62f5871c08ace6285d7fe75d5a0d79afdac0ef972de9dc")
    result = {"passed": all(r["passed"] for r in checks), "checks": len(checks),
              "failed": [r for r in checks if not r["passed"]],
              "current_pilot": CURRENT.relative_to(ROOT).as_posix(),
              "repeat_execution_count": len(timings), "independent_output_checks": audit["checks"],
              "unit_test_source_sha256": sha(ROOT / "tests/test_strength.py"),
              "limits": "artifact and reproducibility acceptance only; numerical model acceptance remains false",
              "execution": "Codex (AI); no independent human review; working tree"}
    target = BASE / "delivery-20261029/review.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
