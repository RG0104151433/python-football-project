"""Versioned table contracts, deterministic plots, limitations and publication."""
from __future__ import annotations
import io
import json
from pathlib import Path

from ..data_contract import PrepError, atomic_bytes, csv_bytes, digest, file_hash, json_bytes, project_path
from .data import GROUPS, require

COUNTS = "n_matches n_home_wins n_draws n_away_wins home_win_rate draw_rate away_win_rate status"
UNCERTAINTY = "standard_error ci_lower ci_upper confidence_level method_id method_version uncertainty_status status"
FIELDS = {
    "analysis_membership": "data_version identity_version sample_id match_id source_record_id date analysis_era_id tournament_group included primary_exclusion_reason exclusion_reasons",
    "sample_flow": "flow_id stage parent_stage reason n_records basis status",
    "grouped_counts": "scope period_id start_date end_date n_calendar_years tournament_group " + COUNTS,
    "reference_weights": "reference_id scope period_id stratum_kind stratum_id n_reference_matches n_reference_total weight status",
    "type_estimates": "estimate_id sample_id scope period_id tournament_group estimand reference_id n_matches estimate unit " + UNCERTAINTY,
    "type_differences": "contrast_id sample_id scope period_id estimand reference_id n_friendly n_non_friendly estimate unit " + UNCERTAINTY,
    "rolling_windows": "window_id start_date end_date label_year n_calendar_years n_observed_years n_matches missing_years status",
    "rolling_counts": "window_id tournament_group " + COUNTS,
    "window_membership": "window_id match_id",
}
KEYS = {"analysis_membership": "match_id", "sample_flow": "flow_id stage reason", "grouped_counts": "scope period_id tournament_group",
        "reference_weights": "reference_id stratum_id", "type_estimates": "estimate_id", "type_differences": "contrast_id",
        "rolling_windows": "window_id", "rolling_counts": "window_id tournament_group", "window_membership": "window_id match_id"}
LIMITATIONS = [
    dict(id="archive_scope", text="结果限于当前档案和筛选范围，不代表全球全部比赛的无偏样本；数据最终冻结尚未完成。"),
    dict(id="selection_strength", text="赛事选择、对手实力、地区和参赛者可能混杂；时间调整后的差不是赛事类型的因果效应。"),
    dict(id="time_resolution", text="全时期只统一五年代比例，滚动补充统一窗内年份；都没有统一球队构成。"),
    dict(id="reference_choice", text="参考代表当前档案构成，起点和十年宽度没有最优性证明；末组仅五年，其他非友谊赛事内部也有差异。"),
    dict(id="overlapping_windows", text="相邻十年窗共享九年，曲线不是36份独立证据；平滑可掩盖突变，窗口参考和参赛者会变化。"),
    dict(id="shared_q1_information", text="两问主分析共用十单元表，第二问是进一步解释，不是独立验证。"),
    dict(id="inference_not_run", text="共享球队、主客角色、共同时间冲击和滚动联合推断未验收；无正式区间、显著性或预测结论。"),
]


def sorted_rows(name, rows):
    fields, keys = set(FIELDS[name].split()), KEYS[name].split()
    require(all(set(r) == fields for r in rows), "TQ_RECONCILIATION_FAILED", "Fields: "+name)
    values = [tuple(r[k] for k in keys) for r in rows]
    require(len(values) == len(set(values)), "TQ_RECONCILIATION_FAILED", "Duplicate table keys: "+name)
    return sorted(rows, key=lambda r: tuple(r[k] for k in keys))


