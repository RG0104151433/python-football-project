# 第三问准备修订交接（geo-prep-v3，P1–P5 关闭）

生成：2026-10-26。执行者：WorkBuddy agent（AI）。目标：只关闭 v2 审查 P1–P5，不重做六步采集、不重查 FIFA、不扩充资料、不计算地区胜率。

## 一、路径

- 新包：`data/external/geography_preparation/geo-prep-v3/`（v1/v2 保留）
- 主运行：`outputs/logs/regions/preparation-20261026T085703Z-7476ddc3-r1/`（RUN1）
- 同输入重复：`outputs/logs/regions/preparation-20261026T085725Z-7476ddc3-r2/`（RUN2，`repeat_check.json`）
- 快照重放：`outputs/logs/regions/preparation-20261026T085748Z-7476ddc3-replay-r1/`（`replay_check.json`）
- 工具：`scripts/prepare_region_mapping.py`（v3；`prepare`/`replay`/`finalize`/`selftest`）

## 二、P1–P5 关闭证据

| 项 | 关闭方式 | 实际证据 |
|---|---|---|
| P1 输入绑定 | 运行开始把 13 项输入复制到 `run/inputs/`（package 六份 + sources 两页 + q2/clean + 身份三份），逐项登记源路径、快照路径、SHA、字节；**后续计算只读快照** | `inputs/inputs_manifest.json`：13 项 `snapshot_ok=True`；六份包文件 `equals_pkg=True`（与 v3 包字节一致） |
| P2 贡献表 | `team_contributions.csv`：候选×臂×年代×赛事×角色×球队；分母=该臂该层该角色场次；零分母记"无法计算"；逐层校验合计=臂场次 | 29,290 行；`contributions_reconcile_to_arm_cells` 通过；零分母路径由自测 `contributions_reconcile_and_zero_denominator` 验证 |
| P3 布尔 | 只接受字面 `true`/`false`；筛选与校验同规则；`select_included` 断言纳入+排除=总数 | 自测 `strict_boolean_rejects_variants`（"True"/" true"/"true "/"TRUE" 均失败）、`canonical_boolean_no_silent_drop` 通过；实际输入 24,917+23,185=48,102 |
| P4 快照可运行 | `replay` 用原运行 code 快照与 inputs 快照重放，`--root` 显式；新目录不覆盖 | `replay_check.json`：**16/16 核心 CSV 与原运行一致**；重放代码 SHA 记录在案 |
| P5 失败交接 | 缺文件/非法布尔/缺失关联/规则冲突/检查失败 → `failure_report.json` + 退出码 2，不写 manifest | 自测 `failure_report_end_to_end`：真实子进程用非法输入运行，rc=2、failure_report 存在、manifest 不存在 |

## 三、实际命令与结果

```
python scripts/prepare_region_mapping.py prepare --tag r1
python scripts/prepare_region_mapping.py prepare --tag r2
python scripts/prepare_region_mapping.py replay --run outputs/logs/regions/preparation-20261026T085703Z-7476ddc3-r1
python scripts/prepare_region_mapping.py finalize <run>
```
- RUN1/RUN2：status ok；A 24,891 / B 24,818 / C 24,891；关系 same_unit 8,395、same_region_diff_unit 12,055、cross_region 4,368、unknown 99；自测 14/14；贡献表 29,290 行。
- 两跑核心 CSV 16/16 一致（`repeat_check.json`）；快照重放 16/16 一致（`replay_check.json`）。
- 检查项数见各 `validation_report.json`（含 14 项自测与 3 个覆盖探针）；失败项 0。
- 文件构成：每个运行登记 34 个文件 = 19 个根文件（r1 含 handoff.md；r2 为 repeat_check.json、重放为 replay_check.json）+ 1 个代码快照 + 14 个输入文件（13 份输入快照 + inputs_manifest.json）。上段"20 输出"表述有误，以此为准。
- manifest 由 finalize 在 handoff/repeat/replay 文件齐全后重算，覆盖运行根、`code/`、`inputs/` 全部文件。

## 四、仍存在的限制（未变）

1. 俄罗斯 1980-01-01—1992-07-02 多区未知：99 场 B、26 场 A/C 不可用；分段界为项目约定，非 FIFA 逐日官方记录。
2. 大洋洲 502 场仅作分布展示候选；国家行中文名未补。
3. 分类 v1、承载办法、19 条候选与参考口径仍待主线裁决；本批未改变分类/候选内容。
4. 未运行 pytest（本工具非 pytest 套件成员）；未改前两问、原比赛、会员裁定与共享方案。

## 五、共享文件与日志

- 未修改根 README、阶段 README、材料索引、pipeline_state；未提交/推送。
- 研究日志新增 **R20261026-13**（记录 P1–P5 与验证；不改旧条目）。
