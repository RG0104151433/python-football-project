# 第二问字段字典：tournaments-tables-v1

CSV UTF-8 BOM、LF；浮点十位小数，整数计数，小写布尔，数组JSON。
空数值表示不可算/未运行，不等于零。所有差为友谊赛减其他非友谊赛事。

## analysis_membership.csv

唯一键与排序：match_id

- data_version: string; unit=not applicable; 基础清洗版本。
- identity_version: string; unit=not applicable; 本次成员采用版本。
- sample_id: string; unit=not applicable; 完整分析样本指纹，不是每个子组的样本量。
- match_id: string; unit=not applicable; 原比赛稳定ID。
- source_record_id: string; unit=not applicable; 原始快照逐行定位。
- date: string; unit=not applicable; 比赛ISO日期。
- analysis_era_id: string; unit=not applicable; 研究年代，范围外为空。
- tournament_group: string; unit=not applicable; friendly或non_friendly；追踪表可保留未纳入的未知组。
- included: boolean; unit=not applicable; 是否纳入本次两问共用样本。
- primary_exclusion_reason: string; unit=not applicable; 互斥主排除原因。
- exclusion_reasons: JSON array; unit=not applicable; 完整排除原因JSON数组。

## sample_flow.csv

唯一键与排序：flow_id stage reason

- flow_id: string; unit=not applicable; 计数层标识。
- stage: string; unit=not applicable; 流程阶段。
- parent_stage: string; unit=not applicable; 上级流程。
- reason: string; unit=not applicable; 去向原因。
- n_records: integer; unit=records; 流程该去向记录数。
- basis: string; unit=not applicable; 原始与清洗计数层，禁止跨层重复扣减。
- status: string; unit=not applicable; 数值可用或不可用状态。

## grouped_counts.csv

唯一键与排序：scope period_id tournament_group

- scope: string; unit=not applicable; overall/era/year/rolling中的适用范围。
- period_id: string; unit=not applicable; all、年代ID、年份或窗口ID。
- start_date: string; unit=not applicable; 含首日。
- end_date: string; unit=not applicable; 含末日。
- n_calendar_years: integer; unit=years; 日历年份数，末年代五年，滚动十年。
- tournament_group: string; unit=not applicable; friendly或non_friendly；追踪表可保留未纳入的未知组。
- n_matches: integer; unit=records; 真实支持比赛数，非标准化伪场数。
- n_home_wins: integer; unit=records; 主胜整数场数。
- n_draws: integer; unit=records; 平局整数场数，仍在主胜率分母。
- n_away_wins: integer; unit=records; 客胜整数场数。
- home_win_rate: decimal; unit=probability; 主胜数/场数。
- draw_rate: decimal; unit=probability; 平局数/场数。
- away_win_rate: decimal; unit=probability; 客胜数/场数。
- status: string; unit=not applicable; 数值可用或不可用状态。

## reference_weights.csv

唯一键与排序：reference_id stratum_id

- reference_id: string; unit=not applicable; 共同时间参考ID，raw为空。
- scope: string; unit=not applicable; overall/era/year/rolling中的适用范围。
- period_id: string; unit=not applicable; all、年代ID、年份或窗口ID。
- stratum_kind: string; unit=not applicable; era或year。
- stratum_id: string; unit=not applicable; 权重对应年代或年份。
- n_reference_matches: integer; unit=records; 参考层两类合计场数。
- n_reference_total: integer; unit=records; 参考总体两类合计场数。
- weight: decimal; unit=probability; 该层场数/参考总场数，两类共用。
- status: string; unit=not applicable; 数值可用或不可用状态。

## type_estimates.csv

唯一键与排序：estimate_id

