"""Joint analysis entry. Run from repository root; no third-party data downloads."""
from pathlib import Path
import argparse
from collections import defaultdict
import json
import math
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data_contract import file_hash, write_json
from src.strength.io import read_rows
from src.strength.global_run import load as load_learning
from src.strength_joint.contract import load
from src.strength_joint.design import Design
from src.strength_joint.model import fit, predict
from src.strength_joint.contrasts import calculate, changes
from src.strength_joint.validation import kernel_check, small_feedback, feedback_world
from src.strength_joint.reporting import publish, metrics, calibration, DICTIONARY

LOG = ROOT / "outputs/logs/strength_joint"


def sensitivity(cfg, rows, design, results, targets, geography):
    base = predict(results["M3_nested"], rows, design)
    main_contrasts = calculate({"M3_nested": results["M3_nested"]}, rows, targets, geography, design, cfg)
    reference = {r["target_id"]: r for r in main_contrasts}
    variants = []; inputs = {}
    for directory in cfg["initializations"]:
        path = ROOT / directory / "study_differences.csv"
        index = {r["match_id"]: r for r in read_rows(path)}
        if index.keys() != {r["match_id"] for r in rows}:
            raise ValueError("INPUT_VERSION_MISMATCH: initialization IDs")
        variant = [dict(r, strength_difference=index[r["match_id"]]["difference"]) for r in rows]
        variants.append((Path(directory).name, "mean_only_variance_and_jump_fixed; not full initialization distribution", variant))
        inputs[path.relative_to(ROOT).as_posix()] = file_hash(path)
    weak = ROOT / cfg["weak_jump_score"]
    index = {r["match_id"]: r for r in read_rows(weak / "study_prematch_features.csv")}
    report = json.loads((weak / "report.json").read_text())
    source_report = json.loads((ROOT / cfg["raw_score"] / "report.json").read_text())
    weak_manifest = json.loads((weak / "manifest.json").read_text())
    if file_hash(weak / "study_prematch_features.csv") != weak_manifest["outputs"]["study_prematch_features.csv"]:
        raise ValueError("INPUT_VERSION_MISMATCH: weak score")
    if index.keys() != {r["match_id"] for r in rows} or weak_manifest["identity"]["inputs"] != json.loads((ROOT / cfg["raw_score"] / "manifest.json").read_text())["identity"]["inputs"]:
        raise ValueError("INPUT_VERSION_MISMATCH: weak learning schedule")
    variant = []
    for r in rows:
        alt = index[r["match_id"]]
        if any(str(alt[k]) != str(r[k]) for k in ("date", "prediction_cutoff", "home_history", "away_history")):
            raise ValueError("FUTURE_INFORMATION: weak date/history")
        nh = float(r["home_jump_intensity"]) * report["parameters"]["jump_rate"] / source_report["parameters"]["jump_rate"]
        na = float(r["away_jump_intensity"]) * report["parameters"]["jump_rate"] / source_report["parameters"]["jump_rate"]
        sd = report["parameters"]["jump_sd"]
        variance = float(alt["difference_variance"])
        v0 = variance - (nh + na) * sd * sd
        if v0 <= 0:
            raise ValueError("DISTRIBUTION_FIELDS_MISSING: weak base variance")
        variant.append(dict(r, strength_difference=alt["difference"], strength_difference_variance=variance,
            strength_difference_base_variance=v0, home_jump_intensity=nh, away_jump_intensity=na, jump_scale_sd=sd))
    variants.append(("weak_jump_full_distribution", "same verified learning dates/history; actual weak Poisson distribution", variant))
    inputs[cfg["weak_jump_score"] + "/manifest.json"] = file_hash(weak / "manifest.json")
    output = []
    fits = {}
    for label, scope, variant in variants:
        print("JOINT_SENSITIVITY", label, flush=True)
        result = fit(variant, design, "M3_nested", cfg["numerics"])
        fits[label] = result
        p = predict(result, variant, design)
        alt = calculate({"M3_nested": result}, variant, targets, geography, design, cfg)
        for r in alt:
            original = reference[r["target_id"]]
            output.append(dict(variant=label, scope=scope, target_id=r["target_id"], study_rows=len(rows),
                main_reference_id=original["reference_id"], variant_reference_id=r["reference_id"],
                main_difference_pp=original["difference_pp"], variant_difference_pp=r["difference_pp"],
                difference_change_pp=None if r["difference_pp"] is None or original["difference_pp"] is None else r["difference_pp"] - original["difference_pp"],
                mean_absolute_fitted_probability_change=float(np.mean(abs(p - base))),
                max_absolute_fitted_probability_change=float(np.max(abs(p - base))),
                inference_status="INFERENCE_NOT_ADMITTED"))
    return output, fits, inputs


