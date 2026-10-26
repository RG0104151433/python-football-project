# 第三问数据准备交接（geo-prep-v1）

生成：2026-10-26；执行者：WorkBuddy agent（AI）；运行目录 `outputs/logs/regions/preparation-20261026T040745Z-52745246/`（下称 RUN）。
本次只做资料整理、关联、计数与校验，**未计算任何地区胜率、调整值、区间或排名**，也未冻结正式统计协议。分类与候选比较均为待主线确认的候选。

## 1. 六项任务与交付

| # | 任务 | 状态 | 交付文件（RUN 内，另有注明） |
|---|---|---|---|
| 1 | 输入关联与双方球队清单 | 完成 | `inputs_used.json`、`linkage_checks.json`、`team_inventory.csv`（215 行） |
| 2 | M49 标准快照与分类字典 | 完成 | `sources/m49_page.html`、`sources/m49_overview.html`（包内，SHA 见 inputs）、`region_dictionary.csv`（包内）、`m49_areas.csv`（RUN，248 行国家/地区原始层级） |
| 3 | 球队地理归属与来源/例外 | 完成（1 处设计性未知） | `team_geography_rules.csv`（217 规则：215 队，俄罗斯 3 段）、`sources.csv`、`exceptions.csv`（包内） |
| 4 | 逐场地域关系与 A/B/C 可用性 | 完成 | `match_region_relations.csv`（24,917 行，1:1） |
| 5 | 计数覆盖与候选比较目录 | 完成 | `counts_home_region_era_tournament.csv`、`counts_home_unit_era_tournament.csv`、`counts_relation_era_tournament.csv`、`counts_direction_matrix.csv`、`unknown_distribution.csv`、`candidate_comparisons.csv`（11 条候选） |
| 6 | 参考支持、校验与交接 | 完成 | `reference_support.csv`、`validation_report.json`（33 项检查，0 失败）、`manifest.json`、本文件 |

工具：`scripts/prepare_region_mapping.py`（新文件，未改任何既有入口）。复算：仓库根目录运行 `python scripts/prepare_region_mapping.py`（或 `.venv\Scripts\python.exe` 同上），重建 RUN 并按 manifest 核对 SHA。输出 CSV 为 UTF-8 BOM + LF、字段稳定排序（M49 代码按字符串保存，保留前导零）。

## 2. 输入版本与复算数量

- data_version `prep-3fab808178cf8ad71d88`；identity `identity-reviewed-29d880765c1623764940`；sample `sample-3bc69e2cc4f843242018`；第二问 `tournaments-4893e38db46f83f6c219`。
- 第二问表 48,102 行，`included=true` **24,917**（`false` 23,185），布尔按字符串 true/false 显式解析；版本三元组全表唯一。
- 按 match_id 与清洗表一对一：重复 0、未匹配 0、日期/赛事/来源记录不一致 0、行数膨胀 0；全部非中立、全部落在 1980-01-01—2024-12-31。
- 球队标签复算：主队 214、客队 214、并集 **215**（与期望一致，实际计算值见 linkage_checks.json）。
- 年代分布 1980s 3,504 / 1990s 4,814 / 2000s 6,872 / 2010s 6,632 / 2020_2024 3,095；赛事 friendly 9,598 / non_friendly 15,319。

## 3. 地理覆盖：球队数与比赛数分开

**球队（215）**：214 支有唯一 M49 国家/地区归属（大区+细区均可定）；`team:russia` 按日期三段——1992-07-03 起为欧洲/东欧，此前为苏联/独联体跨欧亚（**多区未知**）。本样本中**不存在“大区明确、细区不明确”的球队**（M49 最深层总能给出细区），该情形仅由工具小例子校验覆盖。

**比赛（24,917）**：
- 主队大区已定 24,891（欧洲 8,045、亚洲 5,921、非洲 5,868、美洲 4,555、大洋洲 502），未知 26（俄罗斯/苏联段为主队）。
- 目标可用性：A 24,891、B 24,818、C 24,891；A/C 不可用 26 场、B 不可用 99 场（合同一原因：苏联/独联体跨区）。
- 地域关系：同细区 8,395；同大区不同细区 12,055；跨大区 4,368；同大区但关系未知 0；大区未知 99。
- 主队大区→客队大区矩阵见 `counts_direction_matrix.csv`（最大四格：欧→欧 6,367、非→非 5,621、美→美 4,111、亚→亚 4,046；跨区最大为亚→欧 1,086、欧→亚 970）。

## 4. 仍缺/受限的具体信息与影响

