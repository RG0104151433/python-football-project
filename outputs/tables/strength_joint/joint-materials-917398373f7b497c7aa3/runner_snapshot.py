"""Generate static research figures and bound handoff evidence from actual outputs."""
from pathlib import Path
import io
import json
import sys
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data_contract import file_hash, write_json
from src.strength.io import read_rows
from src.strength_joint.reporting import publish


def run():
    pointer = json.loads((ROOT / "outputs/logs/strength_joint/analysis_pointer.json").read_text())
    folder = ROOT / pointer["directory"]
    audit_path = ROOT / "outputs/logs/strength_joint" / (folder.name + "-audit.json")
    audit = json.loads(audit_path.read_text())
    if not audit["passed"]:
        raise ValueError("Independent audit not passed")
    suite = ET.parse(ROOT / "outputs/logs/strength_joint/all_strength_tests.xml").getroot().find("testsuite")
    if int(suite.get("failures")) or int(suite.get("errors")):
        raise ValueError("Tests failed")
    rows = read_rows(folder / "strength_changes.csv")
    display = json.loads((folder / "display_data.json").read_text())
    labels = {
        "Q1:2010s_minus_1980s:adjusted": "2010年代 − 1980年代",
        "Q1:2020_2024_minus_1980s:adjusted": "2020—2024 − 1980年代",
        "Q2:difference:overall:all:era_standardized": "友谊赛 − 其他赛事",
        "Q3:B_ASIA:adjusted": "亚洲主队：洲外 − 同分区对手",
        "Q3:B_EUR:adjusted": "欧洲主队：洲外 − 同分区对手",
        "Q3:C_AFR_015_VS_OTHER:adjusted": "北非 − 其余撒哈拉以南"
    }
    chosen = [next(r for r in rows if r["target_id"] == tid and r["reference_kind"] == "full") for tid in labels]
    available = {f.name for f in font_manager.fontManager.ttflist}
    selected_font = next((f for f in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC") if f in available), "DejaVu Sans")
    plt.rcParams.update({"font.family": selected_font, "axes.unicode_minus": False, "svg.hashsalt": "strength-joint-v1"})
    images = {}
    fig, ax = plt.subplots(figsize=(10, 5.5), layout="constrained")
    positions = list(range(len(chosen)))
    ax.scatter([float(r["without_strength_pp"]) for r in chosen], positions, label="不含实力的共同模型", s=45, color="#59788e")
    ax.scatter([float(r["with_strength_pp"]) for r in chosen], positions, label="加入赛前实力（含不确定性）", s=45, color="#b57b40")
    for i, r in enumerate(chosen):
        ax.plot([float(r["without_strength_pp"]), float(r["with_strength_pp"])], [i, i], color="0.65", linewidth=1)
    ax.axvline(0, color="0.5", linewidth=.8)
    ax.set(yticks=positions, yticklabels=[labels[r["target_id"]] for r in chosen], xlabel="同一新参考条件下的主胜概率差（百分点）",
           title="加入赛前实力后，原组别差异怎样变化？")
    ax.invert_yaxis(); ax.legend(loc="upper right", fontsize=9)
    fig.text(.5, -.015, "1980—2024，同24917场。回顾性工作模型点估计，含外推；未验收区间，不表示因果或显著性。", ha="center", fontsize=9)
    for extension in ("png", "svg"):
        stream = io.BytesIO(); fig.savefig(stream, format=extension, dpi=160, bbox_inches="tight", metadata={"Date": None} if extension == "svg" else {})
        images["strength_adjustment." + extension] = stream.getvalue()
    plt.close(fig)
    main = [r for r in read_rows(folder / "contrasts.csv") if r["model_id"] == "M3_nested"]
    full = {r["target_id"]: r for r in main if r["reference_kind"] == "full"}
    overlap = {r["target_id"]: r for r in main if r["reference_kind"] == "cell_range_overlap"}
    retained = [int(overlap[tid]["reference_rows"]) / int(full[tid]["reference_rows"]) for tid in labels]
    fig, ax = plt.subplots(figsize=(10, 5.5), layout="constrained")
    ax.barh(positions, [100 * n for n in retained], color="#59788e")
    ax.set(yticks=positions, yticklabels=list(labels.values()), xlim=(0, 100), xlabel="双方情景都满足非空单元及评分范围条件的参考比例（%）",
           title="哪些共同条件有实际对照，哪些依赖外推？")
    ax.invert_yaxis()
    for i, n in enumerate(retained):
        ax.text(100 * n + 1, i, f"{100*n:.1f}%", va="center", fontsize=9)
    fig.text(.5, -.015, "这是预定粗分组/范围的支持诊断，不是充分的共同支持证明；辅助参考的估计对象已改变。", ha="center", fontsize=9)
    for extension in ("png", "svg"):
        stream = io.BytesIO(); fig.savefig(stream, format=extension, dpi=160, bbox_inches="tight", metadata={"Date": None} if extension == "svg" else {})
        images["reference_support." + extension] = stream.getvalue()
    plt.close(fig)
    global_path = ROOT / "outputs/logs/strength_joint/global_feedback.json"
    global_report = json.loads(global_path.read_text())
    if not global_report["all_engineering_checks_passed"]:
        raise ValueError("Global feedback pilot incomplete")
    repeat_path = ROOT / "outputs/logs/strength_joint/reproducibility.json"
    repeat_report = json.loads(repeat_path.read_text())
    if not repeat_report["passed"] or repeat_report["original"] != pointer["directory"]:
        raise ValueError("Core repeat not passed for adopted input")
    # The simulator inherited original context columns, including unused score metadata.
    # Canonical simulation tables keep ONLY fields actually supplied to the joint fit;
    # stale original covariance/rating/initialization metadata must not masquerade as synthetic.
    simulation_csvs = {}; simulation_models = {}; simulation_proofs = []; simulation_checks = 0
    fields = ("match_id", "date", "era", "tournament_group", "home_region", "home_unit", "away_region", "away_unit",
              "home_win", "outcome", "strength_difference", "strength_difference_base_variance", "strength_difference_variance",
              "home_jump_intensity", "away_jump_intensity", "jump_scale_sd", "prediction_cutoff")
    for experiment in global_report["reports"]:
        source = ROOT / experiment["directory"]
        original = read_rows(source / "simulated_study_matches.csv")
        clean = []
        for row in original:
            new = {k: row[k] for k in fields}
            new.update(simulation_world=experiment["world"], simulation_seed=experiment["seed"],
                       strength_source="simulated_history_with_fixed_scoring_rule")
            if any(new[k] != row[k] for k in fields) or row["prediction_cutoff"] >= row["date"]:
                raise ValueError("Simulation materialization changed fitted inputs")
            if abs(float(new["strength_difference_variance"]) - float(new["strength_difference_base_variance"]) -
                   (float(new["home_jump_intensity"]) + float(new["away_jump_intensity"])) * float(new["jump_scale_sd"]) ** 2) > 2e-8:
                raise ValueError("Simulation distribution inconsistency")
            clean.append(new); simulation_checks += 1
        name = experiment["world"]
        simulation_csvs["simulation_inputs_" + name + ".csv"] = clean
        simulation_models["simulation_model_" + name + ".json"] = json.loads((source / "model.json").read_text())
        simulation_proofs.append(dict(source=experiment["directory"], source_manifest_sha=file_hash(source / "manifest.json"),
            canonical_file="simulation_inputs_" + name + ".csv", rows=len(clean), fitted_fields_unchanged=True,
            removed_unused_original_score_metadata=True, replay_required_for_schema_projection=False))
    evidence = dict(analysis=pointer["directory"], analysis_manifest_sha=file_hash(folder / "manifest.json"),
                    audit_path=audit_path.relative_to(ROOT).as_posix(), audit_sha=file_hash(audit_path),
                    tests=int(suite.get("tests")), test_sha=file_hash(ROOT / "outputs/logs/strength_joint/all_strength_tests.xml"),
                    global_feedback_path=global_path.relative_to(ROOT).as_posix(), global_feedback_sha=file_hash(global_path),
                    canonical_simulation_tables=simulation_proofs, simulation_projection_checks=simulation_checks,
                    repeated_core_files=repeat_report["identical_core_files"], repeat_sha=file_hash(repeat_path),
                    global_coverage_admitted=False, final_html_created=False, actual_human_review=False, font=selected_font)
    # Image bytes are preserved as hex-free ordinary artifact files by the same immutable contract.
    from src.data_contract import atomic_bytes
    output = publish("joint-materials", dict(evidence=evidence, runner_sha=file_hash(Path(__file__))),
        csvs=simulation_csvs,
        jsons={"display_data.json": display, "handoff.json": evidence, "independent_audit.json": audit, "global_feedback.json": global_report,
               "reproducibility.json": repeat_report, **simulation_models},
        texts={"runner_snapshot.py": Path(__file__).read_text(encoding="utf-8"),
               "all_strength_tests.xml": (ROOT / "outputs/logs/strength_joint/all_strength_tests.xml").read_text(encoding="utf-8")})
    manifest = json.loads((output / "manifest.json").read_text())
    for name, value in images.items():
        path = output / name
        if path.exists() and path.read_bytes() != value:
            raise ValueError("Figure collision " + name)
        atomic_bytes(path, value); manifest["outputs"][name] = file_hash(path)
    write_json(output / "manifest.json", manifest)
    write_json(ROOT / "outputs/logs/strength_joint/materials_pointer.json", dict(directory=output.relative_to(ROOT).as_posix(), manifest_sha256=file_hash(output / "manifest.json")))
    print("JOINT_MATERIALS", output.relative_to(ROOT).as_posix(), flush=True)


if __name__ == "__main__":
    run()
