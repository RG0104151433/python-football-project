"""Locate the existing beam instability before changing the numerical method."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/logs/strength/budget-b6687cb39711461cf7b0"
TARGET = ROOT / "outputs/logs/strength/refinement-20261029/diagnosis.json"


def read(name):
    with (SOURCE / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    rows = read("development_predictions.csv")
    a = {r["match_id"]: r for r in rows if r["components"] == "32" and r["count_cap"] == "3"}
    b = {r["match_id"]: r for r in rows if r["components"] == "64" and r["count_cap"] == "3"}
    differences = []
    for mid in a:
        x, y = a[mid], b[mid]
        differences.append({
            "match_id": mid, "date": x["date"], "home": x["home"], "away": x["away"],
            "max_probability_difference": max(abs(float(x[k]) - float(y[k])) for k in ("p_home", "p_draw", "p_away")),
            "difference_mean_delta": float(y["difference"]) - float(x["difference"]),
            "difference_variance_delta": float(y["difference_variance"]) - float(x["difference_variance"]),
            "home_term_delta": float(y["home_term"]) - float(x["home_term"]),
        })
    development = [r for r in differences if "1970" <= r["date"] <= "1974-12-31"]
    diagnostics = read("daily_diagnostics.csv")
    report = {
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "inputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob("*.csv")},
        "same_poisson_cap": 3,
        "all_comparison_matches": len(differences),
        "development_matches": len(development),
        "worst_development": sorted(development, key=lambda r: -r["max_probability_difference"])[:10],
        "first_all_history_over_gate": next((r for r in sorted(differences, key=lambda r: (r["date"], r["match_id"]))
                                           if r["max_probability_difference"] > .01), None),
        "largest_pruning_days": sorted([r for r in diagnostics if r["components"] == "64" and r["count_cap"] == "3"],
                                       key=lambda r: -float(r["approximate_posterior_pruned_mass"]))[:5],
        "inference": "same-cap beam changes affect both centers and uncertainty; pruning is a candidate cause, not yet a proven unique cause",
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"worst": report["worst_development"][:3],
                      "first_over_gate": report["first_all_history_over_gate"],
                      "largest_pruning": report["largest_pruning_days"][:1]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