| 项目 | 内容 | 影响的比赛/目标 | 是否阻塞 |
|---|---|---|---|
| 苏联/独联体地理 | 跨欧亚实体，按规则不猜单一归属 | 99 场 B、26 场 A/C（主队为苏联段） | 不阻塞：相关场次标未知，其余照常 |
| 大洋洲样本 | 仅 502 场（占 2.0%） | 大洋洲单独作为主队大区的比较支持弱 | 不阻塞：候选目录未纳入大洋洲主队对照 |
| 国家行中文名 | 文档只给层级节点中文名；国家/地区行 `zh_name` 空 | 展示层 | 不阻塞：按需补 |
| 规则日期性质 | 1980/2024 边界是分析窗口（project rule），非实体成立/解散日；俄罗斯三段为项目规则（含 FIFA 接纳日） | 全部 | 已在 date_precision 字段标注 |

## 5. 计数支持（只看支持，不看表现）

- **A**：欧洲/亚洲/非洲/美洲四组场数 4,555—8,045，5 年代 × 2 赛事共 10 层均有比赛；已列 6 组两两候选。大洋洲 502 场未进候选。
- **B**：欧洲内 cross_region 1,626、same_unit 1,764；亚洲内 cross_region 1,866、same_unit 1,819；均给出对应候选。跨区关系在四个大区内的层分布见 `counts_relation_era_tournament.csv`（含 0 格）。
- **C**：欧洲内部候选（北欧 2,504、南欧 2,218、西欧 1,703）；亚洲内部细区场数见 `counts_home_unit_era_tournament.csv`。
- 参考支持：A 候选以母样本 10 层为参考（层全不为空）；B/C 候选以对应主队大区合并赛程为参考，缺层已列在 `reference_support.csv`。**未选权重、未算调整值**；正权重缺层将判不可估。
- 零格与未知分开：区域×年代×赛事有 6 个零格、细区×年代×赛事有 17 个零格（真实无赛程），未知单列为 UNKNOWN 行。

## 6. 实际执行与校验

- 命令：`python scripts/prepare_region_mapping.py`；运行环境为仓库 `.venv`（Python 3.14.8）。
- 校验 33 项全部通过（详见 `validation_report.json`）：输入行数/布尔解析/版本唯一、一对一关联与无膨胀、中性场与日期窗口、214/214/215、M49 解析 248 条、项目细区 22 个且父子不重叠、215 队全覆盖规则且窗口无重叠无空缺、逐场关系行数与去重、四张计数表各自合计回 24,917、方向矩阵合计、6 个工具小例子（边界切换、主客交换方向、大区已知细区未知、跨区缺细区、同细区/异细区、未知大区、零格与未知区分）。
- 未执行：胜平负/胜率、调整、区间、排名、可靠性；未跑 pytest；未改前两问与身份产物；未提交/推送。manifest 记录本 RUN 与包内文件 SHA。

## 7. 需主线决定的问题

1. 是否冻结“大区=M49 Region、细区=最深非空 M49 层（22 个互斥细区）”为 v1 分类，并采用 SSA/北非、拉美两条 rollup 规则？
2. 是否接受科索沃=412（FAQ 统计码，层级同塞尔维亚）、台湾=156（FAQ：M49 视为中国一部分）、英国四足协=826 但保留独立 ID 的处理？
3. 苏联/独联体是否维持“多区未知”（当前），还是改用某一替代口径（需另立规则并重跑）。
4. 11 条候选比较保留哪几条；A 是否纳入大洋洲（当前未纳入）；B 采用“固定主队大区”还是进一步固定到细区。
5. 参考人群：A=母样本 10 层、B=主队大区合并、C=大区合并——是否作为候选保留（数学定权仍待主对话）。

## 8. 共享文件与续做入口

- 本次**未修改**根 README、第三问 README、pipeline_state、论文与汇报支撑材料索引、任何前两问/身份/清洗产物或旧准备报告；只新增 `scripts/prepare_region_mapping.py`、`data/external/geography_preparation/geo-prep-v1/`（sources、seed、字典、来源、例外）与 RUN 目录，并追加研究日志。
- 建议主线在采纳后同步：第三问 README 的“来源与阶段状态”、pipeline 第三问准备状态、材料索引（登记本包与 RUN）。
- 续做入口：RUN 内 `validation_report.json`（失败项为空）、`manifest.json`（SHA 清单）；若改分类或例外，改 `team_geography_seed.csv`/字典后重跑工具即可生成新 RUN，旧 RUN 保留。
