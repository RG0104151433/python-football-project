# geo-prep-v2：第三问地域准备包（修订版）

创建：2026-10-26。承接 [geo-prep-v1](../geo-prep-v1/) 与独立审查 `outputs/logs/regions/review-20261026-geo-prep-v1/review.json`（结论 needs_targeted_revision）。
v1 包与运行目录原样保留；本包是修订版，脚本可显式选择包与输出目录。

## 内容

| 文件 | 说明 |
|---|---|
| `sources/m49_page.html`、`sources/m49_overview.html` | UNSD M49 官方快照（与 v1 相同 SHA，2026-10-26 访问） |
| `team_geography_seed.csv` | 215 队 → M49 代码（与 v1 相同） |
| `region_dictionary.csv` | 原始层级（region/subregion/intermediate）+ 项目层级（大区/22 细区/rollup）。**本次补齐 24 个原始节点的 `raw_parent_code`**，并新增 `project_level`、`project_parent_code` 列，原始与项目两套层级分列 |
| `carrier_model.csv` | 逐队承载模型：`carrier_kind`（modern_state / dependent_territory / constituent_association_of_UK / historical_association_carrier / statistical_area_412 / statistical_area_inside_156 / historical_union_plus_state）、`entity_fact_source`、`project_convention`、`assumption` |
| `sources.csv` | 6 条来源：M49 页/overview/FAQ + 身份包的 registry、historical_exceptions、adopted_decisions；逐条写"实际支持什么"与本地 SHA |
| `exceptions.csv` | **10 条**例外（英国四足协、科索沃、台湾、东德、捷克斯洛伐克、南斯拉夫、俄罗斯）：实体事实、证据路径、承载办法、项目约定、假设、影响场次 |
| `candidate_specs.csv` | 19 条候选：A×6、B×4、C×7（两组定义互斥且机器可读）、D×2（**分布展示候选**，不定义差值） |
| `code_snapshots/prepare_region_mapping_v1.py` | v1 脚本原件快照（SHA=52745246…，与独立审查记录的脚本指纹一致） |

## 相对 v1 的更正（不改写 v1 与其日志）

1. **例外条数**：v1 结构化文件实为 10 条，R20261026-07 日志写"7 条"有误；本包 README 与 R20261026-09 以更正条目记录，不修改旧日志。
2. **零格解释**：v1 交接称"大区 6 个空格来自缺少赛程"有误——6 个零格全部位于 UNKNOWN 类别（已知五个大区的 10 层均有比赛）。本包 `zero_cell_analysis.csv` 把 known_category_zero 与 unknown_category_zero 分开（本批 known 44、unknown 118）。
3. **参考支持范围**：v1 只查合并参考；本包 `candidate_reference_support.csv` 逐候选×臂×层判定，并给出参考是否要求该层、组内是否缺层。
4. **候选写法**：B/C 不再用"其余关系"，改为两组关系/细区显式定义；大洋洲与非洲的关系构成列为分布展示候选并写明理由。
5. **历史承载**：M49 现代代码只作承载对象；`carrier_model.csv` 区分实体事实、项目约定与假设，俄罗斯分段明确标注"非 FIFA 逐日官方记录"。

## 复算

仓库根目录：
```
python scripts/prepare_region_mapping.py prepare --package data/external/geography_preparation/geo-prep-v2 --tag r1
python scripts/prepare_region_mapping.py prepare --package data/external/geography_preparation/geo-prep-v2 --tag r2
python scripts/prepare_region_mapping.py finalize outputs/logs/regions/<run_dir>
```
脚本在 `prepare` 时把自身字节复制到运行目录 `code/` 并登记 SHA；`finalize` 在全部报告生成后重算 manifest 指纹。

## 待主线确认（未在本包冻结）

分区 v1（M49 Region + 最深非空层 22 细区）、SSA/北非/拉美三条 rollup 规则、科索沃 412 / 台湾 156 / 英国 826 的承载办法、俄罗斯三段方案、19 条候选中保留哪些、参考人群口径（A=母样本 / B=主队大区 / C=大区合并）。
