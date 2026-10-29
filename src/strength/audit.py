"""Independent output reconciliation: CSV scores, population, hashes and coverage."""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict

from ..data_contract import file_hash, write_json
from .io import ROOT, read_rows


def audit(folder):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})

    for name, sha in manifest["outputs"].items():
        check("output_hash:" + name, file_hash(folder / name) == sha)
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    learning = ROOT / report["stage1_learning"]
    lm = json.loads((learning / "manifest.json").read_text(encoding="utf-8"))
    for name, sha in lm["outputs"].items():
        check("learning_hash:" + name, file_hash(learning / name) == sha)
    ledger = read_rows(learning / "learning_ledger.csv")
    included = read_rows(learning / "learning_matches.csv")
    source = read_rows(ROOT / manifest["identity"]["config"]["clean_path"])
    check("ledger_covers_clean_ids_exactly", {r["match_id"] for r in ledger} == {r["match_id"] for r in source})
    check("ledger_ids_unique", len({r["match_id"] for r in ledger}) == len(ledger))
    check("included_matches_ledger", {r["match_id"] for r in included} ==
          {r["match_id"] for r in ledger if r["included"] == "true"})
    accepted = {r["match_id"] for r in ledger if r["accepted_current_study"] == "true"}
    check("all24917_retained", len(accepted) == 24917 and accepted.issubset({r["match_id"] for r in included}))
    original = {r["match_id"]: r for r in source}
    check("scores_dates_neutral_unchanged", all(
        r["date"] == original[r["match_id"]]["date"] and
        r["home_score"] == original[r["match_id"]]["home_score"] and
        r["away_score"] == original[r["match_id"]]["away_score"] and
        r["is_neutral"] == original[r["match_id"]]["is_neutral"] for r in ledger))
    forecasts = read_rows(folder / "pilot_predictions.csv")
    groups = defaultdict(list)
    for r in forecasts:
        p = [float(r[k]) for k in ("p_home", "p_draw", "p_away")]
        check("probabilities:" + r["model"] + ":" + r["start"] + ":" + r["match_id"],
              all(math.isfinite(x) and 0 <= x <= 1 for x in p) and abs(sum(p) - 1) <= 2e-9)
        check("cutoff:" + r["model"] + ":" + r["start"] + ":" + r["match_id"],
              r["prediction_cutoff"] == "initial_prior" or r["prediction_cutoff"] < r["date"])
        check("difference_variance:" + r["model"] + ":" + r["start"] + ":" + r["match_id"],
              abs(float(r["difference_variance"]) - float(r["home_variance"]) -
                  float(r["away_variance"]) + 2 * float(r["home_away_covariance"])) < 5e-9)
        check("source_outcome:" + r["match_id"],
              int(r["outcome_index"]) == {"home": 0, "draw": 1, "away": 2}[original[r["match_id"]]["outcome"]])
        groups[(r["model"], r["start"])].append(r)
    for key, rows in groups.items():
        check("unique_forecast_ids:" + str(key), len({r["match_id"] for r in rows}) == len(rows))
    for m in read_rows(folder / "historical_metrics.csv"):
        if m["model"] == "past_frequency":
            # Reconstruct independently, including the same-date count freeze.
            labels = set(manifest["identity"]["config"]["pilot"]["teams"])
            selected = [r for r in included if r["home_team"] in labels and r["away_team"] in labels
                        and int(r["date"][:4]) >= int(m["start"]) and r["date"] < "1980"]
            dates = defaultdict(list)
            for r in selected:
                dates[r["date"]].append(r)
            counts = [1, 1, 1]
            rows = []
            for day, batch in sorted(dates.items()):
                for r in batch:
                    rows.append({"date": day, "outcome_index": r["outcome_index"],
                                 **{k: counts[i] / sum(counts) for i, k in enumerate(("p_home", "p_draw", "p_away"))}})
                for r in batch:
                    counts[int(r["outcome_index"])] += 1
        else:
            rows = groups[(m["model"], m["start"])]
        lo, hi = ("1970", "1974-12-31") if m["period"] == "development" else ("1975", "1979-12-31")
        rows = [r for r in rows if lo <= r["date"] <= hi]
        probs = [[float(r[k]) for k in ("p_home", "p_draw", "p_away")] for r in rows]
        ys = [int(r["outcome_index"]) for r in rows]
        n = len(rows)
        loss = sum(-math.log(p[y]) for p, y in zip(probs, ys)) / n
        accuracy = sum(max(range(3), key=lambda k: p[k]) == y for p, y in zip(probs, ys)) / n
        brier = sum(sum((p[k] - int(k == y))**2 for k in range(3)) for p, y in zip(probs, ys)) / n
        check("metric:" + str(m), n == int(m["count"]) and abs(loss - float(m["log_loss"])) < 3e-9
              and abs(accuracy - float(m["accuracy"])) < 3e-9 and abs(brier - float(m["brier"])) < 3e-9)
    return {"checks": len(checks), "passed": all(c["passed"] for c in checks),
            "failed": [c for c in checks if not c["passed"]],
            "scope": "independent arithmetic/identity/time checks, not model validity or independent human review"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", required=True)
    args = parser.parse_args()
    folder = (ROOT / args.pilot).resolve()
    if not folder.is_relative_to(ROOT):
        raise ValueError("Outside workspace")
    result = audit(folder)
    write_json(folder / "independent_audit.json", result)
    print(json.dumps(result, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
