"""Run the frozen small strength experiment, not global rating production."""
from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
import time
from collections import defaultdict
from datetime import date, timedelta

import numpy as np
from scipy.special import ndtr, expit

from ..data_contract import file_hash, fingerprint, write_json
from .filter import StrengthFilter, batch_update, joint_quadrature, NumericalFailure
from .io import ROOT, config, publish, read_rows
from .prepare import run as prepare


def params(cfg, candidate):
    return {**cfg["pilot"]["base"], **{k: v for k, v in candidate.items() if k != "id"}}


def score(rows):
    if not rows:
        return {"count": 0, "accuracy": None, "log_loss": None, "brier": None}
    p = np.array([[r["p_home"], r["p_draw"], r["p_away"]] for r in rows])
    y = np.array([r["outcome_index"] for r in rows])
    if not np.isfinite(p).all() or p.min() < 0 or np.max(abs(p.sum(axis=1) - 1)) > 1e-9:
        raise NumericalFailure("Invalid prediction probabilities")
    return {"count": len(rows), "accuracy": float(np.mean(np.argmax(p, axis=1) == y)),
            "log_loss": float(-np.log(p[np.arange(len(y)), y]).mean()),
            "brier": float(np.mean(np.sum((p - np.eye(3)[y])**2, axis=1)))}


def calibration(rows, model):
    bins = []
    for c, name in enumerate(("home", "draw", "away")):
        for b in range(5):
            subset = [r for r in rows if min(4, int(r["p_" + name] * 5)) == b]
            bins.append({"model": model, "outcome": name, "bin": b, "count": len(subset),
                         "mean_probability": sum(r["p_" + name] for r in subset) / len(subset) if subset else None,
                         "observed_frequency": sum(r["outcome_index"] == c for r in subset) / len(subset) if subset else None})
    return bins


def stream(games, cfg, parameters, start=1950, variance=None, numerical=None):
    teams = {g[k] for g in games for k in ("home", "away")}
    engine = StrengthFilter(teams, parameters, numerical or cfg["numerics"],
                            variance or cfg["pilot"]["initial_team_variance"],
                            cfg["pilot"]["initial_home_variance"])
    grouped = defaultdict(list)
    for g in games:
        if int(g["date"][:4]) >= start:
            grouped[g["date"]].append(g)
    forecasts = []
    for day, batch in sorted(grouped.items()):
        forecasts.extend(engine.day(day, batch))
    return forecasts, engine


def baseline(games):
    """Past-only Dirichlet-smoothed W/D/L baseline; common validation population."""
    groups = defaultdict(list)
    for g in games:
        groups[g["date"]].append(g)
    counts = np.ones(3)
    result = []
    for day, batch in sorted(groups.items()):
        for g in sorted(batch, key=lambda r: r["match_id"]):
            p = counts / counts.sum()
            result.append({"match_id": g["match_id"], "date": day, "outcome_index": g["outcome"],
                           "p_home": float(p[0]), "p_draw": float(p[1]), "p_away": float(p[2])})
        for g in batch:
            counts[g["outcome"]] += 1
    return result


