# International football: from historical home wins to pre-match prediction

[中文](README.md) | **English**

Browse [all README language editions](文档/05_团队协作/文档语言导航.md). The [documentation review, Chinese](文档/04_整理记录/文档核对与双语说明_20261112.md) explains corrections, preserved originals and scope.


We use public national-team results to study differences across periods, match types and regions, then estimate pre-match strength and test whether context adds predictive information.

The agreed research is complete. The owner confirmed submission by email and python123. The current classroom deck is V5 with 14 screens; verified fixture results and a timed team rehearsal remain pending.

## Start here

- Paper: [final PDF](paper/final_paper.pdf), [editing guide](paper/README.en.md).
- Presentation: [V5](presentation/index.html), [short English script](presentation/PRESENTATION_SCRIPT_EN.md), [results checklist](presentation/RESULTS_DAY_CHECKLIST.md).
- Deliverables: [collection guide, Chinese](交付材料/00_取用与提交说明.md). Generated submission ZIPs are local, not versioned.
- Research: [question overview](研究/README.en.md), [adopted versions](研究/pipeline_state.json).
- Archives: [paper](paper/archive/README.en.md), [presentation](presentation/archive/README.en.md), [relocation record](文档/04_整理记录/仓库优化执行记录_20261111.json).

## Check and run

Run from the repository root:

```powershell
python quick_check.py
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-core.txt
```

The quick check uses only the standard library and currently passes 7/7. Install dependencies only to run research code. Core dependencies are NumPy, SciPy, Matplotlib, psutil, threadpoolctl and pytest. `requirements.txt` freezes the original full environment; the core version ranges are not an identical pinned reproduction environment. See the [local setup guide, Chinese](文档/02_环境配置/克隆仓库后的快速上手.md) and [script guide](scripts/README.en.md).

Recipients of the compact attachments should merge the `FootballProject/` folders from Code.zip and Data.zip. The compact data support core checks and reported results; strict historical replay may require omitted evidence from the full repository.

## Main findings

- Questions 1–3 use the same 24,917 non-neutral matches. Their average home-win differences do not directly identify a causal home advantage.
- On the same 21,413 historical predictions, the joint model reduces log loss by 16.12% relative to background alone and 0.42% relative to strength alone. Binary home-win/non-home-win accuracy is 70.01%; this is neither three-way nor future-fixture accuracy.
- No fixed history length is universally best, and evidence of regional applicability varies.
- Fifty-two Nations League forecasts for 12–17 November 2026 are archived: 49 main binary predictions and three withheld under the venue rule. All 52 also have auxiliary three-way probabilities. No verified actual results have been entered.

## Repository and collaboration

`研究/` follows preparation, identity confirmation and Questions 1–9. `src/` implements methods; `scripts/` provides entry points; `data/` and `outputs/` retain evidence; `paper/` and `presentation/` hold the report and deck; `文档/` holds plans, collaboration records and the research log.

Read [AGENTS.md](AGENTS.md) and the [research log, Chinese](文档/01_项目方案/研究日志与决策记录.md) before substantive work. Update the [supporting-material index, Chinese](文档/05_团队协作/论文与汇报支撑材料索引.md). Independent review starts at [REVIEW_START_HERE.md](REVIEW_START_HERE.md). The report and presentation are in English; the class name remains 睿信2526班 as requested.
