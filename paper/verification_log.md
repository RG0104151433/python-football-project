# 论文/代码验证日志

本文件记录 `quick_check.py`、`pytest`、编译和提交前检查的**实际输出**；不要填写未运行的检查，也不要把计划写成通过。

## 2026-11-05 基线（Codex AI）

- 环境：Windows 64 位；Python 3.14.8；项目 `.venv`。
- 命令：`.\.venv\Scripts\python.exe quick_check.py`
- 结果：**7/7 passed**（raw snapshot、cleaned dataset、study population、Q5 aggregates、Q6 baseline、Q7 overall、Q8 forecasts）。
- 命令：`.\.venv\Scripts\python.exe quick_check.py --full`
- 结果：**8/8 passed**；`pytest` 402 passed in 69.19s。
- 命令：`.\.venv\Scripts\python.exe paper\check_citations.py`
- 结果：BibTeX entries 0；TeX files scanned 5；distinct cited keys 0；一致性 OK（此时尚未录入文献）。
- 命令：`latexmk -xelatex -interaction=nonstopmode -outdir=build main.tex`（`paper/`）
- 结果：编译通过，`build/main.pdf` 1 页骨架；空参考文献；无 `csquotes` 警告。
- 说明：以上是当前机器、当前工作区的检查；不是干净克隆、第二台机器、外部文献或提交平台验收。

## Agent 运行记录模板

```text
### YYYY-MM-DD｜执行者/工具
- commit / dirty state：
- 命令：
- 实际输出（粘贴关键行）：
- 通过/失败：
- 失败定位与修复：
- 未验证：
- 下一步：
```
