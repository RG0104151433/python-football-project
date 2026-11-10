"""Build an offline presentation from adopted results, without refitting models.

Static figure style adapts figures4papers (Chen Liu), CC BY-NC 4.0.
The inspected upstream mark_events function is actually called on project data.
The HTML animation layer is original local SVG/JavaScript, not an upstream API.
"""
from pathlib import Path
import base64
import csv
import hashlib
import importlib.util
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor/figures4papers/b709de17da7e"
ASSETS = HERE / "assets"
SOURCES = {
    "eras": "outputs/tables/eras/eras-fifa-dddf11dd6dc0b7531b88/era_estimates.csv",
    "counts": "outputs/tables/eras/eras-fifa-dddf11dd6dc0b7531b88/era_summary.csv",
    "types": "outputs/tables/tournaments/tournaments-4893e38db46f83f6c219/type_differences.csv",
    "regions": "outputs/tables/regions/regions-0a1c61664a722e6c641f/contrast_results.csv",
    "yearly": "outputs/tables/strength_joint/rolling-prediction-4722c7b1b5f63cef35e3/yearly_metrics.csv",
    "windows": "outputs/tables/history_window/joint-review-4888d987645daee73e19/combination_metrics.csv",
    "costs": "outputs/tables/history_window/joint-review-4888d987645daee73e19/cost_components.csv",
    "regional": "outputs/tables/regional_effectiveness/regional-evaluation-7ea3e4ab7c7dbb8eeb58/regional_metrics.csv",
    "forecasts": "outputs/tables/future_predictions/future-unl-61f639846da9193d4cca/forecasts.csv",
    "states": "paper/strength_evidence_manifest.json",
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows(key):
    with (ROOT / SOURCES[key]).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def data():
    models = []
    for mid, label in [("M0_nested", "Background only"), ("M1_strength", "Strength only"), ("M3_nested", "Strength + context")]:
        rs = [r for r in rows("yearly") if r["model_id"] == mid]
        n = sum(int(r["matches"]) for r in rs)
        assert n == 21413
        models.append(dict(id=mid, name=label, n=n,
            loss=sum(float(r["log_loss"]) * int(r["matches"]) for r in rs) / n,
            accuracy=100 * sum(float(r["binary_accuracy"]) * int(r["matches"]) for r in rs) / n))
    era_ids = ["1980s", "1990s", "2000s", "2010s", "2020_2024"]
    era_rows = [r for r in rows("eras") if r["reference_id"] == "reference-90003d0bdb8d6f65cead"]
    eras = []
    for eid in era_ids:
        rs = {r["estimand"]: r for r in era_rows if r["analysis_era_id"] == eid}
        count = next(r for r in rows("counts") if r["sample_name"] == "base_venue" and r["period_id"] == eid)
        eras.append(dict(label=eid.replace("2020_2024", "2020–24"), n=int(count["n_matches"]),
                         direct=100*float(rs["observed_rate"]["estimate"]), adjusted=100*float(rs["standardized_rate"]["estimate"])))
    assert sum(x["n"] for x in eras) == 24917
    contrast_names = {"B_ASIA": "Asia: external − same subregion", "B_EUR": "Europe: external − same subregion",
                      "C_AFR_015_VS_011": "Africa: North − West", "C_AMER_FOCUS": "Americas: South − rest"}
    contrasts = [dict(id=r["contrast_id"], name=contrast_names[r["contrast_id"]],
                     direct=float(r["direct_difference_pp"]), adjusted=float(r["adjusted_difference_pp"]))
                 for r in rows("regions") if r["contrast_id"] in contrast_names]
    combos = [dict(id=r["combination_id"], label=r["combination_id"].replace("annual_reset_", "").replace("cumulative_1950", "all").replace("__outcome_", " / ").replace("cumulative", "all"),
                   loss=float(r["primary_log_loss"])) for r in rows("windows") if r["scope"] == "evaluation"]
    assert len(combos) == 6 and len(contrasts) == 4
    costs = {r["combination_id"]: float(r["outcome_job_seconds"]) for r in rows("costs")
             if r["rating_policy"] == "cumulative_1950"}
    region_names = {"150": "Europe", "142": "Asia", "002": "Africa", "019": "Americas", "009": "Oceania"}
    regional = []
    for group, label in region_names.items():
        rs = {r["model"]: r for r in rows("regional") if r["scope"] == "main" and r["group"] == group}
        regional.append(dict(name=label, n=int(rs["joint"]["matches"]), strength=float(rs["strength"]["log_loss"]),
                             joint=float(rs["joint"]["log_loss"]), bias=float(rs["joint"]["bias_pp"])))
    assert sum(x["n"] for x in regional) == 9727
    forecasts = []
    for r in rows("forecasts"):
        def num(k):
            return float(r[k]) if r[k] else None
        forecasts.append(dict(id=r["match_id"], date=r["date"], home=r["home_team"], away=r["away_team"], status=r["main_status"],
                              p=num("main_home_probability"), lo=num("latent_probability_p05"), hi=num("latent_probability_p95"),
                              native=[num("native_home_probability"), num("native_draw_probability"), num("native_away_probability")]))
    assert len(forecasts) == 52 and sum(x["p"] is not None for x in forecasts) == 49
    states = json.loads((ROOT / SOURCES["states"]).read_text(encoding="utf-8"))
    for path, expected in states["sources"].items():
        assert sha(ROOT / path) == expected, path
    type_gap = {r["estimand"]: float(r["estimate"]) for r in rows("types") if r["scope"] == "overall"}
    return dict(models=models, eras=eras, contrasts=contrasts, typeGap=type_gap, windows=combos, costs=costs,
                regional=regional, forecasts=forecasts, states=states["plotted_points"],
                sourceFiles=SOURCES, vendorCommit="b709de17da7e8f9a72e51a5de5bced924a01eeab")


def static_figures(d):
    # Adapted typography/palette/export conventions; no fabricated error bars.
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 15,
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 1.4,
        "svg.fonttype": "none", "pdf.fonttype": 42, "legend.frameon": False})
    colors = ["#9b7772", "#42949E", "#0F4D92"]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.8), layout="constrained")
    for i, m in enumerate(d["models"]):
        axes[0].barh(i, m["loss"], color=colors[i], height=.5)
        axes[0].text(m["loss"]+.009, i, f'{m["loss"]:.6f}', va="center", fontsize=13)
        axes[1].scatter(m["accuracy"], i, s=160, color=colors[i], zorder=3)
        axes[1].text(m["accuracy"]+2, i, f'{m["accuracy"]:.2f}%', va="center", fontsize=13)
    for ax in axes:
        ax.set_yticks(range(3), [m["name"] for m in d["models"]]); ax.invert_yaxis(); ax.grid(axis="x", alpha=.15); ax.set_axisbelow(True)
    axes[0].set_xlim(0,.77);axes[0].set_xlabel("Mean log loss · lower is better");axes[0].set_title("Probability quality",loc="left",fontweight="bold")
    axes[1].set_xlim(0,100);axes[1].set_xlabel("Home-win / non-home-win accuracy (%)");axes[1].set_title("Binary decisions",loc="left",fontweight="bold")
    fig.suptitle("Strength contributes the larger historical improvement", fontsize=20, fontweight="bold")
    fig.supxlabel("Same 21,413 matches, 1990–2024 · retrospective reuse · no real-data loss-difference interval", fontsize=11)
    save(fig, "model_comparison")
    # Real function-level use of the inspected upstream Python script.
    upstream = VENDOR / "figure_ophthal_review/plot_trend.py"
    spec = importlib.util.spec_from_file_location("figures4papers_trend", upstream)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    fig, axes = plt.subplots(2, 2, figsize=(13.5,8), sharey=True, layout="constrained")
    for ax, (name, points) in zip(axes.flat, d["states"].items()):
        years = [p["date"][:4] for p in points]
        x = np.array([int(year)-1980 for year in years])
        means = np.array([p["mean"] for p in points]); sd = np.array([p["sd"] for p in points])
        ax.errorbar(x, means, yerr=sd, fmt="o", color="#0F4D92", ecolor="#a7bdcf", ms=3, capsize=2, lw=1)
        ax.set_xticks([0,10,20,30,44], ["1980","1990","2000","2010","2024"])
        ax.set_xlim(-1,45)
        ax.set_title(name,loc="left",fontweight="bold");ax.set_ylim(-1.5,7);ax.axhline(0,color="#aaa",lw=.8);ax.grid(axis="y",alpha=.15)
        if name == "Japan":
            calendar = [str(year) for year in range(1980,2025)]
            lookup = dict(zip(years, means))
            calendar_means = np.array([lookup.get(year, np.nan) for year in calendar])
            module.mark_events(ax, calendar, calendar_means, {"2010":"Main regional\ncomparison begins"}, dy=.08)
    for ax in axes[:,0]:ax.set_ylabel("Latent strength")
    for ax in axes[-1,:]:ax.set_xlabel("Selected pre-match year")
    fig.suptitle("Ability changes; uncertainty remains part of the estimate",fontsize=20,fontweight="bold")
    fig.supxlabel("Latest eligible match per team/year, both roles · mean ±1 SD, not a confidence interval or true-strength label",fontsize=11)
    save(fig, "strength_trajectories")


