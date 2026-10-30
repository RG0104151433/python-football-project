"""Interface checks, both-route diagnostics and complete-history cost pilot."""
from collections import defaultdict
from datetime import date, timedelta
import json
import gzip
import time
import numpy as np
from scipy.special import ndtr
from src.data_contract import file_hash, fingerprint, write_json, atomic_bytes
from src.strength.io import ROOT
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength_joint.design import Design
from src.strength_joint.model import Kernel, objective, slopes
from src.strength_stage6_sensitivity import read
from .worlds import before_day, complete_wdl, generate
from .targets import Targets, probability_and_gradient, soft_probit_projection
from .methods import refit_pair, calendar_influence, multiplier_draws, summarize_draws, bartlett_weights
from .reporting import publish


def interface(c):
    checks = []; rng = np.random.default_rng(63001)
    def check(name, value, limit=0.):
        checks.append(dict(name=name, error=float(value), limit=limit, passed=bool(value <= limit)))
    engine = CollapsedJumpFilter(["A", "B", "C", "D"], c["score_parameters"], c["score_numerics"])
    for i, day in enumerate(("1979-01-01", "1979-06-01", "1980-01-01")):
        batch = [dict(match_id="x"+str(i), date=day, home="A", away="B", venue=0 if i == 1 else 1, friendly=i == 1, outcome=i),
                 dict(match_id="y"+str(i), date=day, home="C", away="D", venue=1, friendly=False, outcome=(i+1)%3)]
        state = fingerprint(engine.state()); prior, q = before_day(engine, day, batch)
        check("readonly:"+day, state != fingerprint(engine.state()))
        clone = CollapsedJumpFilter.restore(engine.state())
        a = engine.day(day, batch); b = clone.day(day, list(reversed(batch)))
        check("same_day_order:"+day, float(np.max(abs(engine.mean-clone.mean))), 2e-12)
        check("same_day_covariance:"+day, float(np.max(abs(engine.cov-clone.cov))), 2e-12)
        check("raw_probability:"+day, max(abs(q[k, j]-a[k][name]) for k in range(2) for j, name in enumerate(("p_home", "p_draw", "p_away"))), 2e-12)
        check("marginal:"+day, max(abs(prior[k]["strength_difference_variance"]-a[k]["difference_variance"]) for k in range(2)), 2e-12)
    q = np.array([[.3, .2, .5], [.6, .1, .3]])
    check("wdl_sum", np.max(abs(complete_wdl([.4, .7], q).sum(axis=1)-1)), 1e-14)
    check("draw_tilt_keeps_home", np.max(abs(complete_wdl([.4, .7], q, 2.)[:, 0]-[.4, .7])), 1e-14)
    x = np.column_stack((np.ones(80), np.tile([0., 1.], 40))); beta = np.array([.2, -.35])
    projection = soft_probit_projection(x, ndtr(x @ beta))
    check("known_projection_coefficients", np.max(abs(np.array(projection["theta"])-beta)), 2e-7)
    rr = c["rows"][::997]; design = Design(c["rows"])
    result = json.loads((ROOT/c["cfg"]["analysis"]/"models.json").read_text())["M3_nested"]
    p, grad = probability_and_gradient(result, rr, design); finite = []
    for j in range(len(result["theta"])):
        plus = dict(result, theta=list(result["theta"])); minus = dict(result, theta=list(result["theta"]))
        plus["theta"][j] += 1e-5; minus["theta"][j] -= 1e-5
        finite.append((probability_and_gradient(plus, rr, design)[0]-probability_and_gradient(minus, rr, design)[0])/2e-5)
    check("target_gradient", np.max(abs(np.column_stack(finite)-grad)), 2e-8)
    check("b0_probit", np.max(abs(Kernel(rr).evaluate(np.linspace(-1, 1, len(rr)), 0)-ndtr(np.linspace(-1, 1, len(rr))))), 2e-12)
    w = bartlett_weights(rng, 40000, 5, 3); empirical = w.T @ w / len(w)
    expected = np.maximum(1-abs(np.arange(5)[:, None]-np.arange(5)[None, :])/3, 0)
    check("bartlett_covariance_MC", np.max(abs(empirical-expected)), .025)
    check("bartlett_PSD", max(0., -float(np.linalg.eigvalsh(expected).min())), 1e-12)
    report = dict(passed=all(r["passed"] for r in checks), checks=len(checks), detail=checks,
        learning_matches=len(c["games"]), study_matches=len(c["rows"]), primary_targets=len(c["registry"]),
        projection=projection, formal_inference_admitted=False)
    folder = publish("interface", c, jsons={"review.json": report})
    if not report["passed"]: raise ValueError("INTERFACE_CHECK_FAILED: "+str(folder))
    return folder


