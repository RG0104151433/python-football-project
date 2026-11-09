"""Render adopted Q1--Q3 tables for the paper; do not refit any research model.

Run from the repository root: python paper/make_historical_overview.py
Only the overview PDF/PNG and its figure provenance record are written.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "eras": "outputs/tables/eras/eras-fifa-dddf11dd6dc0b7531b88/era_estimates.csv",
    "era_counts": "outputs/tables/eras/eras-fifa-dddf11dd6dc0b7531b88/era_summary.csv",
    "types": "outputs/tables/tournaments/tournaments-4893e38db46f83f6c219/type_differences.csv",
    "regions": "outputs/tables/regions/regions-0a1c61664a722e6c641f/contrast_results.csv",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(key: str) -> list[dict[str, str]]:
    with (ROOT / SOURCES[key]).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    eras = ["1980s", "1990s", "2000s", "2010s", "2020_2024"]
    rates = [r for r in rows("eras") if r["reference_id"] == "reference-90003d0bdb8d6f65cead"]
    counts = {r["period_id"]: int(r["n_matches"]) for r in rows("era_counts") if r["sample_name"] == "base_venue"}
    rolling = sorted([r for r in rows("types") if r["scope"] == "rolling" and r["estimand"] == "raw"], key=lambda r: r["period_id"])
    regional = {r["contrast_id"]: r for r in rows("regions")}
    selected_ids = ["B_ASIA", "B_EUR", "C_AFR_015_VS_011", "C_AMER_FOCUS"]
    selected = [regional[k] for k in selected_ids]
    assert len(rolling) == 36 and sum(counts[e] for e in eras) == 24917
    assert all(r["adjusted_status"] == "ok" for r in selected)
    assert all(sum(r["analysis_era_id"] == e and r["estimand"] == est for r in rates) == 1 for e in eras for est in ["observed_rate", "standardized_rate"])

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    fig = plt.figure(figsize=(7.0, 5.5), layout="constrained")
    grid = fig.add_gridspec(2, 2, height_ratios=[1.05, 1.0], hspace=0.12)
    a = fig.add_subplot(grid[0, 0]); b = fig.add_subplot(grid[0, 1]); c = fig.add_subplot(grid[1, :])
    colors = ["#788e9c", "#165e79"]
    x = np.arange(5)
    for est, label, marker, color in zip(["observed_rate", "standardized_rate"], ["Direct", "Adjusted"], ["o", "s"], colors):
        values = {r["analysis_era_id"]: 100 * float(r["estimate"]) for r in rates if r["estimand"] == est}
        a.plot(x, [values[e] for e in eras], marker=marker, label=label, color=color, linewidth=1.4, markersize=4)
    a.set_xticks(x, ["1980s", "1990s", "2000s", "2010s", "2020–2024"])
    a.tick_params(axis="x", labelsize=7)
    a.set_xlim(-0.35, 4.55)
    a.set_title("A  Era rates (zoomed scale)", loc="left")
    a.set_ylabel("Home-win rate (%)")
    a.legend(frameon=False, fontsize=8, loc="upper left")
    a.grid(axis="y", alpha=.22)
    years = [int(r["period_id"].split("_")[1]) for r in rolling]
    b.plot(years, [float(r["estimate"]) for r in rolling], color=colors[1], linewidth=1.6)
    b.axhline(0, color="#777777", linewidth=.8, linestyle="--")
    b.set_title("B  Friendly minus other matches", loc="left")
    b.set_xlabel("Ten-year window ending in")
    b.set_ylabel("Home-win difference (pp)")
    b.set_xticks([1989, 2000, 2010, 2024]); b.grid(axis="y", alpha=.22)
    labels = ["Asia:\nexternal − same subregion", "Europe:\nexternal − same subregion",
              "Africa:\nNorth Africa − West Africa", "Americas:\nSouth America − rest"]
    y = np.arange(4)
    for offset, key, marker, color, label in [(-.10, "direct_difference_pp", "o", colors[0], "Direct"), (.10, "adjusted_difference_pp", "D", colors[1], "Adjusted")]:
        c.scatter([float(r[key]) for r in selected], y + offset, s=28, marker=marker, color=color, label=label, zorder=3)
    c.set_yticks(y, labels, fontsize=9)
    c.invert_yaxis(); c.axvline(0, color="#777777", linewidth=.8, linestyle="--")
    c.set_xlim(-20, 24); c.set_xlabel("Home-win difference (percentage points)")
    c.set_title("C  Selected regional contrasts (different references)", loc="left")
    c.grid(axis="x", alpha=.22); c.legend(frameon=False, fontsize=8, loc="lower right")
    outdir = ROOT / "paper/figures"; stem = outdir / "fig_historical_overview"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), dpi=200, bbox_inches="tight")
    plt.close(fig)
    outputs = [stem.with_suffix(ext) for ext in [".pdf", ".png"]]
    manifest = {
        "decision_log_id": "R20261107-03", "executor": "Codex (AI)", "human_review": False,
        "purpose": "Render existing adopted historical results, not a new analysis or interval estimate",
        "sources": {p: sha(ROOT / p) for p in SOURCES.values()},
        "selected_rows": {"era_rates": rates, "rolling_raw_differences": rolling, "regional_contrasts": selected},
        "era_counts": {e: counts[e] for e in eras}, "sample_matches": 24917,
        "outputs": {p.relative_to(ROOT).as_posix(): sha(p) for p in outputs},
        "script_sha256": sha(Path(__file__)),
        "limits": ["Descriptive rates and differences; no confidence intervals drawn", "36 windows overlap", "Four regional contrasts use distinct references; not a ranking", "Full outputs are in SUPPORTING_RESULTS.md"]}
    (ROOT / "paper/historical_overview_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Historical overview rendered: 5 eras, 36 windows, 4 representative regional contrasts.")


if __name__ == "__main__":
    main()
