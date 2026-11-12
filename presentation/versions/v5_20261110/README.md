# 当前采用V5

**中文** | [English](README.en.md)


打开index.html，旁边保留repository_architecture.html。本版基于冻结V4增加第9页悬停放大框，主入口已采用同版V5。

悬停或键盘聚焦52场方块，可查看双方、主客身份、日期及当前预测。辅助三分类突出胜/平/负色段；主二分类放大概率及实力条件90%范围，三场未出值保留为空。记录只有日期，不补造开球时刻。

移出、按Esc或离页隐藏，信息框不拦截控件；赛果录入不改封存预测。

完整仓库运行python presentation/build_v5.py重建；读取冻结V4并附加forecast_hover_v5.js，不覆盖V4。悬停检查见../../v5_verification.json，赛果检查见../../v5_results_handoff_verification.json。

讲稿PRESENTATION_SCRIPT_EN.md有552—556个朗读词，中文操作与英文分开，含操作计划8:25；实际彩排未完成。接入比分看RESULTS_DAY_CHECKLIST.md，尚未录入真实比分。
