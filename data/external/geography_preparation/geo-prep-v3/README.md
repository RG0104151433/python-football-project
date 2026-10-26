# geo-prep-v3：第三问地域准备包（P1–P5 修订）

**2026-10-26存储迁移（R20261026-16）：** 本包两份M49网页已统一移到[共享目录](../../geography_sources/m49-20261026/)，不再在sources/重复保存；旧CSV/清单及来源SHA保持原样，由relocations.json解析旧路径。当前程序/重放入口支持该布局，下面为R13交付时说明。分类和候选数据未改变，正式研究清单另以config/regions_study.json的v2为准。

创建：2026-10-26。承接 [geo-prep-v2](../geo-prep-v2/) 与独立审查 `outputs/logs/regions/review-20261026-geo-prep-v2/review.json`（结论 arithmetic_reusable_targeted_handoff_and_input_hardening_required）。v1/v2 包与运行目录原样保留。

## 相对 v2 的变更

| 审查项 | 变更 | 位置 |
|---|---|---|
| P1 关键输入未绑定 | 六份关键输入（seed、carrier、dictionary、specs、exceptions、sources）+ M49 两页 + 比赛/身份输入共 13 项，运行开始时复制进 `run/inputs/` 并登记 SHA；**计算只读快照**，运行可证明使用这些具体字节 | 运行内 `inputs/inputs_manifest.json`、`inputs/package/`、`inputs/external/` |
| P2 贡献表不完整 | 新增 `team_contributions.csv`：候选×臂×年代×赛事×角色(home/away)×球队，含场次、分母、占比；零分母记"无法计算"；逐层核对合计回臂场次 | 运行内 `team_contributions.csv` |
| P3 布尔不一致 | 严格只接受字面 `true`/`false`（无 strip、无大小写兼容）；`select_included` 与校验使用同一规则，并核对纳入+排除=总数 | 脚本 `load_q2_rows`/`select_included`；“True”即失败 |
| P4 快照不可直接运行 | `replay --run <run>`：用原运行的**代码快照 + 输入快照**重放，写入新目录并比对核心 CSV；`--root` 显式 | 脚本 `replay` 子命令；运行内 `replay_check.json` |
| P5 失败交接 | 输入/缺失关联/规则冲突/检查失败 → `failure_report.json`（stage、error_type、detail、已执行检查、traceback 尾部）+ 退出码 2；不写 manifest；`run/code` 快照仍在 | 运行内失败目录；自测 `failure_report_end_to_end` |

## 内容

- `sources/m49_page.html`、`sources/m49_overview.html`：与 v2 相同 SHA 的 M49 快照。
- 六份关键输入：与 v2 内容一致（SHA 相同），作为 v3 包基线。
- `code_snapshots/prepare_region_mapping_v2.py`：v2 脚本原件（SHA=af547658…，与 v2 审查记录一致）。
- 说明：v3 的分类字典、承载模型、例外、候选规格**未改变内容**；本批只修交接与输入绑定，不重开资料。

## 复算

仓库根目录：
```
python scripts/prepare_region_mapping.py prepare --tag r1
python scripts/prepare_region_mapping.py prepare --tag r2
python scripts/prepare_region_mapping.py replay --run outputs/logs/regions/<r1>
python scripts/prepare_region_mapping.py finalize outputs/logs/regions/<run>
```
`prepare` 会把当前脚本与 13 项输入复制进运行目录；`replay` 不使用 `scripts/` 下当前文件，而使用原运行的 `code/prepare_region_mapping.py`。
