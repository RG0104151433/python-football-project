"""Apply the frozen joint method to original targets, without retuning it."""
from pathlib import Path
import json
import numpy as np
from .design import build_design, sha, rows, require
from .models import FixedDesign
from .joint import RestrictedMoments, calibrated_halfwidth
from .guard import protect_scale


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_verified(root, config_path="config/reliability_analysis.json"):
    root = Path(root)
    plan = read(root / config_path)
    contract = read(root / plan["contract"])
    bindings = read(root / plan["bindings"])["bindings"]
    checked = {**bindings, **contract["artifacts"]}
    for p, h in checked.items():
        require(sha(root / p) == h, "Frozen dependency changed: " + p)
    require(contract["method"] == "J-RMC6-T-v15", "Unapproved application method")
    require(contract["status"] == "admitted_only_for_explicit_model_conditional_step4", "Method gate closed")
    ctx = build_design(root)
    targets = [t for t in ctx["catalogue"] if t["target_id"] in ctx["vectors"]]
    families = {f:[j for j,t in enumerate(targets) if t["family"] == f] for f in sorted(contract["families"])}
    d = FixedDesign(ctx["facts"], np.stack([ctx["vectors"][t["target_id"]] for t in targets]),
                    [t["target_id"] for t in targets], families,
                    [t for t in ctx["catalogue"] if t["target_id"] not in ctx["vectors"]])
    expect = plan["expected"]
    require((d.n, len(ctx["catalogue"]), len(d.targets), len(d.unsupported), len(d.teams)) ==
            tuple(expect[k] for k in ("matches", "catalogue", "supported", "unsupported", "teams")), "Unexpected design sizes")
    cfg = read(root / plan["model_config"])
    approval = read(root / contract["audit"])
    require(approval["all_passed"], "Parent method audit not passed")
    require(sha(root / plan["previous_scales"]) == approval["outputs"][plan["previous_scales"]], "Approved scales artifact changed")
    cache = read(root / cfg["cache_pointer"])
    cache_path = root / cache["directory"] / "cache.npz"
    require(sha(cache_path) == cache["cache_sha256"], "Kernel cache changed")
    require(sha(root / "src/reliability/joint.py") == cache["joint_source_sha256"], "Joint source/cache mismatch")
    guard_meta = read((root / cfg["guard_cache"]).parent / "guard_manifest.json")
    require(sha(root / cfg["guard_cache"]) == guard_meta["guard_sha256"], "Guard changed")
    with np.load(root / cfg["guard_cache"], allow_pickle=False) as source:
        guard = source["guard"]
    tail = read(root / cfg["tail_weights"])
    require(tail["target_ids"] == d.targets and len(guard) == len(d.targets), "Target order mismatch")
    cal_path = Path(plan["contract"]).parent / "calibration.json"
    cal = read(root / cal_path)
    inputs = {**checked, **ctx["inputs"], **ctx["parent_outputs"]}
    for p in (config_path, plan["contract"], plan["bindings"], plan["previous_scales"],
              cache_path.relative_to(root).as_posix(), cfg["cache_pointer"], cfg["guard_cache"],
              cfg["tail_weights"], cal_path.as_posix()):
        inputs[p] = sha(root / p)
    return dict(root=root, plan=plan, contract=contract, context=ctx, design=d,
                model=RestrictedMoments.load(d, cache_path), guard=guard,
                tail=np.asarray(tail["weights"], float), calibration=cal,
                calibration_id="calibration-" + sha(root / cal_path)[:20], inputs=inputs)