def diagnostic(c):
    started = time.perf_counter(); rows = c["rows"]; design = Design(rows)
    all_models = json.loads((ROOT/c["cfg"]["analysis"]/"models.json").read_text())
    models = {m:all_models[m] for m in ("M0_nested", "M3_nested")}; target = Targets(c["cfg"], c["registry"])
    values, jac = target.evaluate(models, rows, design)
    expected = np.array([float(r["estimate"]) for r in c["registry"]])
    error = float(np.max(abs(values-expected)))
    if error > 2e-7: raise ValueError("REGISTERED_POINT_TARGET_MISMATCH: "+str(error))
    calendar, geometry, individual = calendar_influence(models, rows, design, jac)
    ranges, draws_out, summaries = [], [], []
    for bandwidth in c["cfg"]["calendar_bandwidth_days"]:
        draws = multiplier_draws(calendar, c["cfg"]["multiplier_repetitions"], bandwidth, c["cfg"]["multiplier_seed"]+bandwidth)
        summary = summarize_draws(draws, c["cfg"]["nominal_level_for_diagnostics"])
        summaries.append(dict(bandwidth_days=bandwidth, **summary))
        for j, item in enumerate(c["registry"]):
            half = summary["half_widths_pp"][j]
            ranges.append(dict(registry_id=item["registry_id"], target_id=item["target_id"], axis=item["effect_size_axis"],
                method="B_calendar_multiplier_raw_score", bandwidth_days=bandwidth, estimate_pp=float(values[j]),
                diagnostic_se_pp=summary["standard_errors_pp"][j], diagnostic_lower_pp=float(values[j]-half),
                diagnostic_upper_pp=float(values[j]+half), family_size=54, max_t_critical=summary["max_t_critical"],
                status="DEVELOPMENT_DIAGNOSTIC_NOT_CONFIDENCE_INTERVAL", coverage_admitted=False))
        draws_out.extend(dict(bandwidth_days=bandwidth, replicate=i, **{r["registry_id"]:float(v) for r, v in zip(c["registry"], d)}) for i, d in enumerate(draws))
    cal = [dict(calendar_offset=i, **{r["registry_id"]:float(v) for r, v in zip(c["registry"], row)}) for i, row in enumerate(calendar)]
    report = dict(method="B", primary_targets=54, calendar_days=len(calendar), registry_reconstruction_error_pp=error,
        geometry=geometry, paired_models_share_multipliers=True, raw_score_centering_validated=False,
        bandwidth_selected=False, formal_inference_admitted=False, seconds=time.perf_counter()-started,
        summaries=summaries, source_model_refitted=False)
    return publish("diagnostic", c, csvs={"diagnostic_ranges.csv":ranges, "multiplier_draws.csv.gz":draws_out, "calendar_influence.csv.gz":cal}, jsons={"report.json":report})