def analyze(cfg, rows, targets, geography, inputs, run_sensitivity=True):
    begin = time.perf_counter(); design = Design(rows)
    kernel = kernel_check(rows, design, cfg["numerics"])
    if not kernel["passed"]:
        raise ValueError("NUMERIC_GATE_FAILED: " + repr(kernel))
    results = {}; metric_rows = []; calibration_rows = []; coefficient_rows = []
    prediction_rows = [dict(match_id=r["match_id"], date=r["date"], era=r["era"], tournament_group=r["tournament_group"],
        home_region=r["home_region"], home_unit=r["home_unit"], away_region=r["away_region"], away_unit=r["away_unit"],
        home_win=int(r["home_win"]), strength_information_cutoff=r["prediction_cutoff"],
        outcome_model_information_cutoff="2024-12-31_retrospective_fit_not_prematch_prediction") for r in rows]
    precision = []
    for model in cfg["models"]:
        print("JOINT_FIT", model, flush=True)
        result = fit(rows, design, model, cfg["numerics"])
        results[model] = result
        p = predict(result, rows, design)
        strict_p = predict(result, rows, design, cfg["numerics"]["strict_tail"])
        delta = float(max(abs(p - strict_p)))
        if delta > cfg["numerics"]["probability_reference_gate"]:
            raise ValueError("NUMERIC_GATE_FAILED: fit precision")
        precision.append(dict(model_id=model, max_tail_tightening_probability_change=delta))
        metric_rows.append(metrics(result, rows, p)); calibration_rows.extend(calibration(rows, p, model))
        for row, value in zip(prediction_rows, p):
            row[model] = float(value)
        for name, value in zip(result["names"] + result["slope_names"], result["theta"]):
            coefficient_rows.append(dict(model_id=model, parameter=name, value=value,
                                        scale="log_positive_slope" if name.startswith("log_b") else "latent_probit", standard_error=None))
        print("JOINT_FIT_DONE", model, result["loss"], round(time.perf_counter() - begin, 2), flush=True)
    contrasts = calculate(results, rows, targets, geography, design, cfg)
    contrasts += calculate(results, rows, targets, geography, design, cfg, supported_reference=True)
    comparison = changes(contrasts)
    sens_rows = []; sens_fits = {}; sens_inputs = {}
    if run_sensitivity:
        sens_rows, sens_fits, sens_inputs = sensitivity(cfg, rows, design, results, targets, geography)
    core_report = json.loads((ROOT / cfg["raw_score"] / "report.json").read_text())
    small = small_feedback(cfg, cfg["numerics"], core_report["parameters"], core_report["numerics"])
    if not all(r["numerical_fit_passed"] and r["max_prequery_score_error"] < 2e-8 and r["draws"] > 0 and r["away_wins"] > 0 for r in small):
        raise ValueError("NUMERIC_GATE_FAILED: small feedback")
    validation = dict(kernel=kernel, precision=precision, numerical_fit_passed=True, small_feedback=small,
        core_targets=32, originally_supported_targets=27, originally_unsupported_targets=5,
        score_learning_rows=38919, study_rows=len(rows), forecast_validation_performed=False,
        inference_status="INFERENCE_NOT_ADMITTED", confidence_intervals_computed=False,
        global_feedback_pilot="separate --stage global-feedback; not a coverage admission",
        outstanding=["full-size coverage and dependence/misspecification acceptance", "complete initialization-distribution refits (current initialization diagnostic changes mean only)",
                     "independent future forecast validation", "A/B actual human replication"])
    support_rows = [{k: r[k] for k in ("target_id", "model_id", "reference_id", "reference_kind", "reference_rows", "old_target_status", "point_status",
        "arm1_zero_cell_fraction", "arm2_zero_cell_fraction", "arm1_sparse_cell_fraction", "arm2_sparse_cell_fraction",
        "arm1_outside_score_range_fraction", "arm2_outside_score_range_fraction", "main_evidence_eligible")} for r in contrasts]
    display = dict(status="retrospective_point_estimates_only", main_model=cfg["main_model"], same_study_rows=len(rows),
        model_metrics=metric_rows, comparisons=comparison, main_contrasts=[r for r in contrasts if r["model_id"] == cfg["main_model"]],
        uncertainty_status="INFERENCE_NOT_ADMITTED", claims_forbidden=["causal effects", "percentage causally explained", "independent future prediction", "significance without admitted intervals"])
    csvs = {"model_metrics.csv": metric_rows, "coefficients.csv": coefficient_rows, "joint_predictions.csv": prediction_rows,
            "contrasts.csv": contrasts, "strength_changes.csv": comparison, "support.csv": support_rows, "calibration.csv": calibration_rows}
    if sens_rows:
        csvs["sensitivity.csv"] = sens_rows
    folder = publish("joint-analysis", dict(protocol=cfg, inputs=dict(inputs, **sens_inputs), run_sensitivity=run_sensitivity), csvs=csvs,
        jsons={"models.json": results, "sensitivity_models.json": sens_fits, "validation.json": validation, "display_data.json": display},
        texts={"data_dictionary.md": DICTIONARY})
    write_json(LOG / "analysis_pointer.json", dict(directory=folder.relative_to(ROOT).as_posix(), manifest_sha256=file_hash(folder / "manifest.json"), seconds=time.perf_counter() - begin))
    print("JOINT_ANALYSIS_COMPLETE", folder.relative_to(ROOT).as_posix(), flush=True)
    return folder


