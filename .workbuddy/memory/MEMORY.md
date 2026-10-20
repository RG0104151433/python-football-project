# 工作区长期笔记（足球分析课程项目）

## 项目性质
本工作区 = 北京理工大学《Programming with Python》课程项目（期末课程设计）工作目录。
- 硬性要求：组内 ≤4 人；代码 ≥100 行 + ≥2 个数据/AI 库；报告五节模板（Introduction / Method / Results / Discussion / References）；双渠道提交（python123.io 只传报告+代码；邮件 python_projects@163.com 报告/代码/数据分开打包）；截止 2026-11-13 23:59；第 9–11 周课堂答辩 10 分钟。
- 题目方向：国际男子足球国家队实力演变与主场优势，基于自建 Elo 的时间回测研究。

## 关键路径
- 仓库根目录：`C:\Users\EasonG\Desktop\Repository\python-football-project`
- 旧路径 `Desktop\文件\python项目` 已废弃（整理记录见 `文档/04_整理记录/文件整理记录_2026-10-20.json`），注意 PyCharm 运行配置可能残留旧解释器。
- 方案文档：`文档/01_项目方案/足球分析项目_实施路线与风险.md`、`文档/01_项目方案/下一步执行清单_阶段二至三.md`（阶段划分/排期/清洗规则清单/实测事实以这两份为准）。

## 环境
- Python 3.14.8（64 位）+ 根目录 `.venv`（已验收；check_env.py 8 项全过）。
- 依赖锁定在根目录 `requirements.txt`；`requirements.in` 为直接依赖。
- 方案文档第 3 节仍写 `py -3.12`，属过时内容，以 3.14.8 为准。

## 已完成
- 2026-10-20：Step 0 骨架 —— `.gitignore`、9 个目录（data/raw|processed|external、src、notebooks、tests、outputs/figures|tables|logs）、`config.json`（cutoff_date=2024-12-31 等）。
- 2026-10-20：数据源调研（详见当日日志），确认主源 + openfootball 镜像 + eloratings.net 外部参照。

## 约定与陷阱
- `data/raw/` 冻结快照与 `outputs/figures|tables|logs` **必须提交 Git**（断网复现），只有 `.venv`/缓存/IDE 配置被忽略。
- `neutral` 是字符串 "TRUE"/"FALSE"，绝不能用 `bool('FALSE')`。
- 赛果口径：含加时、不含点球，不得称"90 分钟赛果"。
- Elo 期望得分 ≠ 胜率；三分类必须用完整概率向量评估（Log loss）。
- 主场优势只能表述为描述性关联，控实力后才是预测贡献，不是因果。