def numerical_checks(cfg):
    p = params(cfg, {"id": "both"})
    engine = StrengthFilter(["A", "B", "C"], p, cfg["numerics"])
    m, c = engine.components[0].mean, engine.components[0].cov
    games = [{"match_id": "a", "home": "A", "away": "B", "venue": 1},
             {"match_id": "b", "home": "C", "away": "A", "venue": 0}]
    a = engine.design(games)
    records = []
    for outcomes in itertools.product(range(3), repeat=2):
        em, ec, ez, _ = batch_update(m, c, a, outcomes, [0.95, 0.62], p["delta"], cfg["numerics"])
        rm, rc, rz = joint_quadrature(m, c, a, outcomes, [0.95, 0.62], p["delta"], 35)
        rm2, rc2, rz2 = joint_quadrature(m, c, a, outcomes, [0.95, 0.62], p["delta"], 55)
        pred_ep = ndtr((em[0] - em[1] - p["delta"]) / math.sqrt(1 + ec[0, 0] + ec[1, 1] - 2 * ec[0, 1]))
        pred_ref = ndtr((rm2[0] - rm2[1] - p["delta"]) / math.sqrt(1 + rc2[0, 0] + rc2[1, 1] - 2 * rc2[0, 1]))
        records.append({"outcomes": list(outcomes), "mean_max_error": float(np.max(abs(em - rm2))),
                        "cov_max_error": float(np.max(abs(ec - rc2))), "log_evidence_error": abs(ez - rz2),
                        "next_gaussian_projection_probability_error": float(abs(pred_ep - pred_ref)),
                        "reference_refinement_error": max(float(np.max(abs(rm - rm2))), float(np.max(abs(rc - rc2))), abs(rz - rz2))})
    return {"cases": records, "maximum_probability_error": max(r["next_gaussian_projection_probability_error"] for r in records),
            "gate": cfg["numerics"]["precision_checks"]["probability_error_gate"],
            "passed": max(r["next_gaussian_projection_probability_error"] for r in records) <= cfg["numerics"]["precision_checks"]["probability_error_gate"],
            "limits": "two-game Gaussian-prior cases only; no global posterior error bound"}


def simulate(cfg):
    setting = cfg["simulation"]
    aggregate, trajectories, failures = [], [], []
    for scenario in setting["scenarios"]:
        for rep in range(setting["replicates"]):
            # Identical schedule and base uniform innovations across models and scenarios.
            rng = np.random.default_rng(setting["seed"] + rep)
            games, truths = [], []
            base_strength = np.array([0.8, 0.3, -0.4, -0.7])
            teams = ["A", "B", "C", "D"]
            for k in range(setting["matches_per_replicate"]):
                i, j = rng.choice(4, 2, replace=False)
                neutral, friendly = k % 7 == 0, k % 5 == 0
                strength = base_strength.copy()
                after = max(0, k - setting["change_match"] + 1)
                if scenario == "persistent_drop" and after:
                    strength[0] -= 1.5
                if scenario == "gradual_drop":
                    strength[0] -= min(1.5, after * 0.075)
                home = 0.35 + (0.8 if scenario == "home_shift" and after else 0)
                u = strength[i] - strength[j] + (0 if neutral else home)
                cdf = (lambda x: expit(x / 0.6)) if scenario == "logistic_link" else ndtr
                pp = np.array([cdf(u - 0.3), cdf(0.3 - u) - cdf(-0.3 - u), cdf(-0.3 - u)])
                pp = 0.97 * pp + 0.03 / 3
                y = int(np.searchsorted(np.cumsum(pp), rng.random()))
                if scenario == "isolated" and k == setting["change_match"]:
                    # Fixed surprising loss by A, then return to stable generator.
                    i, j, y = 0, 3, 2
                day = (date(1960, 1, 1) + timedelta(days=setting["days_between_matches"] * k)).isoformat()
                games.append(dict(match_id=f"sim-{k:03d}", date=day, home=teams[i], away=teams[j],
                                  venue=0 if neutral else 1, friendly=friendly, outcome=y))
                truths.append((strength - strength.mean(), home))
            for candidate in cfg["pilot"]["candidates"][:4]:
                engine = StrengthFilter(teams, params(cfg, candidate), cfg["numerics"])
                forecasts, errors, home_errors, signal = [], [], [], None
                baseline_level = None
                try:
                    for k, g in enumerate(games):
                        forecasts.extend(engine.day(g["date"], [g]))
                        estimate = sum(c.weight * c.mean for c in engine.components)
                        centered = estimate[:4] - estimate[:4].mean()
                        errors.append(float(np.mean((centered - truths[k][0])**2)))
                        home_errors.append(float((estimate[-1] - truths[k][1])**2))
                        if k == setting["change_match"] - 1:
                            baseline_level = float(centered[0])
                        if k >= setting["change_match"] and signal is None and baseline_level - centered[0] >= setting["detection_mean_drop"]:
                            signal = k - setting["change_match"] + 1
                        if rep == 0:
                            trajectories.append(dict(scenario=scenario, model=candidate["id"], match_no=k,
                                                     truth_A=float(truths[k][0][0]), estimate_A=float(centered[0]),
                                                     estimate_home=float(estimate[-1]), truth_home=truths[k][1]))
                    metrics = score(forecasts[setting["change_match"]:])
                    aggregate.append(dict(scenario=scenario, replicate=rep, model=candidate["id"], **metrics,
                                          centered_strength_rmse=math.sqrt(float(np.mean(errors[setting["change_match"]:]))),
                                          home_rmse=math.sqrt(float(np.mean(home_errors[setting["change_match"]:]))),
                                          mean_drop_signal=signal is not None, signal_delay_matches=signal,
                                          max_pruned_mass=max(d["approximate_posterior_pruned_mass"] for d in engine.diagnostics)))
                except (NumericalFailure, np.linalg.LinAlgError) as exc:
                    failures.append(dict(stage="simulation", scenario=scenario, replicate=rep,
                                         model=candidate["id"], error=str(exc)))
    return aggregate, trajectories, failures


