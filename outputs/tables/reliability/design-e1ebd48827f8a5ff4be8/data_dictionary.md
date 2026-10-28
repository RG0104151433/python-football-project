# Q4第二步数据字典

本目录只包含目标重建和设计诊断，没有统计推断结果。CSV为UTF-8 BOM、LF，浮点显式17位有效数字。

- target_catalogue：完整292个目标，来源表/行/列/单位、家族、可计算状态及缺层；概率为内部尺度，展示乘100。supported_point_target不表示方法已验收。
- coefficient_recipes：按组件重建逐场系数；Q1/Q2按era/year/type与scope/period筛选，Q3按region_target/group成员再筛层。组件multiplier*q_numerator/q_denominator/n逐次相加；正参考空层使整个目标不可估，不得跳过。
- target_support：按非零合并系数记录球队/年份/对子、正参考组件最小场数及1/2场组件；l1/l2、最大单场系数和集中度仅为设计诊断。
- team_exposure：双方角色出场数、有符号/绝对系数和。incident_absolute_mass_share每队取两个角色占总逐场绝对系数质量的比例；所有球队该比例加总为2，不是概率分布。
- year_exposure：逐目标年份出场及系数质量；不能由此证明时间关联只持续一年。
- target_overlap：可计算目标两两共享比赛/任一角色球队/年份；零共享比赛也可能相关。不是协方差矩阵。
- dyad_schedule：忽略主客方向的球队对子重复次数，仅供依赖诊断；估计主胜时方向仍保留。
- calendar_counts：年/月×赛事类型场数；没有精确赛事届次/轮次，不冒称赛事独立群已知。
- competition_context：原快照按source_record_id核对日期/比分/场地后取回赛事原名，届次/轮次明确为空。赛事名×年份不能直接充当真实届次或独立聚类。它是依赖背景资料，不改变本步既有目标条件和系数。
- summary：全局赛程/依赖机会和各家族规范化系数行数值秩（阈值1e-10）。不代表独立样本量或未知协方差的秩。
- checks：真实版本/成员/系数与原结果对应核对；不是模型覆盖率检验。
