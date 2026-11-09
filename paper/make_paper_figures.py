"""Generate draft English figures for the course paper.

Usage (from the repository root):
    python paper/make_paper_figures.py
    python paper/make_paper_figures.py --outdir paper/figures

The script reads only the adopted result CSVs listed below and writes PDF/PNG
files. It does not rerun models or change any research output. The generated
figures are draft candidates; final selection, captions, and source registration
remain a writing task.

Generated:
    fig2_era_rates.pdf/.png
    fig3_model_comparison.pdf/.png
    fig4_history_windows.pdf/.png
    fig5_regional_metrics.pdf/.png
    fig6_forecast_examples.pdf/.png

Not generated here (manual/agent task):
    fig1_study_design  (flow diagram; TikZ/PPT recommended)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]

ERAS = ROOT / "outputs/tables/eras/eras-fifa-dddf11dd6dc0b7531b88/era_estimates.csv"
ERA_SUMMARY = ROOT / "outputs/tables/eras/eras-fifa-dddf11dd6dc0b7531b88/era_summary.csv"
Q5_YEARLY = ROOT / "outputs/tables/strength_joint/rolling-prediction-4722c7b1b5f63cef35e3/yearly_metrics.csv"
Q6_COMBINATIONS = ROOT / "outputs/tables/history_window/joint-review-4888d987645daee73e19/combination_metrics.csv"
Q6_COSTS = ROOT / "outputs/tables/history_window/joint-review-4888d987645daee73e19/cost_components.csv"
Q7_REGIONAL = ROOT / "outputs/tables/regional_effectiveness/regional-evaluation-7ea3e4ab7c7dbb8eeb58/regional_metrics.csv"
Q8_FORECASTS = ROOT / "outputs/tables/future_predictions/future-unl-61f639846da9193d4cca/forecasts.csv"

ERA_ORDER = ["1980s", "1990s", "2000s", "2010s", "2020_2024"]
ERA_LABELS = {
    "1980s": "1980–1989",
    "1990s": "1990–1999",
    "2000s": "2000–2009",
    "2010s": "2010–2019",
    "2020_2024": "2020–2024\n(5 years)",
}
MODEL_LABELS = {
    "M0_nested": "Background only",
    "M1_strength": "Strength only",
    "M3_nested": "Strength + context",
}
COMBO_LABELS = {
    "annual_reset_20y__outcome_12y": "20y / 12y",
    "annual_reset_20y__outcome_cumulative": "20y / all",
    "annual_reset_12y__outcome_12y": "12y / 12y",
    "annual_reset_12y__outcome_cumulative": "12y / all",
    "cumulative_1950__outcome_12y": "all / 12y",
    "cumulative_1950__outcome_cumulative": "all / all",
}
REGION_LABELS = {
    "ALL": "Overall",
    "150": "Europe",
    "142": "Asia",
    "002": "Africa",
    "019": "Americas",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "figure.dpi": 120,
            "savefig.dpi": 220,
            "savefig.bbox": "tight",
        }
    )


def save(fig: plt.Figure, outdir: Path, stem: str) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(outdir / f"{stem}.pdf")
    fig.savefig(outdir / f"{stem}.png")
    plt.close(fig)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fig2_era_rates(outdir: Path) -> None:
    estimates = read_rows(ERAS)
    summary = read_rows(ERA_SUMMARY)
    reference = "reference-90003d0bdb8d6f65cead"
    observed = {
        row["analysis_era_id"]: float(row["estimate"])
        for row in estimates
        if row["reference_id"] == reference and row["estimand"] == "observed_rate"
    }
    adjusted = {
        row["analysis_era_id"]: float(row["estimate"])
        for row in estimates
        if row["reference_id"] == reference and row["estimand"] == "standardized_rate"
    }
    counts = {
        row["period_id"]: int(row["n_matches"])
        for row in summary
        if row["sample_name"] == "base_venue"
    }

    x = np.arange(len(ERA_ORDER))
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.plot(x, [100 * observed[era] for era in ERA_ORDER], marker="o", label="Observed")
    ax.plot(
        x,
        [100 * adjusted[era] for era in ERA_ORDER],
        marker="s",
        label="Common-composition adjusted",
    )
    ax.set_xticks(x)
    ax.set_xticklabels([ERA_LABELS[era] for era in ERA_ORDER])
    ax.set_ylabel("Home-win rate (%)")
    ax.set_title("Home-win rate by era, non-neutral matches")
    ax.legend(loc="upper left", frameon=False)
    ax.set_ylim(48.8, 52.4)
    for i, era in enumerate(ERA_ORDER):
        ax.annotate(
            f"n={counts[era]:,}",
            (i, 49.0),
            ha="center",
            va="bottom",
            fontsize=8,
            color="#555555",
        )
    save(fig, outdir, "fig2_era_rates")


def fig3_model_comparison(outdir: Path) -> None:
    rows = read_rows(Q5_YEARLY)
    metrics = {}
    for model in MODEL_LABELS:
        selected = [row for row in rows if row["model_id"] == model]
        n = sum(int(row["matches"]) for row in selected)
        metrics[model] = {
            "n": n,
            "log_loss": sum(float(row["log_loss"]) * int(row["matches"]) for row in selected) / n,
            "accuracy": 100
            * sum(float(row["binary_accuracy"]) * int(row["matches"]) for row in selected)
            / n,
        }

    models = list(MODEL_LABELS)
    labels = [MODEL_LABELS[model].replace(" only", "\nonly").replace(" + ", " +\n") for model in models]
    x = np.arange(len(models))
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.4))

    losses = [metrics[model]["log_loss"] for model in models]
    bars = axes[0].bar(x, losses, color=["#8c9aa6", "#5b7f95", "#1f5c78"], width=0.62)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=0, ha="center")
    axes[0].set_ylabel("Mean log loss (lower is better)")
    axes[0].set_ylim(0.50, 0.70)
    axes[0].set_title("Probability quality")
    for bar, value in zip(bars, losses):
        axes[0].annotate(f"{value:.4f}", (bar.get_x() + bar.get_width() / 2, value),
                         ha="center", va="bottom", fontsize=8)

    accuracies = [metrics[model]["accuracy"] for model in models]
    bars = axes[1].bar(x, accuracies, color=["#8c9aa6", "#5b7f95", "#1f5c78"], width=0.62)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=0, ha="center")
    axes[1].set_ylabel("Binary accuracy (%)")
    axes[1].set_ylim(50, 75)
    axes[1].set_title("Home-win / non-home accuracy")
    for bar, value in zip(bars, accuracies):
        axes[1].annotate(f"{value:.2f}%", (bar.get_x() + bar.get_width() / 2, value),
                         ha="center", va="bottom", fontsize=8)

    fig.tight_layout()
    save(fig, outdir, "fig3_model_comparison")


def fig4_history_windows(outdir: Path) -> None:
    metrics = {
        row["combination_id"]: row
        for row in read_rows(Q6_COMBINATIONS)
        if row["scope"] == "evaluation"
    }
    costs = {row["combination_id"]: row for row in read_rows(Q6_COSTS)}
    order = list(COMBO_LABELS)
    labels = [COMBO_LABELS[key] for key in order]
    losses = [float(metrics[key]["primary_log_loss"]) for key in order]
    seconds = [float(costs[key]["outcome_job_seconds"]) for key in order]
    baseline = float(metrics["cumulative_1950__outcome_cumulative"]["primary_log_loss"])

    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.6))
    x = np.arange(len(order))
    axes[0].plot(x, losses, marker="o", color="#1f5c78")
    axes[0].axhline(baseline, color="#888888", linestyle="--", linewidth=1,
                    label="Cumulative / cumulative")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=25, ha="right")
    axes[0].set_ylabel("Mean log loss")
    axes[0].set_title("Evaluation performance (9,727 matches)")
    axes[0].set_ylim(0.5585, 0.5625)
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")

    axes[1].bar(x, seconds, color="#5b7f95", width=0.62)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=25, ha="right")
    axes[1].set_ylabel("Outcome-training time (s)")
    axes[1].set_title("Cost of the outcome-training component")
    for i, value in enumerate(seconds):
        axes[1].annotate(f"{value:.0f}", (i, value), ha="center", va="bottom", fontsize=8)

    save(fig, outdir, "fig4_history_windows")


def fig5_regional_metrics(outdir: Path) -> None:
    rows = read_rows(Q7_REGIONAL)
    groups = ["ALL", "150", "142", "002", "019"]
    data = {}
    for group in groups:
        for model in ("joint", "strength"):
            selected = [
                row
                for row in rows
                if row["scope"] == "main" and row["group"] == group and row["model"] == model
            ]
            if selected:
                data[(group, model)] = selected[0]

    x = np.arange(len(groups))
    width = 0.36
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.8))

    joint_loss = [float(data[(group, "joint")]["log_loss"]) for group in groups]
    strength_loss = [float(data[(group, "strength")]["log_loss"]) for group in groups]
    axes[0].bar(x - width / 2, strength_loss, width, label="Strength only", color="#8c9aa6")
    axes[0].bar(x + width / 2, joint_loss, width, label="Strength + context", color="#1f5c78")
    tick_labels = [REGION_LABELS[group] for group in groups]
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(tick_labels)
    axes[0].set_ylabel("Mean log loss")
    axes[0].set_title("Probability quality")
    axes[0].legend(frameon=False, fontsize=8)

    joint_bias = [float(data[(group, "joint")]["bias_pp"]) for group in groups]
    strength_bias = [float(data[(group, "strength")]["bias_pp"]) for group in groups]
    axes[1].bar(x - width / 2, strength_bias, width, label="Strength only", color="#8c9aa6")
    axes[1].bar(x + width / 2, joint_bias, width, label="Strength + context", color="#1f5c78")
    axes[1].axhline(0, color="#333333", linewidth=1)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(tick_labels)
    axes[1].set_ylabel("Mean predicted − observed (pp)")
    axes[1].set_title("Calibration bias")
    axes[1].legend(frameon=False, fontsize=8)

    counts = {group: int(data[(group, "joint")]["matches"]) for group in groups}
    save(fig, outdir, "fig5_regional_metrics")


def fig6_forecast_examples(outdir: Path) -> None:
    rows = read_rows(Q8_FORECASTS)
    by_pair = {(row["home_team"], row["away_team"]): row for row in rows}
    cases = [
        ("Czech Republic", "Spain", "12 Nov"),
        ("Netherlands", "Greece", "13 Nov"),
        ("England", "Croatia", "12 Nov"),
    ]
    selected = [by_pair[(home, away)] for home, away, _ in cases]

    fig, axes = plt.subplots(
        1, 2, figsize=(9.0, 3.4), gridspec_kw={"width_ratios": [1.7, 1.0]}
    )

    probabilities = [100 * float(row["main_home_probability"]) for row in selected]
    lower = [
        probability - 100 * float(row["latent_probability_p05"])
        for probability, row in zip(probabilities, selected)
    ]
    upper = [
        100 * float(row["latent_probability_p95"]) - probability
        for probability, row in zip(probabilities, selected)
    ]
    y = np.arange(len(selected))
    axes[0].errorbar(
        probabilities,
        y,
        xerr=[lower, upper],
        fmt="o",
        color="#1f5c78",
        ecolor="#5b7f95",
        elinewidth=2,
        capsize=4,
    )
    axes[0].axvline(50, color="#888888", linestyle="--", linewidth=1)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(
        [f"{home}–{away}\n{date}" for home, away, date in cases]
    )
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, 100)
    axes[0].set_xlabel("Home-win probability (%)")
    axes[0].set_title("Main binary model")
    for i, probability in enumerate(probabilities):
        axes[0].annotate(
            f"{probability:.1f}%",
            (probability, i),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    ukraine = by_pair[("Ukraine", "Georgia")]
    labels = ["Home win", "Draw", "Away win"]
    values = [
        100 * float(ukraine["native_home_probability"]),
        100 * float(ukraine["native_draw_probability"]),
        100 * float(ukraine["native_away_probability"]),
    ]
    bars = axes[1].bar(labels, values, color=["#1f5c78", "#8c9aa6", "#b4602b"], width=0.62)
    axes[1].set_ylim(0, 100)
    axes[1].set_ylabel("Probability (%)")
    axes[1].set_title("Ukraine–Georgia\n(auxiliary three-class)")
    for bar, value in zip(bars, values):
        axes[1].annotate(
            f"{value:.1f}%",
            (bar.get_x() + bar.get_width() / 2, value),
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.tight_layout()
    save(fig, outdir, "fig6_forecast_examples")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "paper/figures",
        help="output directory (default: paper/figures)",
    )
    args = parser.parse_args()
    outdir = args.outdir if args.outdir.is_absolute() else ROOT / args.outdir

    style()
    fig2_era_rates(outdir)
    fig3_model_comparison(outdir)
    fig4_history_windows(outdir)
    fig5_regional_metrics(outdir)
    fig6_forecast_examples(outdir)

    sources = {
        "fig2_era_rates": [ERAS, ERA_SUMMARY],
        "fig3_model_comparison": [Q5_YEARLY],
        "fig4_history_windows": [Q6_COMBINATIONS, Q6_COSTS],
        "fig5_regional_metrics": [Q7_REGIONAL],
        "fig6_forecast_examples": [Q8_FORECASTS],
    }
    manifest = {
        "status": "draft_candidates_not_final_selection",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "paper/make_paper_figures.py",
        "generator_sha256": sha256(Path(__file__)),
        "figures": [
            {
                "stem": stem,
                "pdf": {"path": f"paper/figures/{stem}.pdf", "sha256": sha256(outdir / f"{stem}.pdf")},
                "png": {"path": f"paper/figures/{stem}.png", "sha256": sha256(outdir / f"{stem}.png")},
                "sources": [str(path.relative_to(ROOT)).replace("\\", "/") for path in paths],
            }
            for stem, paths in sources.items()
        ],
        "manual_tasks": ["fig1_study_design"],
    }
    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Generated draft English figures:")
    for item in manifest["figures"]:
        print(f"  {outdir / (item['stem'] + '.pdf')}")
        print(f"  {outdir / (item['stem'] + '.png')}")
    print(f"  {manifest_path}")
    print("Manual/agent task remains: fig1_study_design.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
