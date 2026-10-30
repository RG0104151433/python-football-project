"""Immutable output bundles including exact joint source, tests and protocol."""
from pathlib import Path
import io
import json
import zipfile
from src.data_contract import atomic_bytes, csv_bytes, file_hash, fingerprint, write_json
from src.strength.io import ROOT, environment


def sources():
    paths = [*ROOT.glob("src/strength_joint/*.py"), ROOT / "scripts/analyze_strength_joint.py",
             ROOT / "scripts/audit_strength_joint.py", ROOT / "tests/test_strength_joint.py", ROOT / "config/strength_joint.json"]
    return {p.relative_to(ROOT).as_posix(): file_hash(p) for p in sorted(paths) if p.exists()}


def publish(kind, identity, csvs=None, jsons=None, texts=None):
    identity = dict(identity, code=sources(), environment=environment())
    stage_id = kind + "-" + fingerprint(identity)[:20]
    folder = ROOT / "outputs/tables/strength_joint" / stage_id
    content = {}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as z:
        for name in sorted(identity["code"]):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            z.writestr(entry, (ROOT / name).read_bytes())
    content["source_snapshot.zip"] = archive.getvalue()
    for name, rows in (csvs or {}).items():
        if not rows:
            raise ValueError("Empty output needs explicit schema: " + name)
        content[name] = csv_bytes(list(rows[0]), rows)
    for name, obj in (jsons or {}).items():
        content[name] = (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    content.update({name: value.encode("utf-8") for name, value in (texts or {}).items()})
    for name, value in content.items():
        path = folder / name
        if path.exists() and path.read_bytes() != value:
            raise ValueError("Artifact collision: " + str(path))
    for name, value in content.items():
        atomic_bytes(folder / name, value)
    manifest = dict(stage_id=stage_id, identity=identity, outputs={name: file_hash(folder / name) for name in content})
    write_json(folder / "manifest.json", manifest)
    return folder


def metrics(result, rows, probabilities):
    import numpy as np
    y = np.array([int(r["home_win"]) for r in rows])
    return dict(model_id=result["model_id"], matches=len(rows), parameters=result["parameters"],
        binary_home_log_loss=result["loss"], brier=float(np.mean((probabilities - y) ** 2)),
        home_binary_accuracy=float(np.mean((probabilities >= .5) == y)), observed_home_rate=float(y.mean()),
        fitted_home_rate=float(probabilities.mean()), mean_bias=float((probabilities - y).mean()),
        gradient=result["gradient"], multistart_loss_spread=result["multistart_loss_spread"],
        curvature_min=result["curvature_min"], rank=result["rank"], numerical_fit_passed=result["numerical_fit_passed"],
        evaluation_role="retrospective_in_sample_not_future_prediction", inference_status="INFERENCE_NOT_ADMITTED")


def calibration(rows, probabilities, model):
    import numpy as np
    output = []
    for field in ("era", "tournament_group", "home_region", "away_region"):
        for label in sorted({r[field] for r in rows}):
            mask = np.array([r[field] == label for r in rows])
            y = np.array([int(r["home_win"]) for r in rows])[mask]; p = probabilities[mask]
            output.append(dict(model_id=model, grouping=field, group=label or "unknown", matches=len(y),
                observed_home_rate=float(y.mean()), fitted_home_rate=float(p.mean()), bias_pp=float(100 * (p - y).mean()),
                role="in_sample_misfit_diagnostic_not_independent_validation"))
    return output


DICTIONARY = """# 第五问第三环节共同分析输出

原24917场，主胜=1、平局/客胜=0，平局保留分母；五地理大区不是六足联。
model_metrics.csv：二元主胜样本内损失/准确率，不能与第二环节三结果损失直接比较；不称未来预测能力。
coefficients.csv及models.json：潜在尺度参数、三初值、秩、梯度和局部曲率；系数不是百分点或因果效应，无未经验证SE。
joint_predictions.csv：一场一行，原标签/地区/信息截止及各模型拟合概率；结果模型使用全期估计，不能当真正赛前预测。
contrasts.csv：32个原CORE目标的映射、两情景概率/百分点差、参考ID与外推诊断。原目录32项中27可算、5缺层；新参考不同，same_estimand_as_old=false。
strength_changes.csv：在同一新参考下无实力/有实力的率差及变化，不称解释比例。
support.csv：每个目标/模型的零单元、稀疏、评分范围外比例；细胞/极值检验不是充分的共同支持证明。
sensitivity.csv：明确记录变更什么、保留什么；初始化仅均值替换不是完整分布敏感性。
validation.json：数值/优化/反馈试算和统计推断分开，区间INFERENCE_NOT_ADMITTED时为空。
display_data.json：同版展示取数，不是最终HTML或论文。
所有CSV为UTF-8 BOM、LF、固定小数，缺项为空；原数据与前三问结果不覆盖。
"""