def global_feedback(cfg, rows, inputs):
    begin = time.perf_counter(); learning_cfg, games, learning_inputs = load_learning(cfg["learning_config"])
    templates = {r["match_id"]: r for r in rows}
    score_report = json.loads((ROOT / cfg["raw_score"] / "report.json").read_text())
    all_reports = []
    for world in cfg["simulation"]["worlds"]:
        for seed in cfg["simulation"]["global_seeds"]:
            generated, report = feedback_world(games, templates, score_report["parameters"], score_report["numerics"], seed, world)
            if len(generated) != 24917 or report["max_prequery_score_error"] >= 2e-8:
                raise ValueError("NUMERIC_GATE_FAILED: global feedback interface")
            design = Design(generated)
            result = fit(generated, design, "M3_nested", cfg["numerics"])
            report.update(numerical_fit_passed=True, fit_loss=result["loss"], fitted_intercept=result["theta"][0],
                          fitted_strength_slope=math.exp(result["theta"][-1]), interval_admission=False,
                          role="single_full_schedule_cost_and_feedback_pilot_not_coverage_test",
                          true_conditional_intercept=.15 if world == "score_conditional" else None,
                          true_conditional_slope=.8 if world == "score_conditional" else None)
            folder = publish("joint-feedback", dict(protocol=cfg, inputs=dict(inputs, **learning_inputs), world=world, seed=seed),
                csvs={"simulated_study_matches.csv": generated}, jsons={"report.json": report, "model.json": result})
            all_reports.append(dict(directory=folder.relative_to(ROOT).as_posix(), **report))
            write_json(LOG / "global_feedback_progress.json", all_reports)
            print("JOINT_GLOBAL_WORLD_COMPLETE", world, folder.relative_to(ROOT).as_posix(), flush=True)
    write_json(LOG / "global_feedback.json", dict(reports=all_reports, seconds=time.perf_counter() - begin,
        all_engineering_checks_passed=True, independent_worlds_per_scenario=len(cfg["simulation"]["global_seeds"]),
        confidence_interval_coverage_admitted=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/strength_joint.json")
    parser.add_argument("--stage", choices=["analysis", "global-feedback", "all"], default="analysis")
    parser.add_argument("--skip-sensitivity", action="store_true", help="development only; separately identified output")
    args = parser.parse_args()
    try:
        cfg, rows, targets, geography, inputs = load(args.config)
        if args.stage in ("analysis", "all"):
            analyze(cfg, rows, targets, geography, inputs, not args.skip_sensitivity)
        if args.stage in ("global-feedback", "all"):
            global_feedback(cfg, rows, inputs)
    except Exception as error:
        write_json(LOG / "latest_failure.json", dict(error=repr(error), stage=args.stage,
            completed=False, inference_admitted=False))
        raise