def save(fig, name):
    for fmt in ["svg", "png", "pdf"]:
        fig.savefig(ASSETS / f"{name}.{fmt}", dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def image_data(path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    d = data(); static_figures(d)
    (ASSETS / "presentation_data.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    template = (HERE / "deck.template.html").read_text(encoding="utf-8")
    (HERE / "index.html").write_text(template.replace("__PRESENTATION_DATA__", json.dumps(d, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    comparisons = [("Same-match predictor comparison", "fig3_model_comparison.png", "model_comparison.png"),
                   ("Archived strength estimates", "fig_strength_states.png", "strength_trajectories.png")]
    chunks=[]
    for title, old, new in comparisons:
        chunks.append(f'<h2>{title}</h2><div class="pair"><figure><figcaption>Existing paper figure — preserved</figcaption><img src="{image_data(ROOT/"paper/figures"/old)}" alt="Existing paper chart"></figure><figure><figcaption>figures4papers-style candidate</figcaption><img src="{image_data(ASSETS/new)}" alt="New candidate chart"></figure></div>')
    compare='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Figure comparison</title><style>body{font:18px/1.5 'Segoe UI',sans-serif;background:#f4f2eb;color:#172c3d;margin:35px}h1{max-width:900px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0;background:white;padding:16px}img{width:100%}a{color:#0F4D92}@media(max-width:850px){.pair{grid-template-columns:1fr}}</style><h1>Alternative figures, identical research evidence.</h1><p>Candidate exports adapt Chen Liu's figures4papers conventions (CC BY-NC 4.0). The upstream mark_events helper is actually called on the strength panel. The full-zero loss/accuracy scales replace the original truncated comparison bars; labels are larger and editable SVG/PDF exports are available. No new uncertainty ranges or performance claims are added. Presentation suitability is an editorial judgement, not an objective quality score.</p>'''+''.join(chunks)+'''<p><a href="index.html">Open the interactive presentation</a> · <a href="https://github.com/ChenLiu-1996/figures4papers">Upstream project and attribution</a>. The paper and existing submission archives have not been replaced.</p></html>'''
    (HERE / "figure_comparison.html").write_text(compare, encoding="utf-8")
    manifest={"decision_log_id":"R20261108-07","purpose":"first offline interactive English presentation draft; no research refit",
        "sources":{s:sha(ROOT/s) for s in SOURCES.values()},"vendor_commit":d["vendorCommit"],
        "upstream_function_called":"figure_ophthal_review.plot_trend.mark_events", "source_license":"CC-BY-NC-4.0",
        "web_animation_implementation":"local original SVG/JavaScript; not an upstream interactive API",
        "outputs":{p.relative_to(ROOT).as_posix():sha(p) for p in [HERE/"index.html",HERE/"figure_comparison.html",*sorted(ASSETS.glob('*'))]},
        "paper_and_submission_archives_replaced":False,"model_recomputed":False}
    (HERE / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Built offline deck, two real-data figure candidates (SVG/PNG/PDF), and comparison page.")


if __name__ == "__main__":
    import runpy
    runpy.run_path(str(HERE / "build_v5.py"), run_name="__main__")
