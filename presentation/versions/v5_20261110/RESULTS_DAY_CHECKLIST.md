# V5比赛结果快速接入与讲稿更新

本接口已在V5实测：导入、分类计数、排除未决/未出预测、导出备份、刷新后保留，以及原预测不被改写。测试只用临时虚拟比分，不是真实研究结果。

## 展示当天的四步

1. 复制V5同目录的results_template.csv，另存为results_checked_20261117.csv。保留fixture_id，逐场核对实际主客队及最终90分钟含补时比分。未结束/未查证保持pending；延期/取消按对应状态填写。不要填加时或点球数。
2. 已核验行设置status=final，填写非负整数home_score、away_score、真实source_url和checked_at（建议ISO时间并带时区）。不要为了凑52场提前填结果；11月17日上午未必所有比赛已结束。
3. 打开V5第10页Import results CSV导入，先选Main binary，核对Correct/Wrong/Pending/Withheld/Evaluated和Accuracy。再切Auxiliary three-way单独核对。导入是整份替换，不是隐式追加。可以点比赛方块看比分和来源，不会跳到已删除的案例页。
4. 点Export imported CSV备份，并在presentation/PRESENTATION_SCRIPT_EN.md第10页段落填入现场显示的N/C/W/A/P。这些空位只是讲稿，不驱动图表；图表始终由CSV计算。换教室机器后重新导入，不能依赖原电脑的浏览器存储。

## 规则不要混淆

- 主模型：p≥0.5选主胜，否则选平/客胜。三场主预测withheld不进入主模型判对错分母。
- 辅助三分类：选概率最大的主胜/平/客胜；与主模型单独计算。
- 待核验场次不计准确率分母；比分导入不会重训或改写封存概率。
- 日期不是具体开球时刻。不要用计划日期代替已确认完赛状态。
- 论文目前封存的未验收描述不因展示录入自动变成已验收结论；若需要修改论文，应另行更新相关段落与结果版本。

## 当前状态

尚未提供真实比分，全52行模板仍是pending。v5_results_handoff_verification.json记录临时测试范围，没有把虚拟比分写进模板。
