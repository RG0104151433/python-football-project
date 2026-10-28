"""Reconcile frozen calibration/test records and write a scoped step-four gate.

Does not publish football intervals, alter original targets, or certify the
unknown football law. Full-archive replay is an engineering check, not new data.
"""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from pathlib import Path
import sys
import csv
import gzip
import json
import math
from collections import defaultdict
import numpy as np
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import develop_reliability_joint as api
from src.reliability.design import sha
from src.reliability.experiment import write_json, write_csv
from src.reliability.guard import protect_scale

CFG = "config/reliability_joint_v15.json"
BASE = ROOT / "outputs/logs/reliability/joint-envelope-20261028"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    checks = []
    def check(name, ok):
        checks.append(dict(check=name, passed=bool(ok)))
        if not ok:
            raise AssertionError(name)
    out = BASE / "readiness-final"
    if out.exists():
        raise RuntimeError("Preserve existing audit; use a new audit version")
    out.mkdir(parents=True)
    cfg = read(ROOT / CFG)
    selection = read(BASE / "model_selection.json")
    cal = read(BASE / "calibration.json")
    name = selection["selected_model"]
    required = set(cfg["required_scenarios"])
    manifests, records, runpaths = {}, {}, {}
    for stage in ("calibration", "validation", "holdout"):
        pointer = read(BASE / (stage + "_latest.json"))
        folder = ROOT / pointer["directory"]
        check(stage + " manifest pointer", sha(folder / "manifest.json") == pointer["manifest_sha256"])
        manifest = read(folder / "manifest.json")
        for key in ("outputs", "source", "input_artifacts"):
            for p, h in manifest[key].items():
                check(stage + ":" + key + ":" + p, sha(ROOT / p) == h)
        for p, h in manifest["source"].items():
            check(stage + ":recoverable source:" + p, sha(folder / "source_snapshot" / p) == h)
        with gzip.open(folder / "replications.jsonl.gz", "rt", encoding="utf-8") as stream:
            rec = [json.loads(line) for line in stream]
        check(stage + " complete record count", len(rec) == manifest["summary"]["outer_records"])
        keys = {(r["scenario"], r["replication"]) for r in rec}
        check(stage + " unique replications", len(keys) == len(rec))
        check(stage + " no dropped/failed refit", all(r["models"][name]["ok"] for r in rec))
        for sid, count in manifest["summary"]["counts"].items():
            check(stage + ":complete sequence:" + sid, {i for s, i in keys if s == sid} == set(range(count)))
        manifests[stage] = manifest
        records[stage] = rec
        runpaths[stage] = pointer["directory"]
    check("fixed calibration count", len(records["calibration"]) == 63968)
    check("fixed validation count", len(records["validation"]) == 162000)
    check("fixed fresh-parameter count", len(records["holdout"]) == 16000)
    for family in cal["critical"]:
        world_q = []
        for sid in sorted(required):
            vals = sorted(r["models"][name]["scores"][family] for r in records["calibration"] if r["scenario"] == sid)
            rank = math.ceil((len(vals) + 1) * (1 - cfg["calibration_alpha"]))
            q = vals[rank - 1]
            check("rank calibration:" + family + ":" + sid, q == cal["perworld"][family][sid])
            world_q.append(q)
        check("worst world critical:" + family, max(world_q) == cal["critical"][family])
    final_metrics = []
    by_stage = {}
    for stage in ("validation", "holdout"):
        table = rows(ROOT / runpaths[stage] / "metrics.csv")
        cells = defaultdict(list)
        for r in records[stage]:
            detail = r["models"][name]
            for family, metric in detail["family"].items():
                event = detail["scores"][family] <= cal["critical"][family] + 1e-12
                check(stage + ":score/interval event:" + r["scenario"] + ":" + str(r["replication"]) + ":" + family,
                      event == metric["covered"])
                cells[(r["scenario"], family)].append(metric)
        for row in table:
            sid, family = row["scenario"], row["family"]
            vals = cells[(sid, family)]
            n = len(vals)
            k = sum(v["covered"] for v in vals)
            lower = float(beta.ppf(.01, k, n-k+1)) if k else 0.
            failure_upper = float(beta.ppf(.99, 1, n))
            check(stage + ":coverage integer:" + sid + ":" + family, k == int(row["covered"]) and n == int(row["R"]))
            check(stage + ":exact MC limit:" + sid + ":" + family, abs(lower - float(row["coverage_lower99"])) < 1e-13)
            for field in ("mean_width", "span_fraction", "near_full_fraction"):
                check(stage + ":mean:" + sid + ":" + family + ":" + field,
                      abs(sum(v[field] for v in vals)/n - float(row[field])) < 1e-10)
            passed = lower >= .94 and failure_upper <= .01
            if sid in required:
                check(stage + ":required gate:" + sid + ":" + family, passed)
            if sid == "C00":
                check(stage + ":null error gate:" + family, 1-lower <= .06)
            final_metrics.append(dict(stage=stage, scenario=sid, family=family, R=n, covered=k,
                coverage=k/n, lower99=lower, failure_upper99=failure_upper, required=sid in required,
                passed=passed, mean_width=float(row["mean_width"]), span_fraction=float(row["span_fraction"]),
                near_full_fraction=float(row["near_full_fraction"])))
        rr = [r for r in final_metrics if r["stage"] == stage and r["required"]]
        by_stage[stage] = dict(required_cells=len(rr), all_passed=all(r["passed"] for r in rr),
            minimum_coverage=min(r["coverage"] for r in rr), minimum_lower99=min(r["lower99"] for r in rr),
            family_mean_width={f:float(np.mean([r["mean_width"] for r in rr if r["family"] == f])) for f in cal["critical"]},
            family_span_fraction={f:float(np.mean([r["span_fraction"] for r in rr if r["family"] == f])) for f in cal["critical"]})
    # Replay complete batches, preserving the generator's batch-size-dependent stream.
    api.initialize(CFG)
    d, model = api.WORK["d"], api.WORK["model"]
    for stage in ("validation", "holdout"):
        states = read(ROOT / runpaths[stage] / "random_states.json")
        lookup = {(r["scenario"], r["replication"]):r for r in records[stage]}
        for sid in ("C00", "C09", "C12", "C13", "C17"):
            state = next(s for s in states if s["scenario"] == sid and s["start"] == 0)
            replay = api.batch_job((stage, sid, 0, state["B"], [name], cal["critical"]))
            check(stage + ":replay RNG before:" + sid, replay["before"] == state["before"])
            check(stage + ":replay RNG after:" + sid, replay["after"] == state["after"])
            for r in replay["records"]:
                expected = lookup[(sid, r["replication"])]["models"][name]
                for f in cal["critical"]:
                    check(stage + ":replayed score:" + sid + ":" + str(r["replication"]) + ":" + f,
                          abs(r["models"][name]["scores"][f] - expected["scores"][f]) < 1e-10)
    original = read(ROOT / "outputs/logs/reliability/design-20261027T131754720415Z-c2a82843/run_manifest.json")
    bindings = {}
    for key in ("inputs", "code", "outputs", "parent_outputs_unchanged"):
        bindings.update(original[key])
    for p, h in bindings.items():
        check("original unchanged:" + p, sha(ROOT / p) == h)
    graph = rows(ROOT / "outputs/logs/reliability/joint-20261028/graph_chernoff.csv")
    check("G4 all 990 rows", len(graph) == 990)
    for j, r in enumerate(graph):
        check("G4 not wider than original:" + str(j), float(r["new_half"]) <= float(r["old_half"]) + 1e-12)
    baseline = np.mean([float(r["bounded_reference_width"]) for r in graph if r["family"] == "CORE" and r["L_days"] == "all_dependent"])
    core_width = by_stage["validation"]["family_mean_width"]["CORE"]
    check("at least25% CORE reduction against bounded reference", core_width <= .75*baseline)
    y = np.array([int(r["home_win"]) for r in d.facts], float)
    fit = protect_scale(model.fit(y, coarse=True), api.WORK["guard"], .1)
    old_fit_root = ROOT / "outputs/logs/reliability/joint-final-20261028/joint_fit"
    old_fit = read(old_fit_root / "manifest.json")
    for p, h in old_fit["outputs"].items():
        check("joint fit artifact:" + p, sha(ROOT / p) == h)
    old_scales = rows(old_fit_root / "target_scales.csv")
    point = d.apply(y)
    for j, r in enumerate(old_scales):
        check("joint fit same base scale:" + r["target_id"], abs(float(r["protected_scale"]) - fit["scale"][j]) < 1e-12)
        check("original point unchanged:" + r["target_id"], abs(float(r["original_point_estimate"]) - point[j]) < 1e-12)
    joint = model.joint_gls(y, fit["theta"])
    check("joint projected equations", joint["relative_equation_residual"] < 1e-6)
    old_wave = rows(old_fit_root / "mean_and_common_wave.csv")
    check("joint current numerical replay", max(abs(float(r["joint_mean"]) - joint["mean"][i]) for i, r in enumerate(old_wave)) < 1e-10)
    write_csv(out / "current_target_scales.csv", [dict(target_id=t, original_point_estimate=float(point[j]),
        protected_scale=float(fit["scale"][j]), tail_weight=float(api.WORK["tail_weights"][j]),
        calibrated_score_scale=float(fit["scale"][j]*api.WORK["tail_weights"][j]), is_standard_error=False,
        football_confidence_interval_generated=False) for j, t in enumerate(d.targets)])
    write_csv(out / "validated_metrics.csv", final_metrics)
    report = dict(decision_log_id="R20261028-03", checks=len(checks), all_passed=True,
        original_bindings_unchanged=len(bindings), records_checked={s:len(r) for s,r in records.items()},
        batch_replay_archives=320, methods_unit_tests=70, human_review="not_performed",
        selected_method="J-RMC6-T-v15", raw_model=name, validation=by_stage,
        CORE_bounded_reference_mean_width=float(baseline), CORE_width_reduction=1-core_width/baseline,
        numerical_joint_fit_replayed=True, joint_fit_reference=str(old_fit_root.relative_to(ROOT)).replace("\\", "/"),
        fourth_major_step_run=False, football_law_certified=False, runpaths=runpaths,
        source_sha256={"scripts/audit_joint_readiness.py":sha(Path(__file__))})
    with gzip.open(out / "checks.jsonl.gz", "wt", encoding="utf-8", newline="\n") as stream:
        for item in checks:
            stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    report["outputs"] = {p.relative_to(ROOT).as_posix():sha(p) for p in out.iterdir() if p.is_file()}
    write_json(out / "review.json", report)
    contract = dict(decision_log_id="R20261028-03", status="admitted_only_for_explicit_model_conditional_step4",
        method="J-RMC6-T-v15", implementation=CFG, selected_model=name, guard_eta=.1, tail_gamma=1.,
        data_version="prep-3fab808178cf8ad71d88", identity_version="identity-reviewed-29d880765c1623764940",
        sample_version="sample-3bc69e2cc4f843242018", design_id=cfg["parent_design_id"],
        n=24917, target_catalogue_rows=292, supported_targets=198, unsupported_targets_retained_null=94,
        families={f:len(ids) for f,ids in d.families.items()},
        interval="raw A*Y +/- familycritical * protectedscale(Y) * frozentailweight; clip to logical range; constantY returns fullrange",
        no_standard_error_or_p_value_claim=True, coverage="rank theorem >=99% for each frozen referenceworld/family over calibration and new synthetic archive; real-world inclusion unknown; not global198 target coverage",
        required_worlds=sorted(required), stress_worlds=cfg["outside_calibration_stress"],
        actual_football_intervals_generated=False, fourth_major_step_status="not_run",
        sensitivity_rule="Changed schedule/sample/A/q/targets require fresh calibration and tests before intervals; changed-target point-only sensitivity must be labelled descriptive",
        output_columns=["target_id","family","status","point_probability_scale","lower_probability_scale","upper_probability_scale","method_id","calibration_id","scope","unsupported_reason"],
        no_causal_or_prospective_claim=True, human_review="not_performed",
        artifacts={p.relative_to(ROOT).as_posix():sha(p) for p in [ROOT/CFG,ROOT/cfg["tail_weights"],BASE/"model_selection.json",BASE/"calibration.json",out/"review.json"]},
        audit="outputs/logs/reliability/joint-envelope-20261028/readiness-final/review.json")
    write_json(BASE / "fourth_step_contract.json", contract)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