def real_pilot(cfg, learning):
    labels = set(cfg["pilot"]["teams"])
    games = []
    for r in read_rows(learning / "learning_matches.csv"):
        if r["home_team"] in labels and r["away_team"] in labels and r["date"] <= cfg["pilot"]["end"]:
            games.append(dict(match_id=r["match_id"], date=r["date"], home=r["home_entity_id"],
                              away=r["away_entity_id"], venue=0 if r["is_neutral"] == "true" else 1,
                              friendly=r["tournament_group"] == "friendly", outcome=int(r["outcome_index"])))
    forecasts, metrics, diagnostics, failures, calibrations = [], [], [], [], []
    checkpoints = {}
    run_cache = {}
    for candidate in cfg["pilot"]["candidates"]:
        for start in cfg["pilot"]["starts"]:
            try:
                rows, engine = stream(games, cfg, params(cfg, candidate), start)
                run_cache[(candidate["id"], start)] = rows
                for period, lo, hi in (("development", "1970-01-01", "1974-12-31"),
                                       ("selection_validation", "1975-01-01", "1979-12-31")):
                    subset = [r for r in rows if lo <= r["date"] <= hi]
                    metrics.append(dict(model=candidate["id"], start=start, period=period, **score(subset)))
                    if period == "selection_validation":
                        calibrations.extend({**c, "start": start} for c in calibration(subset, candidate["id"]))
                forecasts.extend(dict(model=candidate["id"], start=start, **r) for r in rows)
                diagnostics.extend(dict(model=candidate["id"], start=start, **d) for d in engine.diagnostics)
                if candidate["id"] in {"smooth", "robust", "jump", "both"} and start == 1950:
                    checkpoints[candidate["id"]] = engine.state()
            except (NumericalFailure, np.linalg.LinAlgError) as exc:
                failures.append(dict(stage="real_pilot", model=candidate["id"], start=start, error=str(exc)))
    for start in cfg["pilot"]["starts"]:
        for period, lo, hi in (("development", "1970-01-01", "1974-12-31"),
                               ("selection_validation", "1975-01-01", "1979-12-31")):
            subset = [r for r in baseline([g for g in games if int(g["date"][:4]) >= start]) if lo <= r["date"] <= hi]
            metrics.append(dict(model="past_frequency", start=start, period=period, **score(subset)))
    # Numerical-budget and initial-prior checks use development data only.
    sensitivity = []
    development_games = [g for g in games if g["date"] <= "1974-12-31"]
    for name, variance, numerical in [
        ("prior_variance_0.5", 0.5, cfg["numerics"]),
        ("prior_variance_2.0", 2.0, cfg["numerics"]),
        ("components_16_cap_3", 1.0, {**cfg["numerics"], "max_components": 16, "jump_total_cap": 3}),
    ]:
        try:
            rows, eng = stream(development_games, cfg, params(cfg, {"id": "both"}), 1950, variance, numerical)
            compare = {r["match_id"]: r for r in run_cache.get(("both", 1950), []) if "1970" <= r["date"] <= "1974-12-31"}
            evaluation = [r for r in rows if r["match_id"] in compare]
            gap = max((max(abs(r[k] - compare[r["match_id"]][k]) for k in ("p_home", "p_draw", "p_away")) for r in evaluation), default=0)
            sensitivity.append(dict(setting=name, **score(evaluation), max_probability_difference=gap,
                                    numeric_gate_pass=gap <= cfg["numerics"]["precision_checks"]["probability_error_gate"]
                                    if name.startswith("components") else None,
                                    max_pruned_mass=max(d["approximate_posterior_pruned_mass"] for d in eng.diagnostics)))
        except (NumericalFailure, np.linalg.LinAlgError) as exc:
            failures.append(dict(stage="sensitivity", setting=name, error=str(exc)))
    validation = [r for r in metrics if r["period"] == "selection_validation" and r["model"] != "past_frequency" and r["count"]]
    # A pilot winner is descriptive only. Never promote to a production rule here.
    ranked = sorted(validation, key=lambda r: (r["log_loss"], r["model"], r["start"]))
    report = {
        "teams": sorted(labels), "within_set_games": len(games),
        "development_games": sum("1970" <= g["date"] <= "1974-12-31" for g in games),
        "validation_games": sum("1975" <= g["date"] <= "1979-12-31" for g in games),
        "numerically_best_pilot_row": ranked[0] if ranked else None,
        "production_model_selected": False,
        "selection_limits": "small restricted population; beam/EP checks, hyperparameter uncertainty and global predictive acceptance not complete",
        "validation_match_sets_equal": len({tuple(r["match_id"] for r in run_cache[key] if "1975" <= r["date"] <= "1979-12-31") for key in run_cache}) <= 1,
        "no_post1980_results_used": all(g["date"] < "1980" for g in games),
        "checkpoint_scope": "six-team-only development replay; cannot initialize production ratings",
    }
    return forecasts, metrics, diagnostics, calibrations, sensitivity, failures, checkpoints, report