def infer_original(bundle):
    d, model = bundle["design"], bundle["model"]
    y = np.asarray([int(r["home_win"]) for r in d.facts], float)
    fit = protect_scale(model.fit(y, corrected=True, coarse=True), bundle["guard"], .1)
    protected = fit["scale"].copy()
    fit["scale"] = protected * bundle["tail"]
    require(np.all(np.isfinite(fit["scale"])) and np.all(fit["scale"] >= 0), "Invalid score scales")
    point = d.apply(y)
    half = calibrated_halfwidth(d, fit, bundle["calibration"]["critical"])
    lower, upper = np.maximum(point-half, d.lo), np.minimum(point+half, d.hi)
    previous = list(rows(bundle["root"] / bundle["plan"]["previous_scales"]))
    require(len(previous) == len(d.targets), "Incomplete approved scales catalogue")
    for j, r in enumerate(previous):
        require(r["target_id"] == d.targets[j], "Previous scale target order")
        require(abs(point[j]-float(r["original_point_estimate"])) < 1e-12, "Point estimate changed")
        require(abs(fit["scale"][j]-float(r["calibrated_score_scale"])) < 1e-11, "Score scale changed")
    lookup = {tid:j for j,tid in enumerate(d.targets)}
    intervals, bounded = [], []
    for t in bundle["context"]["catalogue"]:
        tid, f = t["target_id"], t["family"]
        common = dict(target_id=tid, question=t["question"], family=f, kind=t["kind"], label=t["label"],
            reference_id=t["reference_id"], display_unit=t["display_unit"], source_table=t["source_table"],
            source_row_key=t["source_row_key"], scope=bundle["plan"]["scope"])
        if tid not in lookup:
            a = dict(**common, status="unsupported", point_probability_scale=None,
                lower_probability_scale=None, upper_probability_scale=None,
                point_display=None, lower_display=None, upper_display=None,
                logical_lower=None, logical_upper=None, protected_scale=None, tail_weight=None,
                calibrated_score_scale=None, family_critical=None, unsupported_reason=t["missing_cells"])
            b = dict(a)
        else:
            j = lookup[tid]
            require(abs(point[j]-t["estimate_probability"]) < 1e-12, "Catalogue point mismatch")
            require(d.lo[j]-1e-12 <= lower[j] <= point[j]+1e-12 and point[j]-1e-12 <= upper[j] <= d.hi[j]+1e-12,
                    "Invalid delivered interval")
            a = dict(**common, status="model_conditional", point_probability_scale=float(point[j]),
                lower_probability_scale=float(lower[j]), upper_probability_scale=float(upper[j]),
                point_display=float(100*point[j]), lower_display=float(100*lower[j]), upper_display=float(100*upper[j]),
                logical_lower=float(d.lo[j]), logical_upper=float(d.hi[j]), protected_scale=float(protected[j]),
                tail_weight=float(bundle["tail"][j]), calibrated_score_scale=float(fit["scale"][j]),
                family_critical=bundle["calibration"]["critical"][f], unsupported_reason="")
            delta = bundle["plan"]["bounded_reference_alpha"]/(2*len(d.families[f]))
            lo = d.lo[j]+delta*(point[j]-d.lo[j]);hi = d.hi[j]-delta*(d.hi[j]-point[j])
            b = dict(a, status="bounded_reference", lower_probability_scale=float(lo), upper_probability_scale=float(hi),
                lower_display=float(100*lo), upper_display=float(100*hi), scope="Bounded outcomes only, separate95% family Markov reference; not selected by observed width")
        a.update(method_id=bundle["contract"]["method"], calibration_id=bundle["calibration_id"],
                 score_scale_is_standard_error=False, all_constant_branch=fit["all_constant"])
        b.update(method_id="bounded-Markov-family-v1", calibration_id="", score_scale_is_standard_error=False)
        # Scales and q are diagnostics of the joint method, not of the Markov construction.
        for k in ("protected_scale", "tail_weight", "calibrated_score_scale", "family_critical"):
            b.pop(k, None)
        intervals.append(a);bounded.append(b)
    return intervals, bounded, dict(theta=fit["theta"].tolist(), kernel_labels=model.labels,
        all_constant=fit["all_constant"], mean_working_model_not_probability=True, previous_scales_reproduced=True)