def pilot(c):
    """Two complete plug-in bootstrap draws and truth development, NOT coverage."""
    rows = c["rows"]; design = Design(rows); target = Targets(c["cfg"], c["registry"])
    models = json.loads((ROOT/c["cfg"]["analysis"]/"models.json").read_text()); generator = models["M3_nested"]
    templates = {r["match_id"]:r for r in rows}; index = {r["match_id"]:i for i, r in enumerate(rows)}
    reports, estimates, soft, world_models, all_probs, all_rows = [], [], [], {}, [], []
    for seed in c["cfg"]["world_seeds"]:
        started = time.perf_counter()
        cache_identity = dict(seed=seed, protocol=c["cfg"], inputs=c["inputs"], code={p.name:file_hash(p) for p in sorted((ROOT/"src/strength_inference").glob("*.py"))})
        cache = ROOT/"outputs/logs/strength_inference/checkpoints"/(fingerprint(cache_identity)+".json.gz")
        if cache.exists():
            checkpoint = json.loads(gzip.decompress(cache.read_bytes()))
            if checkpoint["identity"] != cache_identity: raise ValueError("CHECKPOINT_IDENTITY_MISMATCH")
            rr, probs, meta, fitted = (checkpoint[k] for k in ("rows", "probabilities", "metadata", "models"))
            print("INFERENCE_RESUME_COMPLETE_WORLD", seed, flush=True)
        else:
            rr, probs, meta = generate(c["games"], templates, design, generator, c["score_parameters"], c["score_numerics"], seed)
            rr.sort(key=lambda r:index[r["match_id"]])
            fitted = refit_pair(rr, design, c["joint_cfg"]["numerics"])
            checkpoint = dict(identity=cache_identity, rows=rr, probabilities=probs, metadata=meta, models=fitted)
            atomic_bytes(cache, gzip.compress(json.dumps(checkpoint, allow_nan=False).encode(), mtime=0))
        fit_started = time.perf_counter()
        study_probs = sorted((p for p in probs if not p["auxiliary_learning"]), key=lambda r:index[r["match_id"]])
        values, jac = target.evaluate(fitted, rr, design)
        known = dict(fitted); known["M3_nested"] = generator
        known_values, _ = target.evaluate(known, rr, design)
        world_models[str(seed)] = fitted
        calendar, geometry, _ = calendar_influence(fitted, rr, design, jac)
        candidate = multiplier_draws(calendar, c["cfg"]["multiplier_repetitions"], 365, 64000+seed)
        ss = summarize_draws(candidate)
        for j, item in enumerate(c["registry"]):
            level = item["effect_size_axis"] == "level"
            half = ss["half_widths_pp"][j]
            estimates.append(dict(seed=seed, registry_id=item["registry_id"], target_id=item["target_id"], axis=item["effect_size_axis"],
                estimate_pp=float(values[j]), known_M3_truth_pp=float(known_values[j]) if level else None,
                truth_status="EXACT_GENERATOR_COEFFICIENT_FUNCTION" if level else "M0_PROJECTION_NOT_READY",
                B365_diagnostic_half_width_pp=half,
                known_M3_error_pp=float(values[j]-known_values[j]) if level else None,
                diagnostic_contains_known_truth=abs(values[j]-known_values[j]) <= half if level else None,
                method="A_full_feedback_draw_with_B365_companion", reference="same_members_world_rerated", coverage_admitted=False))
        soft.append(np.array([p["true_home_probability"] for p in study_probs]))
        all_probs.extend(dict(seed=seed, **p) for p in probs)
        all_rows.extend(dict(seed=seed, **{k:r[k] for k in ("match_id", "date", "strength_difference", "strength_difference_base_variance",
            "strength_difference_variance", "home_jump_intensity", "away_jump_intensity", "jump_scale_sd", "home_win", "outcome", "prediction_cutoff")}) for r in rr)
        meta.update(targets_and_B_seconds=time.perf_counter()-fit_started, total_seconds=time.perf_counter()-started,
            fitted_models={m:{k:v for k,v in result.items() if k in ("loss","gradient","curvature_min","numerical_fit_passed","rows")} for m,result in fitted.items()},
            B_geometry=geometry, diagnostic_known_level_targets=27, paired_truth_admitted=False)
        reports.append(meta); print("INFERENCE_PILOT_WORLD_COMPLETE", seed, meta["total_seconds"], flush=True)
    x, _ = design.matrix(rows, "M0_nested")
    projections = [soft_probit_projection(x, p) for p in soft]
    pooled = soft_probit_projection(x, np.mean(soft, axis=0))
    comparisons = []
    for j, item in enumerate(c["registry"]):
        ee = [r for r in estimates if r["registry_id"] == item["registry_id"]]
        comparisons.append(dict(registry_id=item["registry_id"], axis=item["effect_size_axis"], A_draws=len(ee),
            A_min_estimate_pp=min(r["estimate_pp"] for r in ee), A_max_estimate_pp=max(r["estimate_pp"] for r in ee),
            A_sample_range_pp=max(r["estimate_pp"] for r in ee)-min(r["estimate_pp"] for r in ee),
            B365_mean_diagnostic_half_width_pp=float(np.mean([r["B365_diagnostic_half_width_pp"] for r in ee])),
            winner="NOT_SELECTED", reason="two draws do not estimate coverage; M0 truth and centering not ready"))
    report = dict(route_A="complete plug-in parametric bootstrap draws; distribution/centering/coverage not admitted",
        route_B="same simulated worlds; 365-day raw-score multiplier diagnostic only", worlds=reports,
        world_count=len(reports), independent_truth_worlds=0, M0_pooled_development_projection=pooled,
        M0_single_world_path_projections=projections, truth_status="DEVELOPMENT_SAME_STREAM_NOT_ORACLE",
        method_selected=None, formal_inference_admitted=False, nominal_coverage_not_tested=True,
        selection_repeated=False, human_review=False)
    return publish("pilot", c, csvs={"world_estimates.csv":estimates, "world_probabilities.csv.gz":all_probs,
        "world_score_marginals.csv.gz":all_rows, "method_comparison.csv":comparisons},
        jsons={"report.json":report, "models.json":world_models})


def run(c, stage):
    if stage in ("validate", "apply", "truth"):
        raise ValueError("NOT_READY: independent precision-controlled truth and frozen coverage protocol required")
    return {"interface":interface, "diagnostic":diagnostic, "pilot":pilot}[stage](c)
