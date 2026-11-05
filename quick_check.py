"""Fast, read-only verification of the adopted course results.

Usage (from the repository root):
    python quick_check.py
    python quick_check.py --json
    python quick_check.py --full     # also runs the pytest suite

This script does NOT rerun any model, simulation, or long experiment and does
NOT write files. It checks that the raw snapshot, the adopted cleaned dataset,
the registered study population, the main Q5 aggregates, the Q6/Q7 evaluation
baseline, and the Q8 forecast ledger still agree with the recorded numbers.

The expected values are tied to the adopted versions. If the team adopts a new
data/result version, update the constants here and record the change in the
research log; do not edit data to make this script pass.

Exit code 0 means all checks passed; 1 means at least one check failed.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

RAW_RESULTS = ROOT / "data/raw/international_results/results.csv"
CLEAN = ROOT / "data/processed/prep-3fab808178cf8ad71d88/matches_clean.csv"
PIPELINE = ROOT / "研究/pipeline_state.json"
Q5_YEARLY = ROOT / "outputs/tables/strength_joint/rolling-prediction-4722c7b1b5f63cef35e3/yearly_metrics.csv"
Q6_COMBINATIONS = ROOT / "outputs/tables/history_window/joint-review-4888d987645daee73e19/combination_metrics.csv"
Q7_REGIONAL = ROOT / "outputs/tables/regional_effectiveness/regional-evaluation-7ea3e4ab7c7dbb8eeb58/regional_metrics.csv"
Q8_FORECASTS = ROOT / "outputs/tables/future_predictions/future-unl-61f639846da9193d4cca/forecasts.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def close(actual: float, expected: float, tolerance: float) -> bool:
    return abs(actual - expected) <= tolerance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    parser.add_argument("--full", action="store_true", help="also run the pytest suite")
    args = parser.parse_args()

    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    try:
        raw = read_rows(RAW_RESULTS)
        dates = [row["date"] for row in raw]
        teams = {row["home_team"] for row in raw} | {row["away_team"] for row in raw}
        tournaments = {row["tournament"] for row in raw}
        check(
            "raw snapshot",
            len(raw) == 49945 and min(dates) == "1872-11-30" and max(dates) == "2026-10-06",
            f"{len(raw):,} matches; {min(dates)}..{max(dates)}; {len(teams)} teams; {len(tournaments)} tournaments",
        )
    except Exception as exc:  # noqa: BLE001 - quick check must report, not crash
        check("raw snapshot", False, f"{type(exc).__name__}: {exc}")

    try:
        clean = read_rows(CLEAN)
        check("cleaned dataset", len(clean) == 48102, f"{len(clean):,} included matches")
    except Exception as exc:  # noqa: BLE001
        check("cleaned dataset", False, f"{type(exc).__name__}: {exc}")

    try:
        pipeline = json.loads(PIPELINE.read_text(encoding="utf-8"))
        confirmation = pipeline["data_confirmation"]
        expected = {
            "study_candidates": 26055,
            "study_retained": 24917,
            "study_excluded": 1138,
            "study_pending": 0,
            "user_approved_matches": 117,
        }
        actual = {key: confirmation.get(key) for key in expected}
        check(
            "study population",
            actual == expected,
            f"candidates={actual['study_candidates']:,}; retained={actual['study_retained']:,}; "
            f"excluded={actual['study_excluded']:,}; pending={actual['study_pending']}; "
            f"owner-approved={actual['user_approved_matches']}",
        )
    except Exception as exc:  # noqa: BLE001
        check("study population", False, f"{type(exc).__name__}: {exc}")

    try:
        rows = read_rows(Q5_YEARLY)
        expected = {
            "M0_nested": (0.671936, 58.19),
            "M1_strength": (0.566020, 69.83),
            "M3_nested": (0.563630, 70.01),
        }
        details = []
        ok = True
        for model, (expected_loss, expected_accuracy) in expected.items():
            selected = [row for row in rows if row["model_id"] == model]
            n = sum(int(row["matches"]) for row in selected)
            loss = sum(float(row["log_loss"]) * int(row["matches"]) for row in selected) / n
            accuracy = 100 * sum(
                float(row["binary_accuracy"]) * int(row["matches"]) for row in selected
            ) / n
            ok = ok and n == 21413 and close(loss, expected_loss, 5e-6) and close(
                accuracy, expected_accuracy, 0.01
            )
            details.append(f"{model}: n={n:,}, logloss={loss:.6f}, acc={accuracy:.2f}%")
        check("Q5 aggregates", ok, "; ".join(details))
    except Exception as exc:  # noqa: BLE001
        check("Q5 aggregates", False, f"{type(exc).__name__}: {exc}")

    try:
        rows = read_rows(Q6_COMBINATIONS)
        selected = [
            row
            for row in rows
            if row["scope"] == "evaluation"
            and row["combination_id"] == "cumulative_1950__outcome_cumulative"
        ]
        ok = (
            len(selected) == 1
            and int(selected[0]["matches"]) == 9727
            and close(float(selected[0]["primary_log_loss"]), 0.5591345107, 5e-9)
        )
        check(
            "Q6 baseline",
            ok,
            "9,727 evaluation matches; cumulative/cumulative logloss="
            + (selected[0]["primary_log_loss"] if selected else "missing"),
        )
    except Exception as exc:  # noqa: BLE001
        check("Q6 baseline", False, f"{type(exc).__name__}: {exc}")

    try:
        rows = read_rows(Q7_REGIONAL)
        selected = [
            row
            for row in rows
            if row["scope"] == "main" and row["group"] == "ALL" and row["model"] == "joint"
        ]
        ok = (
            len(selected) == 1
            and int(selected[0]["matches"]) == 9727
            and close(float(selected[0]["log_loss"]), 0.5591345107, 5e-9)
        )
        check(
            "Q7 overall",
            ok,
            "9,727 matches; joint logloss="
            + (selected[0]["log_loss"] if selected else "missing"),
        )
    except Exception as exc:  # noqa: BLE001
        check("Q7 overall", False, f"{type(exc).__name__}: {exc}")

    try:
        rows = read_rows(Q8_FORECASTS)
        status = {row["main_status"] for row in rows}
        dates = [row["date"] for row in rows]
        counts = {
            "issued": sum(1 for row in rows if row["main_status"] == "issued_binary"),
            "withheld": sum(
                1 for row in rows if row["main_status"] == "withheld_third_country_venue"
            ),
        }
        ok = (
            len(rows) == 52
            and counts == {"issued": 49, "withheld": 3}
            and min(dates) == "2026-11-12"
            and max(dates) == "2026-11-17"
            and status <= {"issued_binary", "withheld_third_country_venue"}
        )
        check(
            "Q8 forecasts",
            ok,
            f"{len(rows)} targets; {counts['issued']} binary; {counts['withheld']} withheld; "
            f"{min(dates)}..{max(dates)}",
        )
    except Exception as exc:  # noqa: BLE001
        check("Q8 forecasts", False, f"{type(exc).__name__}: {exc}")

    if args.full:
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--disable-warnings"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=300,
            )
            tail = (completed.stdout or completed.stderr).strip().splitlines()
            check(
                "pytest",
                completed.returncode == 0,
                tail[-1] if tail else "no output",
            )
        except Exception as exc:  # noqa: BLE001
            check("pytest", False, f"{type(exc).__name__}: {exc}")

    passed = sum(1 for item in checks if item["ok"])
    payload = {
        "passed": passed,
        "total": len(checks),
        "ok": passed == len(checks),
        "python": sys.version.split()[0],
        "checks": checks,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Quick check (read-only; no model rerun)")
        print(f"Python: {payload['python']}")
        for item in checks:
            mark = "PASS" if item["ok"] else "FAIL"
            print(f"[{mark}] {item['name']}: {item['detail']}")
        print(f"\nSUMMARY: {passed}/{len(checks)} passed")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
