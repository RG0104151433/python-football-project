"""Deterministic CSV contracts, plots, publication and run verification."""
import csv
import io
import math
from pathlib import Path

from .io import json_bytes, project_path, read_json, require, sha

COUNTS = "n_matches n_home_wins n_draws n_away_wins home_win_rate draw_rate away_win_rate status"
FIELDS = {
    "analysis_matches": "match_id source_record_id date year era tournament_group home_team_id away_team_id home_team away_team home_score away_score home_win outcome result_basis is_neutral city country home_region home_unit home_rule_id away_region away_unit away_rule_id direction relation A_usable A_reason B_usable B_reason C_usable C_reason",
    "analysis_membership": "target_id match_id group_id included in_reference reason",
    "group_summary": "target_id group_id group_label " + COUNTS + " n_home_teams n_away_teams reference_group standardized_home_win_rate standardization_status standardization_reason",
    "stratum_counts": "target_id group_id era tournament_group " + COUNTS + " group_share",
    "reference_weights": "target_id reference_group era tournament_group n_reference_matches n_reference_total weight status",
    "contrast_results": "contrast_id target_id study_id label arm1 arm2 reference_group n_arm1 n_arm2 direct_arm1_rate direct_arm2_rate adjusted_arm1_rate adjusted_arm2_rate direct_difference direct_difference_pp adjusted_difference adjusted_difference_pp direct_minus_adjusted_pp direct_status adjusted_status reason",
    "layer_contributions": "contrast_id target_id era tournament_group n_arm1 wins_arm1 n_arm2 wins_arm2 arm1_rate arm2_rate weight layer_difference contribution status",
    "team_contributions": "target_id group_id era tournament_group role team_id team_label n_matches denominator share",
    "opponent_composition": "target_id group_id era tournament_group away_region away_unit n_matches denominator share",
    "match_coefficients": "contrast_id target_id method match_id group_id era tournament_group denominator weight coefficient",
}
KEYS = {
    "analysis_matches": "match_id", "analysis_membership": "target_id match_id",
    "group_summary": "target_id group_id", "stratum_counts": "target_id group_id era tournament_group",
    "reference_weights": "target_id era tournament_group", "contrast_results": "contrast_id",
    "layer_contributions": "contrast_id era tournament_group",
    "team_contributions": "target_id group_id era tournament_group role team_id",
    "opponent_composition": "target_id group_id era tournament_group away_region away_unit",
    "match_coefficients": "contrast_id method match_id",
}
LIMITATIONS = [
    "描述当前1980—2024合格非中立档案中的比赛平均主胜率，不代表国家等权或全球无偏样本。",
    "调整只统一年代×赛事构成，未控制具体主客队实力；不是地理的因果作用或纯主场优势。",
    "地域表示球队归属，不是实际旅行距离；历史球队使用已明示的固定载体，未知保留。",
    "不同目标参考不同，不能把跨目标数值拼为全球排名；欧洲内部四组才共享其欧洲参考。",
    "欧洲六个成对差值只有三个独立方向；相关比赛、共同时间冲击、多比较与区间留第四问。",
    "南美地域关系末期跨大区无比赛，全时期调整差不可计算；不删年、不填补。",
    "统计可靠性、分类敏感性和实力调整未运行；独立核算不等于组员已复现或事实全部验证。",
]


def scalar(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        require(math.isfinite(value), "REG_NONFINITE", str(value))
        return format(value, ".17g")
    return str(value)


def csv_content(name, rows, aid):
    fields, keys = FIELDS[name].split(), KEYS[name].split()
    require(all(set(row) == set(fields) for row in rows), "REG_SCHEMA", "Unexpected fields: " + name)
    identifiers = [tuple(row[k] for k in keys) for row in rows]
    require(len(identifiers) == len(set(identifiers)), "REG_DUPLICATE", "Duplicate output key: " + name)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["analysis_id"] + fields, lineterminator="\n")
    writer.writeheader()
    for row in sorted(rows, key=lambda r: tuple(r[k] for k in keys)):
        writer.writerow(dict(analysis_id=aid, **{k: scalar(v) for k, v in row.items()}))
    return buffer.getvalue().encode("utf-8-sig")


