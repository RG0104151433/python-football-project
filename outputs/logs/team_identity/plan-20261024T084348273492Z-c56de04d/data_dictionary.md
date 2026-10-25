# 预演字段

CSV：UTF-8 BOM、LF、稳定排序；布尔true/false，evidence_ids为JSON数组。

match_impacts.csv一行为决定×比赛×一方；去重场数须按match_id统计，不能直接相加各决定。

proposed_annotation只存解释建议，不是替换球队主键；in_study使用原分析资格。proposed_exclusion仅表示情景建议；facts_changed恒false，不交换主客、不改比分或中立标记。

requires_entity_review表示历史实体解释仍需审查；requires_new_population表示若批准须新人群版本并重算两题。unresolved覆盖全部来源标签，以in_study区分本次关卡与范围外事项。
