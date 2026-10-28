"""Summarize completed joint-method selection without generating real intervals."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from pathlib import Path
import sys
import json
import csv
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.reliability.experiment import actual_design, write_json, write_csv
from src.reliability.design import sha


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def main():
    base = ROOT / "outputs/logs/reliability/joint-envelope-20261028"
    if (base / "method_adjudication.json").exists():
        raise RuntimeError("Preserve adjudication; use a new summary version")
    review = read(base / "readiness-final/review.json")
    if not review["all_passed"]:
        raise RuntimeError("Do not summarize a failed audit as approved")
    cfg = read(ROOT / "config/reliability_joint_v15.json")
    d, binding = actual_design(ROOT)
    diagnostics, runpaths, cpu, wall = [], [], 0., 0.
    for stage in ("calibration", "validation", "holdout"):
        folder = ROOT / review["runpaths"][stage]
        manifest = read(folder / "manifest.json")
        cpu += manifest["summary"]["cpu_seconds_workers"]
        wall += manifest["summary"]["wall_seconds"]
        runpaths.append((folder / "manifest.json").relative_to(ROOT).as_posix())
        if stage == "calibration":
            continue
        moments = read(folder / "target_error_moments.json")
        for sid, fields in moments.items():
            n = manifest["summary"]["counts"][sid]
            mean = np.asarray(fields["sum"]) / n
            square = np.asarray(fields["sumsq"]) / n
            variance = np.maximum((square - mean**2)*n/(n-1), 0)
            mcse = np.sqrt(variance/n)
            for j, tid in enumerate(d.targets):
                diagnostics.append(dict(stage=stage, scenario=sid, target_id=tid,
                    family=next(f for f, ids in d.families.items() if j in ids), R=n,
                    empirical_bias=float(mean[j]), empirical_RMSE=float(np.sqrt(square[j])),
                    Monte_Carlo_SE_of_bias=float(mcse[j]),
                    diagnostic_standardized_bias=float(mean[j]/mcse[j]) if mcse[j] > 0 else None,
                    not_a_football_p_value=True))
    write_csv(base / "bias_diagnostics.csv", diagnostics)
    with (base / "readiness-final/validated_metrics.csv").open(encoding="utf-8-sig", newline="") as stream:
        metrics = list(csv.DictReader(stream))
    outside = [r for r in metrics if r["required"] == "False"]
    cal = read(base / "calibration.json")
    decision = dict(decision_log_id="R20261028-03", method="J-RMC6-T-v15",
        selected_as_primary=True, scope="validated model-conditional working method only",
        global_optimality_proved=False, raw_model="J1_restricted_coarse@0.1", six_kernel_parsimony_tolerance=.01,
        joint_mean_common_wave_implemented=True, finite_reference_worlds=32,
        rank_calibration_alpha=.01, exact_rank_coverage_over_calibration_and_new_archive=.99,
        real_law_membership_certified=False, every_family_separate=True,
        final_validation=review["validation"], calibration_critical=cal["critical"],
        mean_CORE_width_reduction_vs_bounded_reference=review["CORE_width_reduction"],
        outside_reference_stress=outside,
        graph_route="G4 kept as conditional finite-bound reference; no independence graph is fact certified",
        rejected_copula_route="Old P0-P3 insufficient coverage/cost; history retained, not production",
        rejected_v14="new-parameter C16 ROLLING945/1000, lower99=.925885; not admitted",
        budget=dict(final_CPU_seconds_workers=cpu, final_stage_wall_seconds_sum=wall,
            formal_cap_CPU_hours=24, below_cap=cpu < 24*3600,
            excludes_worker_initialization_and_audit=True,
            no_B999_nested_bootstrap="Different algorithm and finite-rank theorem; not a reduced-count substitute for old failed protocol"),
        actual_football_intervals=False, fourth_major_step="not_run_ready_with_scope_labels",
        human_review="not_performed", tests=70, audit_checks=review["checks"],
        audit=review["runpaths"], source_hashes={"scripts/summarize_joint_handoff.py":sha(Path(__file__))})
    write_json(base / "method_adjudication.json", decision)
    allruns = []
    roots = ["joint-20261028", "joint-v10-20261028", "joint-final-20261028", "joint-chosen-20261028", "joint-envelope-20261028"]
    for stem in roots:
        for pointer in sorted((ROOT / "outputs/logs/reliability" / stem).glob("*_latest.json")):
            r = read(pointer)
            p = ROOT / r["directory"] / "manifest.json"
            allruns.append(dict(pointer=pointer.relative_to(ROOT).as_posix(), manifest=p.relative_to(ROOT).as_posix(), sha256=sha(p)))
    write_json(base / "current_runs.json", dict(decision_log_id="R20261028-03", runs=allruns,
        development_only_versions=["v12", "v13"], independent_replication_of_real_football=False))
    display = dict(title="从漏掉慢波动到联合估计与独立校准", decision_log_id="R20261028-03",
        method="J-RMC6-T-v15", workflow=["冻结原三问目标", "修正均值投影后的关联方程", "联合恢复均值与共同波动", "开发选择并冻结尺度", "独立校准", "独立测试和新参数留出", "带限制交接"],
        findings=dict(old_P3_C09_conditional_coverage="5/10; development failure, not comparable sample size",
            v14_new_parameter_failure="C16 ROLLING945/1000, not admitted",
            v15_validation_minimum=.986, v15_holdout_minimum=.991,
            CORE_mean_width=review["validation"]["validation"]["family_mean_width"]["CORE"],
            CORE_reference_width=review["CORE_bounded_reference_mean_width"],
            CORE_width_reduction=review["CORE_width_reduction"],
            conditional_mean_span_fraction=review["validation"]["validation"]["family_span_fraction"]["CONDITIONAL"]),
        limitations=["模拟支持明确参照世界，真实足球联合分布未知", "永久全局冲击压力测试仍失败", "条件胜率区间仍较宽", "工作均值不是概率预测", "第四大步真实推断及敏感性未运行"],
        sources={p.relative_to(ROOT).as_posix():sha(p) for p in [base/"readiness-final/review.json",base/"method_adjudication.json",base/"fourth_step_contract.json"]})
    write_json(base / "display_data.json", display)
    write_json(base / "summary_manifest.json", dict(executor="Codex AI; uncommitted", human_review="not_performed",
        source_sha256=sha(Path(__file__)), outputs={p.relative_to(ROOT).as_posix():sha(p) for p in [base/"bias_diagnostics.csv",base/"current_runs.json",base/"method_adjudication.json",base/"display_data.json"]}))
    print(json.dumps(dict(CPU_seconds=cpu, wall_seconds_sum=wall, diagnostics=len(diagnostics), runs=len(allruns))))


if __name__ == "__main__":
    main()