def dictionary():
    descriptions = {
        "analysis_id": "稳定分析身份，连接analysis_metadata.json；不是每次运行编号",
        "match_id": "原比赛稳定ID", "source_record_id": "原始快照记录定位", "date": "比赛ISO日期",
        "year": "公历年", "era": "五年代标签，末组仅2020—2024", "tournament_group": "friendly/non_friendly",
        "target_id": "九个成员目标之一", "contrast_id": "预定成对差值ID，多对可属同一目标",
        "group_id": "目标内互斥组，未纳入时空", "study_id": "四项研究标题之一", "group_label": "配置中的组名",
        "home_win": "主胜指示1/0，平局为0", "outcome": "home/draw/away", "result_basis": "加时后且不含点球大战",
        "is_neutral": "本样本固定false", "included": "在该目标某展示/对比组内", "in_reference": "进入该目标参考人群",
        "reason": "纳入/排除或不可估具体原因", "reference_group": "同目标共同参考，不随每对比较变化",
        "arm1": "差值前组", "arm2": "差值后组", "label": "预定差值显示名", "role": "home/away，两个角色分别对账",
        "method": "direct/standardized", "team_id": "原球队身份，不合并历史实体", "team_label": "中文展示名",
        "direction": "主队大区>客队大区", "relation": "same_unit/same_region_diff_unit/cross_region/unknown",
        "denominator": "占比或系数计算的整数分母", "weight": "标准化为参考层场数/参考总数；直接系数固定1",
        "share": "该记录场数/对应整数分母", "group_share": "组内该层场数/组总数",
        "coefficient": "固定设计差值线性和的有符号逐场系数，未估协方差",
        "layer_difference": "该层前组主胜率减后组", "contribution": "共同权重乘层差，零权重层为0",
        "direct_difference": "前后组直接主胜率之差", "adjusted_difference": "共同构成后前组率减后组率",
        "direct_difference_pp": "直接率差乘100", "adjusted_difference_pp": "调整率差乘100",
        "direct_minus_adjusted_pp": "直接差减调整差，单位百分点，不是因果贡献",
        "standardized_home_win_rate": "按本目标共同参考得到的调整主胜率",
        "standardization_status": "ok或正权重层缺比赛", "standardization_reason": "缺失层清单",
    }
    lines = ["# 第三问字段字典：regions-tables-v1", "", "CSV为UTF-8 BOM、LF、固定键排序。数字不预先舍入，浮点按.17g；空数值不等于0。",
             "analysis_id连接同目录元数据中的版本；run_id和时间仅在运行清单。代码字段按字符串保留前导零。",
             "九目标、十二差值、十一调整差可算；无标准误、置信区间、p值或可靠性结论。", ""]
    for name, fields in FIELDS.items():
        lines += ["## " + name + ".csv", "", "主键/稳定排序：" + KEYS[name], ""]
        for field in ["analysis_id"] + fields.split():
            if field in descriptions:
                text = descriptions[field]
            elif field.startswith("n_") or field.startswith("wins_"):
                text = "非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数"
            elif field.endswith("_rate"):
                text = "0—1概率；无比赛或不支持时空，须结合状态列解释"
            elif field in ("status", "direct_status", "adjusted_status"):
                text = "ok/no_matches/zero_weight/unsupported_positive_reference_layer，按表适用"
            elif field.endswith(("_region", "_unit")):
                text = "三位地理字符串代码；空表示未知，不是代码0"
            elif field.endswith("_rule_id"):
                text = "采用版日期规则ID"
            elif field.endswith("_team_id"):
                text = "原主队/客队身份ID"
            elif field.endswith("_usable"):
                text = "true/false，准备阶段的目标资格"
            elif field.endswith("_reason"):
                text = "准备阶段资格原因"
            elif field.endswith("_score"):
                text = "非负整数进球，不含点球大战"
            elif field in ("home_team", "away_team", "city", "country"):
                text = "原清洗表的球队显示名或比赛地点信息，不重判主场"
            else:
                raise ValueError("Undocumented column: " + field)
            lines.append("- " + field + "：" + text + "。")
        lines.append("")
    lines += ["## 状态、缺失与系数", "", "零场的计数为0，率为空；正权重缺层不改变目标/参考。零权重层跳过加权运算。",
              "系数表仅存非零项；零项由完整事实表和成员/差值配置重建。不支持的调整差不导出假系数。",
              "欧洲成员不按六个差值重复分组；六个差值不独立。共同参考或赛程若视为随机，第四问另处理其变动。", ""]
    return "\n".join(lines).encode("utf-8")


def table_artifacts(tables, metadata, aid):
    base = f"outputs/tables/regions/{aid}"
    artifacts = {f"{base}/{name}.csv": csv_content(name, rows, aid) for name, rows in tables.items()}
    artifacts[base + "/data_dictionary.md"] = dictionary()
    artifacts[base + "/analysis_metadata.json"] = json_bytes(metadata)
    return artifacts