def dictionary():
    meanings = dict(data_version="基础清洗版本", identity_version="本次成员采用版本", sample_id="完整分析样本指纹，不是每个子组的样本量",
        match_id="原比赛稳定ID", source_record_id="原始快照逐行定位", date="比赛ISO日期", analysis_era_id="研究年代，范围外为空",
        tournament_group="friendly或non_friendly；追踪表可保留未纳入的未知组", included="是否纳入本次两问共用样本",
        primary_exclusion_reason="互斥主排除原因", exclusion_reasons="完整排除原因JSON数组", flow_id="计数层标识", stage="流程阶段",
        parent_stage="上级流程", reason="去向原因", basis="原始与清洗计数层，禁止跨层重复扣减", status="数值可用或不可用状态",
        scope="overall/era/year/rolling中的适用范围", period_id="all、年代ID、年份或窗口ID", start_date="含首日", end_date="含末日",
        n_calendar_years="日历年份数，末年代五年，滚动十年", n_observed_years="至少一场比赛的年份数", n_matches="真实支持比赛数，非标准化伪场数",
        n_home_wins="主胜整数场数", n_draws="平局整数场数，仍在主胜率分母", n_away_wins="客胜整数场数",
        home_win_rate="主胜数/场数", draw_rate="平局数/场数", away_win_rate="客胜数/场数", reference_id="共同时间参考ID，raw为空",
        stratum_kind="era或year", stratum_id="权重对应年代或年份", n_reference_matches="参考层两类合计场数",
        n_reference_total="参考总体两类合计场数", weight="该层场数/参考总场数，两类共用", estimate_id="唯一的率目标ID",
        contrast_id="唯一类型差ID，方向F减N", estimand="raw/era_standardized/year_standardized", estimate="按unit解释的完整精度计算结果",
        unit="probability为0到1；percentage_points为百分点", standard_error="未计算，空", ci_lower="未计算，空", ci_upper="未计算，空",
        confidence_level="未计算，空", method_id="未验收推断，空", method_version="未验收推断，空", uncertainty_status="固定not_run",
        n_friendly="该目标范围真实友谊赛场数", n_non_friendly="该目标范围真实其他赛事场数", window_id="十个完整公历年窗口ID",
        label_year="窗口末年，非单年水平", missing_years="两类合计无比赛年份的JSON数组", n_records="流程该去向记录数")
    lines = ["# 第二问字段字典：tournaments-tables-v1", "", "CSV UTF-8 BOM、LF；浮点十位小数，整数计数，小写布尔，数组JSON。",
             "空数值表示不可算/未运行，不等于零。所有差为友谊赛减其他非友谊赛事。", ""]
    for name, fields in FIELDS.items():
        lines += ["## "+name+".csv", "", "唯一键与排序："+KEYS[name], ""]
        for f in fields.split():
            kind = "integer" if f.startswith("n_") or f == "label_year" else "boolean" if f == "included" else "JSON array" if f in ("missing_years", "exclusion_reasons") else "decimal" if f in ("weight", "estimate", "standard_error", "ci_lower", "ci_upper", "confidence_level") or f.endswith("_rate") else "string"
            unit = "probability" if f == "weight" or f.endswith("_rate") else "见unit列" if f in ("estimate", "standard_error", "ci_lower", "ci_upper") else "records" if f.startswith("n_") and "year" not in f else "years" if "year" in f and kind == "integer" else "not applicable"
            lines.append(f"- {f}: {kind}; unit={unit}; {meanings[f]}。")
        lines.append("")
    lines += ["## 状态与目标重建", "", "ok/empty_group/missing_stratum/empty_reference/not_estimable；参考另含zero_weight。",
              "正权重缺一类则标准化为空；双方空年权重零，保留日历窗口并跳过不可算均值。",
              "target_definitions.json给出每个目标的范围、公式、符号、权重和分母来源；据此连接清洗比分和窗口成员，可重建逐场系数。",
              "参考标识仅在本analysis_id内解释；sample_id与成员/分析身份同时绑定。无协方差或置信区间文件。", ""]
    return "\n".join(lines).encode("utf-8")


def table_artifacts(tables, definitions, aid):
    folder = "outputs/tables/tournaments/"+aid
    result = {f"{folder}/{name}.csv": csv_bytes(FIELDS[name].split(), sorted_rows(name, rows)) for name, rows in tables.items()}
    result[folder+"/data_dictionary.md"] = dictionary()
    result[folder+"/target_definitions.json"] = json_bytes(dict(schema_version="tournaments-targets-v1", targets=sorted(definitions, key=lambda d: d["target_id"]),
        reconstruction="For each term: multiplier * stratum_weight / count_of_type_in_stratum for each eligible match; raw uses weight 1 and its scope/period. Zero-weight strata contribute zero. No inferential covariance is estimated."))
    return result


