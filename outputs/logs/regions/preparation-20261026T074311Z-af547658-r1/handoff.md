# 第三问准备修订交接（geo-prep-v2）

生成：2026-10-26。执行者：WorkBuddy agent（AI）。主运行：`outputs/logs/regions/preparation-20261026T074311Z-af547658-r1/`（下称 RUN1）；重复运行：`outputs/logs/regions/preparation-20261026T074344Z-af547658-r2/`（RUN2）。
本批为 v1 审查（`review-20261026-geo-prep-v1`）后的定点修订：只补交接缺口，未计算任何地区胜率/标准化/区间/显著性，未改原始比赛、会员裁定、前两问输入与结果。

## 一、路径

- 新准备包：`data/external/geography_preparation/geo-prep-v2/`（v1 原样保留）
- 主运行：`outputs/logs/regions/preparation-20261026T074311Z-af547658-r1/`
- 重复运行（同输入）：`outputs/logs/regions/preparation-20261026T074344Z-af547658-r2/`，内含 `repeat_check.json`
- 工具：`scripts/prepare_region_mapping.py`（v2，含 `prepare`/`finalize` 子命令；包与运行目录均可参数化）

## 二、审查各项的完成情况

| 审查发现 | 处理 | 证据文件（RUN1 内） |
|---|---|---|
| 1. reference_support 只查合并参考 | 新增逐候选×臂×层支持表（参考是否要求该层、组内场次、支持状态、缺失原因）；并在 summary 中给 10 层双组支持数 | `candidate_reference_support.csv`、`candidate_support_summary.csv` |
| 2. B/C 用"其余关系"、不可机器读取 | 候选规格改为数据文件：两组定义均为显式过滤条件（region/relation/unit）；不再有"其余"；纯分布项标 `distribution_display_candidate` | 包内 `candidate_specs.csv`（19 条） |
| 3. 历史承载与俄罗斯切点只指 M49 | 新增承载模型（实体事实/现代承载/项目约定分列）；俄罗斯三段并注明"FIFA 2018 年份级 + UPI 线索，非逐日官方记录"；身份包例外区间并列 | 包内 `carrier_model.csv`、`exceptions.csv`（10 条）、RUN1 `exception_impacts.csv` |
| 4. 24 个原始节点父级为空 | 用已保存 M49 补齐 `raw_parent_code`（subregion→region，intermediate→subregion），并单列项目层级 `project_level/project_parent_code` | 包内 `region_dictionary.csv`（55 行，缺父级 0） |
| 5. 覆盖表只算主队 | 新增主客构成表：主/客各自场次、独立球队数、层内占比（分母=该层总场次）、组内 top1 及占比（分母=组内场次，为 0 记"无法计算"）、层内未知数；候选臂另有客队构成 | `composition_home_away.csv`、`candidate_arm_composition.csv` |
| 6. 六格零场误写为缺赛程 | 零格分类表：known_category_zero 44、unknown_category_zero 118；大区表 6 个零格全部为 UNKNOWN 行，五个已知大区 10 层均有比赛 | `zero_cell_analysis.csv`；更正说明见包 README 与日志 R20261026-09 |
| 7. 方向测试只是字面比较 | 11 项自测全部经过真实处理函数：交换主客经 `process_relations`、重复ID/非法布尔/版本不一致经 `load_q2_rows`、中间断档与重叠经 `check_rule_series`、多规则命中经 `rule_for`、父级不一致经 `check_rule_parents`、单边已知与未知/零区分、参考缺层经 `support_rows`；非法输入 fail-fast（退出码 2，不生成成功 manifest） | `validation_report.json`（37 项检查 0 失败；自测 11/11） |
| 8. 脚本固定写入 v1 | 包/输出可参数化；每次运行复制代码快照并登记 SHA；两跑核心 CSV 一致 | `inputs_used.json`、`code/prepare_region_mapping.py`、RUN2 `repeat_check.json`（15/15 一致） |

审查点名的三个缺格已作为真实覆盖探针经同一支持判定函数：非洲 cross_region 1980s 非友谊赛（组 0/参考 506）、大洋洲 same_unit 1980s 友谊赛（0/38）、大洋洲 same_region_diff_unit 2000s 友谊赛（0/32），三者均判 `group_missing_layer`（`coverage_probe_cases.csv`），仅证明检查有效，不外推为欧洲/亚洲候选不可用。

## 三、实际运行与校验

- 命令：
  - `python scripts/prepare_region_mapping.py prepare --tag r1`
  - `python scripts/prepare_region_mapping.py prepare --tag r2`
  - 两跑后 `finalize` 重登记 manifest
- 核心数量（复算，非抄写）：24,917 场、双方并集 215 队（主 214/客 214）；A 24,891、B 24,818、C 24,891；关系 same_unit 8,395 / same_region_diff_unit 12,055 / cross_region 4,368 / unknown 99。
- 候选支持：17 个比较候选全部 `supported_all_layers`（10/10 层双组非空且参考层存在）；2 个分布展示候选（大洋洲细区构成、非洲关系构成）。
- 指纹：`inputs_used.json` 记 4 输入 + M49 两页 + 脚本（含运行内代码快照 SHA）；`manifest.json` 由 finalize 在全部报告后生成，覆盖 RUN1 全部文件与 `code/`；RUN2 `repeat_check.json` 记录 15/15 CSV 一致。
- 失败项：0。未运行项：胜率/调整/区间/排名、第四/五问检验、pytest（本工具不属 pytest 套件）。

## 四、尚未解决与影响

1. **俄罗斯 1980-01-01—1992-07-02**：99 场关系未知、26 场主队大区未知（A/C 不可用）。分段界为项目约定，非 FIFA 逐日官方记录；身份包对同一队保留 1980—1992 整年待核区间（用途不同：会员 vs 地理）。不阻塞其余分析。
2. **大洋洲**：502 场，细区 249/180/13/60；只作分布展示候选，是否升格为比较由主线决定（本包不因其场次少而判"不可分析"）。
3. **国家行中文名**：`region_dictionary.csv` 仅层级节点有中文名；国家/地区级中文展示名未补（不影响分类与计数）。
4. **P3/P4 会员政策**（batch06）与地理分类相互独立：地理层不重开会员资格问题。

以上均不阻塞数学方案讨论；候选目录与参考口径仍待主线裁决。

## 五、共享文件与研究日志

- 未修改根 README、第三问 README、材料索引、pipeline_state；建议由主线在验收后同步（本包与 RUN1/RUN2 路径、19 候选、支持状态）。
- 新增研究日志条目：**R20261026-09**（含 v1 日志"7 条例外"的更正说明，不改写 R20261026-07）。
- 未提交、未推送；v1 包与原运行目录经指纹复核未变（仅 `scripts/prepare_region_mapping.py` 更新为 v2，v1 字节存于包内 `code_snapshots/`）。