def figure_artifacts(tables, config, aid):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    import numpy as np

    try:
        font_manager.findfont("Microsoft YaHei", fallback_to_default=False)
        font = "Microsoft YaHei"
    except ValueError:
        font = "DejaVu Sans"
    plt.rcParams.update({"font.family": font, "axes.unicode_minus": False, "svg.hashsalt": "regions-v1", "font.size": 9})
    summaries = {(r["target_id"], r["group_id"]): r for r in tables["group_summary"]}
    contrasts = {r["contrast_id"]: r for r in tables["contrast_results"]}
    artifacts = {}

    def group_panel(ax, tid, title, raw_only=False):
        target = config["analysis_targets"][tid]
        order = target.get("display_order", target["groups"])
        rows = [summaries[tid, g] for g in order]
        y = np.arange(len(rows))
        ax.barh(y - .17, [100 * r["home_win_rate"] if r["home_win_rate"] is not None else np.nan for r in rows],
                height=.32, label="直接率", color="#e7a052")
        if not raw_only:
            ax.barh(y + .17, [100 * r["standardized_home_win_rate"] if r["standardized_home_win_rate"] is not None else np.nan for r in rows],
                    height=.32, label="共同构成调整率", color="#357ba2")
        ax.set_yticks(y, [r["group_label"] + f" (n={r['n_matches']:,})" for r in rows])
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_xlabel("主胜率（%）")
        ax.set_title(title)
        ax.legend(loc="lower right", fontsize=8)
        ax.grid(axis="x", alpha=.2)

    def differences(ax, ids, title):
        rows = [contrasts[cid] for cid in ids]
        y = np.arange(len(rows))
        ax.barh(y - .17, [r["direct_difference_pp"] if r["direct_difference_pp"] is not None else np.nan for r in rows],
                height=.32, label="直接差", color="#e7a052")
        ax.barh(y + .17, [r["adjusted_difference_pp"] if r["adjusted_difference_pp"] is not None else np.nan for r in rows],
                height=.32, label="调整差", color="#357ba2")
        ax.set_yticks(y, [r["label"] for r in rows])
        ax.invert_yaxis()
        ax.axvline(0, color="#444444", linewidth=.8)
        ax.set_xlabel("前组减后组（百分点）")
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(axis="x", alpha=.2)

    panels = {
        "overview": [("group", "PROFILE_MACRO", "五大区概况；共同母样本参考24,917场")],
        "europe": [("group", "B_EUR", "欧洲主队：对手地域关系；参考7,993场"),
                   ("group", "C_EUR", "欧洲内部四组；共同参考8,045场"),
                   ("difference", [x["id"] for x in config["comparisons"] if x["target_id"] == "C_EUR"], "欧洲四组完整六对差值（相关）")],
        "asia": [("group", "B_ASIA", "亚洲主队：对手地域关系；参考5,912场"),
                 ("group", "C_ASIA", "西亚与东亚；共同参考5,921场"),
                 ("difference", ["B_ASIA", "C_ASIA"], "亚洲两子项：参考不同，不作统一排名")],
        "africa": [("group", "C_AFR", "北非与撒哈拉以南；参考5,868场"),
                   ("difference", ["C_AFR"], "北非减撒哈拉以南")],
        "americas": [("group", "C_AMER", "南美与美洲其他分区；参考4,555场"),
                     ("difference", ["C_AMER"], "南美减美洲其他分区"),
                     ("raw", "B_SA", "南美地域关系：仅直接描述；全期调整差不可估")],
    }
    for name, items in panels.items():
        fig, axes = plt.subplots(1, len(items), figsize=(6 * len(items), 6), squeeze=False)
        for ax, (kind, key, title) in zip(axes[0], items):
            if kind == "difference":
                differences(ax, key, title)
            else:
                group_panel(ax, key, title, raw_only=kind == "raw")
        fig.suptitle("1980—2024男子国家队非中立比赛｜地域描述", fontsize=13)
        fig.text(.01, .015, "统一年代×赛事比例；未控制实力。无置信区间或显著性检验。南美属于美洲子集。", fontsize=9)
        fig.tight_layout(rect=(0, .05, 1, .94))
        for extension in ("png", "svg"):
            stream = io.BytesIO()
            md = {"Software": "football-regions-v1"} if extension == "png" else {"Date": None, "Creator": "football-regions-v1"}
            fig.savefig(stream, format=extension, dpi=150, metadata=md)
            artifacts[f"outputs/figures/regions/{aid}/{name}.{extension}"] = stream.getvalue()
        plt.close(fig)
    return artifacts


def publish(root, log_dir, artifacts):
    import hashlib
    for relative, content in artifacts.items():
        path = project_path(root, relative)
        require(not path.exists() or sha(path) == hashlib.sha256(content).hexdigest(),
                "REG_OUTPUT_COLLISION", f"Existing output differs; refusing overwrite: {relative}")
    staging = log_dir / "staging"
    for relative, content in artifacts.items():
        temporary = staging / relative
        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(content)
    for relative in artifacts:
        path = project_path(root, relative)
        temporary = staging / relative
        if path.exists():
            temporary.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.replace(path)
    # Remove only known empty staging directories, never recursive file deletion.
    for directory in sorted((p for p in staging.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        directory.rmdir()
    staging.rmdir()
    return {p: sha(project_path(root, p)) for p in artifacts}


def verify_run(root, manifest_path):
    manifest = read_json(project_path(root, manifest_path))
    require(manifest["status"] == "success", "REG_RUN", "Not a successful run")
    count = 0
    for section in ("inputs", "code", "outputs", "run_artifacts"):
        for relative, expected in manifest[section].items():
            require(sha(project_path(root, relative)) == expected, "REG_HASH", f"Changed {section}: {relative}")
            count += 1
    return dict(status="passed", analysis_id=manifest["analysis_id"], fingerprint_checks=count,
                core_outputs=len(manifest["outputs"]), regional_inference="not_run")