def figure_artifacts(tables, analysis, aid):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    result = {}
    with matplotlib.rc_context({"svg.hashsalt": "tournaments-v1", "font.family": "DejaVu Sans"}):
        def save(fig, name):
            fig.text(.015, .012, f"Descriptive only; F - N; no confidence intervals. {aid}", fontsize=7)
            fig.tight_layout(rect=(0, .06, 1, 1))
            for ext in ("png", "svg"):
                data = io.BytesIO()
                fig.savefig(data, format=ext, dpi=220, metadata={"Date": None} if ext == "svg" else {})
                result[f"outputs/figures/tournaments/{aid}/{name}.{ext}"] = data.getvalue()
            plt.close(fig)
        def value(scope, period, metric, g=None):
            collection = tables["type_differences" if g is None else "type_estimates"]
            row = next(r for r in collection if r["scope"] == scope and r["period_id"] == period and r["estimand"] == metric and (g is None or r["tournament_group"] == g))
            return np.nan if row["estimate"] is None else row["estimate"] * (1 if g is None else 100)
        fig, axes = plt.subplots(1, 2, figsize=(10, 5))
        for g, offset, label in (("friendly", -.18, "Friendly"), ("non_friendly", .18, "Other non-friendly")):
            axes[0].bar(np.arange(2)+offset, [value("overall", "all", e, g) for e in ("raw", "era_standardized")], width=.36, label=label)
        axes[0].set(xticks=[0,1], xticklabels=["Observed", "Common era mix"], ylabel="Home wins (%)", ylim=(0,100), title="Two tournament types")
        axes[0].legend(fontsize=8)
        vals = [value("overall", "all", e) for e in ("raw", "era_standardized")]
        axes[1].bar([0,1], vals)
        for x, v in enumerate(vals):
            if np.isfinite(v): axes[1].annotate(f"{v:+.3f} pp", (x,v), xytext=(0,-15 if v < 0 else 5), textcoords="offset points", ha="center", fontsize=9)
        axes[1].axhline(0, color="black", linewidth=.7)
        axes[1].set(xticks=[0,1], xticklabels=["Observed", "Common era mix"], ylabel="Friendly minus other (pp)", title="Overall descriptive gap")
        axes[1].margins(y=.25)
        save(fig, "overall_comparison")
        fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
        eras = analysis["eras"]
        for g, label in (("friendly", "Friendly"), ("non_friendly", "Other non-friendly")):
            axes[0].plot(range(len(eras)), [value("era",e["id"],"raw",g) for e in eras], "o-", label=label)
        axes[0].set(ylabel="Home wins (%)", title="Within-era tournament comparison (zoomed rate scale)")
        axes[0].legend()
        axes[1].plot(range(len(eras)), [value("era",e["id"],"raw") for e in eras], "o-", color="purple")
        axes[1].axhline(0, color="black", linewidth=.7)
        axes[1].set(ylabel="Friendly minus other (pp)", xticks=range(len(eras)), xticklabels=[e["label"] for e in eras])
        for ax in axes: ax.grid(alpha=.2)
        save(fig, "era_comparison")
        fig, ax = plt.subplots(figsize=(10,5))
        windows = sorted(tables["rolling_windows"], key=lambda w: w["label_year"])
        for e, style, label in (("raw", "-", "Observed within window"), ("year_standardized", "--", "Common year mix within window")):
            ax.plot([w["label_year"] for w in windows], [value("rolling",w["window_id"],e) for w in windows], style, label=label)
        ax.axhline(0, color="black", linewidth=.7)
        ax.set(xlabel="End year of trailing 10-calendar-year window (adjacent windows overlap)", ylabel="Friendly minus other (pp)", title="Rolling tournament gap; window reference changes over time")
        ax.grid(alpha=.2); ax.legend(fontsize=8)
        save(fig, "rolling_comparison")
    return result


def publish(root, artifacts):
    for relative, content in artifacts.items():
        p = project_path(root, relative)
        require(not p.exists() or file_hash(p) == digest(content), "TQ_REPRODUCIBILITY_MISMATCH", relative)
    for relative, content in sorted(artifacts.items()):
        p = project_path(root, relative)
        if not p.exists(): atomic_bytes(p, content)
    return {p: digest(data) for p, data in sorted(artifacts.items())}


def verify_run(root, relative):
    manifest = json.loads(project_path(root, relative).read_text(encoding="utf-8"))
    require(manifest.get("schema_version") == "tournaments-run-v1" and manifest.get("status") == "completed",
            "TQ_INPUT_HASH_MISMATCH", "Only completed Q2 manifests can be verified")
    for kind in ("inputs", "outputs", "code_hashes"):
        for p, expected in manifest[kind].items():
            require(project_path(root,p).is_file() and file_hash(project_path(root,p)) == expected, "TQ_INPUT_HASH_MISMATCH", f"{kind}: {p}")
    return dict(passed=True, analysis_id=manifest["analysis_id"], verified_outputs=len(manifest["outputs"]), inference="not_run")
