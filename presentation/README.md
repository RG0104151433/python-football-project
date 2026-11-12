# 课堂展示：当前V5

**中文** | [English](README.en.md)


当前使用14页V5。论文及材料已由组长确认在两个渠道提交；现在集中准备课堂讲解。真实比分尚未录入，三人实际计时彩排尚未完成。

## 直接用这几份

- [打开展示](index.html)：Chrome或Edge离线打开；同目录保留[结构图](repository_architecture.html)。
- [英文讲稿](PRESENTATION_SCRIPT_EN.md)：本次再压缩为约550词；英文引用块朗读，中文【操作】不读。含操作的计划8:25，留1:35机动，实际时长需合练。
- [赛果接入](RESULTS_DAY_CHECKLIST.md)与[CSV模板](results_template.csv)：展示前准备，不在台上录入；不修改封存预测。
- 本机整套取用：`交付材料/03_课堂展示/`，包含同版HTML、结构图、模板、讲稿与彩排安排。

## 操作与修改

底部Next/Back或左右方向键换页；子图使用页内按钮。正式投影关闭讲者备注；备注也会被投影。地图只切欧洲、实力只选巴西和中国、一场预测展示两种视图即可。

从完整仓库执行`python presentation/build.py`重建采用V5；构建源读取冻结V4并附加V5扩展。只修改讲稿不必重建HTML。`versions/v4_20261110/`继续冻结，`versions/v5_20261110/`保存采用版副本。

当前版本及指纹：[current_version.json](current_version.json)。现有浏览器检查：[V5悬停](v5_verification.json)、[赛果接口](v5_results_handoff_verification.json)。这些是先前运行记录，本轮只改讲稿和入口，未重新执行浏览器检查。

图片与数据来源：[VISUAL_SOURCES.md](VISUAL_SOURCES.md)。当前仓库图是原生SVG；旧Archify成品仅为历史来源。[旧10页讲义](archive/initial_10_screen/handout.pdf)已归档，不能当当前14页备用稿。

旧展示、Archify凭证及配图检索记录已集中到[展示存档](archive/README.md)。新旧路径见[执行记录](../文档/04_整理记录/仓库优化执行记录_20261111.json)。构建和验证脚本保留原路径，数据与正式展示内容不变。

## 历史说明

[完整旧README、推导和版本记录](../文档/04_整理记录/README历史快照_20261112/presentation/历史说明.md)按当时日期阅读，不代替当前状态。
