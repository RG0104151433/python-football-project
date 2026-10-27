# 第三问字段字典：regions-tables-v1

CSV为UTF-8 BOM、LF、固定键排序。数字不预先舍入，浮点按.17g；空数值不等于0。
analysis_id连接同目录元数据中的版本；run_id和时间仅在运行清单。代码字段按字符串保留前导零。
九目标、十二差值、十一调整差可算；无标准误、置信区间、p值或可靠性结论。

## analysis_matches.csv

主键/稳定排序：match_id

- analysis_id：稳定分析身份，连接analysis_metadata.json；不是每次运行编号。
- match_id：原比赛稳定ID。
- source_record_id：原始快照记录定位。
- date：比赛ISO日期。
- year：公历年。
- era：五年代标签，末组仅2020—2024。
- tournament_group：friendly/non_friendly。
- home_team_id：原主队/客队身份ID。
- away_team_id：原主队/客队身份ID。
- home_team：原清洗表的球队显示名或比赛地点信息，不重判主场。
- away_team：原清洗表的球队显示名或比赛地点信息，不重判主场。
- home_score：非负整数进球，不含点球大战。
- away_score：非负整数进球，不含点球大战。
- home_win：主胜指示1/0，平局为0。
- outcome：home/draw/away。
- result_basis：加时后且不含点球大战。
- is_neutral：本样本固定false。
- city：原清洗表的球队显示名或比赛地点信息，不重判主场。
- country：原清洗表的球队显示名或比赛地点信息，不重判主场。
- home_region：三位地理字符串代码；空表示未知，不是代码0。
- home_unit：三位地理字符串代码；空表示未知，不是代码0。
- home_rule_id：采用版日期规则ID。
- away_region：三位地理字符串代码；空表示未知，不是代码0。
- away_unit：三位地理字符串代码；空表示未知，不是代码0。
- away_rule_id：采用版日期规则ID。
- direction：主队大区>客队大区。
- relation：same_unit/same_region_diff_unit/cross_region/unknown。
- A_usable：true/false，准备阶段的目标资格。
- A_reason：准备阶段资格原因。
- B_usable：true/false，准备阶段的目标资格。
- B_reason：准备阶段资格原因。
- C_usable：true/false，准备阶段的目标资格。
- C_reason：准备阶段资格原因。

## analysis_membership.csv

主键/稳定排序：target_id match_id

- analysis_id：稳定分析身份，连接analysis_metadata.json；不是每次运行编号。
- target_id：九个成员目标之一。
- match_id：原比赛稳定ID。
- group_id：目标内互斥组，未纳入时空。
- included：在该目标某展示/对比组内。
- in_reference：进入该目标参考人群。
- reason：纳入/排除或不可估具体原因。

## group_summary.csv

主键/稳定排序：target_id group_id

- analysis_id：稳定分析身份，连接analysis_metadata.json；不是每次运行编号。
- target_id：九个成员目标之一。
- group_id：目标内互斥组，未纳入时空。
- group_label：配置中的组名。
- n_matches：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- n_home_wins：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- n_draws：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- n_away_wins：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- home_win_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- draw_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- away_win_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- status：ok/no_matches/zero_weight/unsupported_positive_reference_layer，按表适用。
- n_home_teams：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- n_away_teams：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- reference_group：同目标共同参考，不随每对比较变化。
- standardized_home_win_rate：按本目标共同参考得到的调整主胜率。
- standardization_status：ok或正权重层缺比赛。
- standardization_reason：缺失层清单。

## stratum_counts.csv

主键/稳定排序：target_id group_id era tournament_group

- analysis_id：稳定分析身份，连接analysis_metadata.json；不是每次运行编号。
- target_id：九个成员目标之一。
- group_id：目标内互斥组，未纳入时空。
- era：五年代标签，末组仅2020—2024。
- tournament_group：friendly/non_friendly。
- n_matches：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- n_home_wins：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- n_draws：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- n_away_wins：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- home_win_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- draw_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- away_win_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- status：ok/no_matches/zero_weight/unsupported_positive_reference_layer，按表适用。
- group_share：组内该层场数/组总数。

## reference_weights.csv

主键/稳定排序：target_id era tournament_group

- analysis_id：稳定分析身份，连接analysis_metadata.json；不是每次运行编号。
- target_id：九个成员目标之一。
- reference_group：同目标共同参考，不随每对比较变化。
- era：五年代标签，末组仅2020—2024。
- tournament_group：friendly/non_friendly。
- n_reference_matches：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- n_reference_total：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- weight：标准化为参考层场数/参考总数；直接系数固定1。
- status：ok/no_matches/zero_weight/unsupported_positive_reference_layer，按表适用。

