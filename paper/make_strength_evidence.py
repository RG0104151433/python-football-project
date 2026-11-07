"""Present adopted stage-2 results; never rerate teams or refit a model."""
from pathlib import Path
import csv
import hashlib
import json
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
BASE = ROOT / "data/processed/strength/strength-delivery-ca43fe498cd43ec8e21f"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report_path = BASE / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    periods = ["reused_1980_1999", "reused_2000_2009",
               "reused_2010_2019", "reused_2020_2024"]
    checks = []
    for period in periods:
        matches = [r for r in report["forecast_checks"]
                   if r["scope"] == "accepted_study" and r["period"] == period]
        assert len(matches) == 1, period
        checks.append(matches[0])
    assert sum(r["count"] for r in checks) == 24917
    composition_path = ROOT / "outputs/logs/strength/composed-calibration-8176105d420b3f2400eb/report.json"
    composition = json.loads(composition_path.read_text(encoding="utf-8"))
    passed = {name: candidate for name, candidate in composition["candidates"].items()
              if candidate["passed"]}
    assert len(composition["candidates"]) == 8 and len(passed) == 2
    composition_scores = {}
    for name, candidate in passed.items():
        rows = [r for r in candidate["forecast_checks"]
                if r["scope"] == "accepted_study" and r["period"] in periods]
        assert len(rows) == 4 and sum(r["count"] for r in rows) == 24917
        composition_scores[name] = sum(r["count"] * r["log_loss"] for r in rows) / 24917
    lines = []
    for r in checks:
        label = r["period"].removeprefix("reused_").replace("_", "--")
        lines.append(f"{label} & {r['count']:,} & {r['frequency_log_loss']:.6f} & "
                     f"{r['fixed_step_log_loss']:.6f} & {r['log_loss']:.6f} & "
                     f"{100*r['accuracy']:.2f} & {100*r['home_probability_bias']:+.4f} " + r"\\")
    rows_path = PAPER / "figures/strength_validation_rows.tex"
    rows_path.write_text(
        r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrrrrr@{}}" + "\n"
        + r"\toprule" + "\n"
        + r"Period & $n$ & Frequency & Fixed-step & Adopted & Accuracy (\%) & Bias (pp) \\" + "\n"
        + r"\midrule" + "\n" + "\n".join(lines) + "\n"
        + r"\bottomrule" + "\n" + r"\end{tabular*}" + "\n",
        encoding="utf-8", newline="\n")

    source = BASE / "study_prematch_features.csv"
    teams = {"Brazil": "team:brazil", "France": "team:france",
             "Spain": "team:spain", "Japan": "team:japan"}
    selected = {name: {} for name in teams}
    resolved = {name: set() for name in teams}
    with source.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            for role in ("home", "away"):
                for name, prefix in teams.items():
                    if row[role].split("@")[0] != prefix:
                        continue
                    resolved[name].add(row[role])
                    year = int(row["date"][:4])
                    candidate = dict(date=row["date"], match_id=row["match_id"], role=role,
                                     team_id=row[role], mean=float(row[f"{role}_mean"]),
                                     sd=math.sqrt(float(row[f"{role}_variance"])))
                    previous = selected[name].get(year)
                    # Deterministic selection if multiple games share the date.
                    if previous is None or (candidate["date"], candidate["match_id"]) > (previous["date"], previous["match_id"]):
                        selected[name][year] = candidate
    assert all(len(ids) == 1 for ids in resolved.values()), resolved
    assert all(len(years) >= 40 for years in selected.values())
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "pdf.fonttype": 42})
    fig, axes = plt.subplots(2, 2, figsize=(9.3, 5.5), sharex=True, sharey=True)
    for ax, (name, years) in zip(axes.flat, selected.items()):
        points = [years[y] for y in sorted(years)]
        x = [int(p["date"][:4]) for p in points]
        ax.errorbar(x, [p["mean"] for p in points], yerr=[p["sd"] for p in points],
                    fmt="o", ms=2.8, color="#17547e", ecolor="#9eb8ca",
                    elinewidth=.8, capsize=1.5)
        ax.axhline(0, color="#999999", linewidth=.6, linestyle=":")
        ax.set_title(name, loc="left", fontweight="bold")
        ax.grid(axis="y", alpha=.18)
        ax.set_xticks([1980, 1990, 2000, 2010, 2020])
    for ax in axes[:, 0]:
        ax.set_ylabel("Pre-match latent strength")
    for ax in axes[-1, :]:
        ax.set_xlabel("Match year (one selected date per year)")
    fig.tight_layout()
    outputs = [rows_path]
    for suffix in ("pdf", "png"):
        path = PAPER / f"figures/fig_strength_states.{suffix}"
        fig.savefig(path, dpi=180, bbox_inches="tight")
        outputs.append(path)
    plt.close(fig)
    manifest = dict(
        purpose="Presentation of existing adopted rating states and three-class checks; no new model run",
        sources={p.relative_to(ROOT).as_posix(): sha(p) for p in (source, report_path, composition_path)},
        selectors=dict(scope="accepted_study", periods=periods,
                       trajectories="Latest comparative-cohort pre-match date per team/year; match_id tie-break; both roles"),
        strength_units="Unit performance-noise scale; not FIFA/Elo points or known true ability",
        uncertainty="Whiskers: marginal mean +/- one SD (including jump variance), not confidence or quantile intervals",
        historical_reuse=True,
        composition_losses_on_24917_study_matches=composition_scores,
        checks=checks,
        plotted_points={name: [years[y] for y in sorted(years)] for name, years in selected.items()},
        outputs={p.relative_to(ROOT).as_posix(): sha(p) for p in outputs})
    (PAPER / "strength_evidence_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"matches": sum(r["count"] for r in checks),
                      "selected_dates": {k: len(v) for k, v in selected.items()},
                      "outputs": [p.relative_to(ROOT).as_posix() for p in outputs]}))


if __name__ == "__main__":
    main()