def run(cfg):
    begin = time.perf_counter()
    learning, learning_manifest = prepare(cfg)
    reference = numerical_checks(cfg)
    print("Numerical reference finished", flush=True)
    sim, traces, simfail = simulate(cfg)
    print(f"Simulation finished: {len(sim)} completed, {len(simfail)} failed", flush=True)
    forecasts, metrics, diagnostics, cal, sens, realfail, checkpoints, real = real_pilot(cfg, learning)
    print(f"Historical pilot finished: {len(metrics)} metric rows", flush=True)
    failures = simfail + realfail
    numerical_pass = reference["passed"] and not failures and all(
        r["numeric_gate_pass"] is not False for r in sens)
    report = {
        "status": "pilot_completed_no_production_acceptance",
        "protocol_fingerprint": fingerprint(cfg),
        "reference": reference, "real_pilot": real,
        "simulation_completed_runs": len(sim), "failed_runs": len(failures),
        "numerical_acceptance": numerical_pass,
        "production_ready": False,
        "next": "Resolve recorded numerical/scope failures; no automatic full1980-2024 scoring or joint fit",
        "stage1_learning": learning.relative_to(ROOT).as_posix(),
    }
    tables = {"simulation_metrics.csv": sim, "simulation_trajectories.csv": traces,
              "historical_metrics.csv": metrics, "pilot_predictions.csv": forecasts,
              "daily_diagnostics.csv": diagnostics, "calibration.csv": cal, "sensitivity.csv": sens}
    # Empty successful output is never silently replaced by an invented row.
    empty = [name for name, rows in tables.items() if not rows]
    report["empty_tables"] = empty
    folder, manifest = publish("pilot", {"config": cfg, "learning_id": learning_manifest["stage_id"],
                                       "purpose": "pre1980_small_development_no_global_acceptance"},
                               csvs={k: v for k, v in tables.items() if v},
                               jsons={"report.json": report, "failures.json": failures, "checkpoints.json": checkpoints})
    timing_path = ROOT / "outputs/logs/strength" / ("execution-" + str(time.time_ns()) + ".json")
    write_json(timing_path, {"stage_id": manifest["stage_id"], "elapsed_seconds": time.perf_counter() - begin,
                            "nondeterministic_timing_only": True})
    return folder, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/strength_pilot.json")
    args = parser.parse_args()
    folder, _ = run(config(args.config))
    print(folder.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