## contrast_results.csv

主键/稳定排序：contrast_id

- analysis_id：稳定分析身份，连接analysis_metadata.json；不是每次运行编号。
- contrast_id：预定成对差值ID，多对可属同一目标。
- target_id：九个成员目标之一。
- study_id：四项研究标题之一。
- label：预定差值显示名。
- arm1：差值前组。
- arm2：差值后组。
- reference_group：同目标共同参考，不随每对比较变化。
- n_arm1：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- n_arm2：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- direct_arm1_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- direct_arm2_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- adjusted_arm1_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- adjusted_arm2_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- direct_difference：前后组直接主胜率之差。
- direct_difference_pp：直接率差乘100。
- adjusted_difference：共同构成后前组率减后组率。
- adjusted_difference_pp：调整率差乘100。
- direct_minus_adjusted_pp：直接差减调整差，单位百分点，不是因果贡献。
- direct_status：ok/no_matches/zero_weight/unsupported_positive_reference_layer，按表适用。
- adjusted_status：ok/no_matches/zero_weight/unsupported_positive_reference_layer，按表适用。
- reason：纳入/排除或不可估具体原因。

## layer_contributions.csv

主键/稳定排序：contrast_id era tournament_group

- analysis_id：稳定分析身份，连接analysis_metadata.json；不是每次运行编号。
- contrast_id：预定成对差值ID，多对可属同一目标。
- target_id：九个成员目标之一。
- era：五年代标签，末组仅2020—2024。
- tournament_group：friendly/non_friendly。
- n_arm1：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- wins_arm1：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- n_arm2：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- wins_arm2：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- arm1_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- arm2_rate：0—1概率；无比赛或不支持时空，须结合状态列解释。
- weight：标准化为参考层场数/参考总数；直接系数固定1。
- layer_difference：该层前组主胜率减后组。
- contribution：共同权重乘层差，零权重层为0。
- status：ok/no_matches/zero_weight/unsupported_positive_reference_layer，按表适用。

## team_contributions.csv

主键/稳定排序：target_id group_id era tournament_group role team_id

- analysis_id：稳定分析身份，连接analysis_metadata.json；不是每次运行编号。
- target_id：九个成员目标之一。
- group_id：目标内互斥组，未纳入时空。
- era：五年代标签，末组仅2020—2024。
- tournament_group：friendly/non_friendly。
- role：home/away，两个角色分别对账。
- team_id：原球队身份，不合并历史实体。
- team_label：中文展示名。
- n_matches：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- denominator：占比或系数计算的整数分母。
- share：该记录场数/对应整数分母。

## opponent_composition.csv

主键/稳定排序：target_id group_id era tournament_group away_region away_unit

- analysis_id：稳定分析身份，连接analysis_metadata.json；不是每次运行编号。
- target_id：九个成员目标之一。
- group_id：目标内互斥组，未纳入时空。
- era：五年代标签，末组仅2020—2024。
- tournament_group：friendly/non_friendly。
- away_region：三位地理字符串代码；空表示未知，不是代码0。
- away_unit：三位地理字符串代码；空表示未知，不是代码0。
- n_matches：非负整数计数；matches/wins为场，teams为球队数，reference_total为参考场数。
- denominator：占比或系数计算的整数分母。
- share：该记录场数/对应整数分母。

## match_coefficients.csv

主键/稳定排序：contrast_id method match_id

- analysis_id：稳定分析身份，连接analysis_metadata.json；不是每次运行编号。
- contrast_id：预定成对差值ID，多对可属同一目标。
- target_id：九个成员目标之一。
- method：direct/standardized。
- match_id：原比赛稳定ID。
- group_id：目标内互斥组，未纳入时空。
- era：五年代标签，末组仅2020—2024。
- tournament_group：friendly/non_friendly。
- denominator：占比或系数计算的整数分母。
- weight：标准化为参考层场数/参考总数；直接系数固定1。
- coefficient：固定设计差值线性和的有符号逐场系数，未估协方差。

## 状态、缺失与系数

零场的计数为0，率为空；正权重缺层不改变目标/参考。零权重层跳过加权运算。
系数表仅存非零项；零项由完整事实表和成员/差值配置重建。不支持的调整差不导出假系数。
欧洲成员不按六个差值重复分组；六个差值不独立。共同参考或赛程若视为随机，第四问另处理其变动。
