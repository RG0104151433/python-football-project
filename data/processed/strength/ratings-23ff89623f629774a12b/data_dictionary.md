# 赛前实力特征（全局参考模型）

每行一场，UTF8 BOM/LF/浮点10位。所有值由此前日期赛果生成；outcome_index不进入特征表。home/away是历史评分实体，不等于地理载体。中立场venue=0，第一方不视为实际主场。home_term是共享场地状态，实际预期应用venue*home_term。双方方差及协方差给出difference_variance；它们条件于选定模型/超参数，不包含全部选择和模型误差。cold_start表示任一方此前少于5场，仅为诊断，不证明5场后可靠；previously_disconnected只检查此前累计对阵图。预测概率已积分评分未知并含场地与背景；不是后续联合研究的结果。rating_run_id/规则/输入版本均固定。检查点采用延迟日历传播表示，查询某日应按state.last[t]补q*间隔，未出场占位先验不能展示为球队历史实力。
