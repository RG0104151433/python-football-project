"""Prepare Q4 step 2. No standard error, p-value or confidence interval."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from src.reliability.design import build_design, design_diagnostics, require, sha


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def csv_bytes(records):
    columns = list(dict.fromkeys(key for row in records for key in row))
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, columns, lineterminator="\n")
    writer.writeheader()
    for row in records:
        writer.writerow({k: format(v, ".17g") if isinstance(v, float) else v for k, v in row.items()})
    return out.getvalue().encode("utf-8-sig")


def run(root=ROOT, config="config/reliability_design.json", run_root="outputs/logs/reliability"):
    root = Path(root).resolve()
    destination = (root / run_root).resolve()
    require(destination.is_relative_to(root), "Run directory must stay in repository")
    run_id = "design-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    log = destination / run_id
    log.mkdir(parents=True, exist_ok=False)
    stage = "input_and_target_reconstruction"
    try:
        context = build_design(root, config)
        stage = "design_diagnostics"
        diagnostic = design_diagnostics(context)
        code = {p: sha(root / p) for p in ("scripts/prepare_reliability.py", "src/reliability/__init__.py", "src/reliability/design.py")}
        environment = dict(python=platform.python_version(), numpy=np.__version__, platform=platform.system())
        aid = "design-" + hashlib.sha256(json_bytes(dict(inputs=context["inputs"], code=code, environment=environment))).hexdigest()[:20]
        family_counts = Counter(r["family"] for r in context["catalogue"] if r["target_id"] in context["vectors"])
        summary = dict(schema_version="reliability-design-summary-v1", analysis_id=aid, config_path=config,
                       n_parent_matches=len(context["facts"]), catalogue_rows=len(context["catalogue"]),
                       supported_targets=len(context["vectors"]), unsupported_targets=len(context["catalogue"]) - len(context["vectors"]),
                       families=dict(family_counts), global_schedule=diagnostic["global_schedule"], family_ranks=diagnostic["family_ranks"],
                       overlap_rows=len(diagnostic["target_overlap"]),
                       competition_context=dict(n_labels=len({r["tournament_name"] for r in context["competition_context"]}),
                                                n_edition_ids=0, n_round_ids=0, role="dependence metadata only, not new target conditioning or a genuine edition identifier"),
                       maximum_source_reconstruction_tolerance_probability=1e-11,
                       status="design_prepared_not_method_validated", inference="not_run", sensitivity="not_run", simulation="not_run",
                       selected_estimator=None, human_review="not_performed",
                       limitations=["Design overlap does not establish nonzero covariance or independence.",
                                    "Supported point targets have not passed interval-method acceptance.",
                                    "Sparse layers are reported, not removed by an arbitrary count threshold.",
                                    "Coefficient algebraic rank is not covariance rank or effective sample size.",
                                    "Fixed-schedule retrospective target; no future, causal or world-census guarantee.",
                                    "Competition names are recovered from raw source records; genuine edition/round, pre-match strength and exogenous network remain unavailable."])
        table_dir = f"outputs/tables/reliability/{aid}"
        artifacts = {
            "target_catalogue.csv": csv_bytes(context["catalogue"]),
            "coefficient_recipes.csv": csv_bytes(context["components"]),
            "competition_context.csv": csv_bytes(context["competition_context"]),
            **{key + ".csv": csv_bytes(diagnostic[key]) for key in ("target_support", "team_exposure", "year_exposure", "target_overlap", "dyad_schedule", "calendar_counts")},
            "summary.json": json_bytes(summary),
            "checks.json": json_bytes(dict(status="passed_design_only", n_checks=len(context["checks"]), checks=context["checks"],
                                            inference="not_run", simulation="not_run", human_review="not_performed")),
            "data_dictionary.md": ("# Q4第二步数据字典\n\n"
                "本目录只包含目标重建和设计诊断，没有统计推断结果。CSV为UTF-8 BOM、LF，浮点显式17位有效数字。\n\n"
                "- target_catalogue：完整292个目标，来源表/行/列/单位、家族、可计算状态及缺层；概率为内部尺度，展示乘100。supported_point_target不表示方法已验收。\n"
                "- coefficient_recipes：按组件重建逐场系数；Q1/Q2按era/year/type与scope/period筛选，Q3按region_target/group成员再筛层。组件multiplier*q_numerator/q_denominator/n逐次相加；正参考空层使整个目标不可估，不得跳过。\n"
                "- target_support：按非零合并系数记录球队/年份/对子、正参考组件最小场数及1/2场组件；l1/l2、最大单场系数和集中度仅为设计诊断。\n"
                "- team_exposure：双方角色出场数、有符号/绝对系数和。incident_absolute_mass_share每队取两个角色占总逐场绝对系数质量的比例；所有球队该比例加总为2，不是概率分布。\n"
                "- year_exposure：逐目标年份出场及系数质量；不能由此证明时间关联只持续一年。\n"
                "- target_overlap：可计算目标两两共享比赛/任一角色球队/年份；零共享比赛也可能相关。不是协方差矩阵。\n"
                "- dyad_schedule：忽略主客方向的球队对子重复次数，仅供依赖诊断；估计主胜时方向仍保留。\n"
                "- calendar_counts：年/月×赛事类型场数；没有精确赛事届次/轮次，不冒称赛事独立群已知。\n"
                "- competition_context：原快照按source_record_id核对日期/比分/场地后取回赛事原名，届次/轮次明确为空。赛事名×年份不能直接充当真实届次或独立聚类。它是依赖背景资料，不改变本步既有目标条件和系数。\n"
                "- summary：全局赛程/依赖机会和各家族规范化系数行数值秩（阈值1e-10）。不代表独立样本量或未知协方差的秩。\n"
                "- checks：真实版本/成员/系数与原结果对应核对；不是模型覆盖率检验。\n").encode("utf-8"),
        }
        stage = "input_stability"
        for p, expected in {**context["inputs"], **context["parent_outputs"], **code}.items():
            require(sha(root / p) == expected, "Input or old output changed during run:" + p)
        stage = "publish"
        output = root / table_dir
        if output.exists():
            require(set(p.name for p in output.iterdir()) == set(artifacts), "Existing design output has different file set")
            for name, content in artifacts.items():
                require((output / name).read_bytes() == content, "Existing design output differs:" + name)
        else:
            output.mkdir(parents=True, exist_ok=False)
            for name, content in artifacts.items():
                (output / name).write_bytes(content)
        hashes = {table_dir + "/" + name: sha(output / name) for name in artifacts}
        manifest = dict(schema_version="reliability-design-run-v1", status="completed_design_only", analysis_id=aid, run_id=run_id,
                        inputs=context["inputs"], parent_outputs_unchanged=context["parent_outputs"], code=code,
                        environment=environment, outputs=hashes, summary=summary,
                        code_state="Content hashes identify execution; no commit created or claimed", config_path=config)
        (log / "run_manifest.json").write_bytes(json_bytes(manifest))
        print(json.dumps(dict(analysis_id=aid, manifest=(log / "run_manifest.json").relative_to(root).as_posix(),
                              supported=summary["supported_targets"], unsupported=summary["unsupported_targets"], checks=len(context["checks"])), ensure_ascii=False))
        return manifest
    except Exception as exc:
        (log / "failure.json").write_bytes(json_bytes(dict(stage=stage, error_type=type(exc).__name__, error=str(exc), status="failed", inference="not_run")))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/reliability_design.json")
    parser.add_argument("--run-root", default="outputs/logs/reliability")
    args = parser.parse_args()
    run(config=args.config, run_root=args.run_root)