- estimate_id: string; unit=not applicable; 唯一的率目标ID。
- sample_id: string; unit=not applicable; 完整分析样本指纹，不是每个子组的样本量。
- scope: string; unit=not applicable; overall/era/year/rolling中的适用范围。
- period_id: string; unit=not applicable; all、年代ID、年份或窗口ID。
- tournament_group: string; unit=not applicable; friendly或non_friendly；追踪表可保留未纳入的未知组。
- estimand: string; unit=not applicable; raw/era_standardized/year_standardized。
- reference_id: string; unit=not applicable; 共同时间参考ID，raw为空。
- n_matches: integer; unit=records; 真实支持比赛数，非标准化伪场数。
- estimate: decimal; unit=见unit列; 按unit解释的完整精度计算结果。
- unit: string; unit=not applicable; probability为0到1；percentage_points为百分点。
- standard_error: decimal; unit=见unit列; 未计算，空。
- ci_lower: decimal; unit=见unit列; 未计算，空。
- ci_upper: decimal; unit=见unit列; 未计算，空。
- confidence_level: decimal; unit=not applicable; 未计算，空。
- method_id: string; unit=not applicable; 未验收推断，空。
- method_version: string; unit=not applicable; 未验收推断，空。
- uncertainty_status: string; unit=not applicable; 固定not_run。
- status: string; unit=not applicable; 数值可用或不可用状态。

## type_differences.csv

唯一键与排序：contrast_id

- contrast_id: string; unit=not applicable; 唯一类型差ID，方向F减N。
- sample_id: string; unit=not applicable; 完整分析样本指纹，不是每个子组的样本量。
- scope: string; unit=not applicable; overall/era/year/rolling中的适用范围。
- period_id: string; unit=not applicable; all、年代ID、年份或窗口ID。
- estimand: string; unit=not applicable; raw/era_standardized/year_standardized。
- reference_id: string; unit=not applicable; 共同时间参考ID，raw为空。
- n_friendly: integer; unit=records; 该目标范围真实友谊赛场数。
- n_non_friendly: integer; unit=records; 该目标范围真实其他赛事场数。
- estimate: decimal; unit=见unit列; 按unit解释的完整精度计算结果。
- unit: string; unit=not applicable; probability为0到1；percentage_points为百分点。
- standard_error: decimal; unit=见unit列; 未计算，空。
- ci_lower: decimal; unit=见unit列; 未计算，空。
- ci_upper: decimal; unit=见unit列; 未计算，空。
- confidence_level: decimal; unit=not applicable; 未计算，空。
- method_id: string; unit=not applicable; 未验收推断，空。
- method_version: string; unit=not applicable; 未验收推断，空。
- uncertainty_status: string; unit=not applicable; 固定not_run。
- status: string; unit=not applicable; 数值可用或不可用状态。

## rolling_windows.csv

唯一键与排序：window_id

- window_id: string; unit=not applicable; 十个完整公历年窗口ID。
- start_date: string; unit=not applicable; 含首日。
- end_date: string; unit=not applicable; 含末日。
- label_year: integer; unit=years; 窗口末年，非单年水平。
- n_calendar_years: integer; unit=years; 日历年份数，末年代五年，滚动十年。
- n_observed_years: integer; unit=years; 至少一场比赛的年份数。
- n_matches: integer; unit=records; 真实支持比赛数，非标准化伪场数。
- missing_years: JSON array; unit=not applicable; 两类合计无比赛年份的JSON数组。
- status: string; unit=not applicable; 数值可用或不可用状态。

## rolling_counts.csv

唯一键与排序：window_id tournament_group

- window_id: string; unit=not applicable; 十个完整公历年窗口ID。
- tournament_group: string; unit=not applicable; friendly或non_friendly；追踪表可保留未纳入的未知组。
- n_matches: integer; unit=records; 真实支持比赛数，非标准化伪场数。
- n_home_wins: integer; unit=records; 主胜整数场数。
- n_draws: integer; unit=records; 平局整数场数，仍在主胜率分母。
- n_away_wins: integer; unit=records; 客胜整数场数。
- home_win_rate: decimal; unit=probability; 主胜数/场数。
- draw_rate: decimal; unit=probability; 平局数/场数。
- away_win_rate: decimal; unit=probability; 客胜数/场数。
- status: string; unit=not applicable; 数值可用或不可用状态。

## window_membership.csv

唯一键与排序：window_id match_id

- window_id: string; unit=not applicable; 十个完整公历年窗口ID。
- match_id: string; unit=not applicable; 原比赛稳定ID。

## 状态与目标重建

ok/empty_group/missing_stratum/empty_reference/not_estimable；参考另含zero_weight。
正权重缺一类则标准化为空；双方空年权重零，保留日历窗口并跳过不可算均值。
target_definitions.json给出每个目标的范围、公式、符号、权重和分母来源；据此连接清洗比分和窗口成员，可重建逐场系数。
参考标识仅在本analysis_id内解释；sample_id与成员/分析身份同时绑定。无协方差或置信区间文件。
