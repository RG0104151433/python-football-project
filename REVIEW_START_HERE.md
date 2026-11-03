# Independent Review: Repository Entry

This document provides navigation only. No findings or verdict are prescribed.

## Start here

Read [AGENTS.md](AGENTS.md), [README.md](README.md), and [the research log](文档/01_项目方案/研究日志与决策记录.md), as required by the repository's collaboration rules. Start with the log's current summary, then retrieve entries relevant to your scope; do not dump its full history by default. Treat repository statements and prior check reports as claims and recorded evidence, not an independent verdict.

## Locations

- [Original course requirements](参考资料/课程原始截图/)
- [Research documents](研究/) and [version/state register](研究/pipeline_state.json)
- [Implementation](src/) and [execution entries](scripts/)
- [Script navigation](scripts/README.md) and [file inventory](scripts/脚本用途目录.md)
- [Configurations](config/) and [root configuration](config.json)
- [Data](data/) and [recorded outputs](outputs/)
- [Source materials](参考资料/)
- [Paper project](paper/)
- [Environment setup](文档/02_环境配置/克隆仓库后的快速上手.md)

Use the repository root as the working directory. Use a local Python environment; do not copy another machine's environment or absolute paths. Inspect an entry before executing it.

The project owner has specified that the final course paper and presentation must be in English. This is a delivery constraint, not an assessment of the current files.

## Independent review

Follow the review scope provided by the requester. Where it is unspecified, state the scope you select. Choose evidence, checks, and conclusions independently.

Preserve source data and existing results. Keep review outputs separate from the files under examination. Follow AGENTS.md for substantive findings and logging; do not edit previous entries.

## Token-efficient working instructions

1. **Locate before reading.** Use `rg --files` to discover paths and `rg -n` to locate relevant passages. Read bounded sections, expanding only when needed. Avoid recursively printing the repository or opening every file in a directory.
2. **Skip tooling internals by default.** Exclude `.git/`, `.venv/`, `.mimosa/`, `.idea/`, `.pytest_cache/`, and `__pycache__/` from content searches unless the assigned scope concerns them. For an unfamiliar generated directory, inspect its location, names, sizes, and a small sample before deciding whether further reading is relevant. Do not exhaustively inspect tool state merely because it exists.
3. **Summarize large files locally.** For CSV/JSON/logs, select relevant fields, schemas, counts, or bounded records rather than returning entire payloads. Inspect archive listings before extracting anything; never print encoded binary contents. Narrow access to research data and outputs instead of treating all generated results as disposable or irrelevant.
4. **Choose the smallest sufficient checks.** Select evidence and representative checks independently. Expand when the available evidence cannot resolve the scoped question. A sample must not be reported as an exhaustive review. Do not launch all scripts, retrain models, or repeat long simulations solely to make the review look comprehensive.
5. **Avoid duplicate work.** Keep a short record of paths and checks already examined. Repeat a check only after a relevant change, failure, or unresolved inconsistency. Existing check records can guide where to look, but cannot be relabelled as checks you executed. Do not create duplicate data copies, source snapshots, or checkpoint sets merely for the review.
6. **Keep outputs compact.** Return findings with precise paths/lines and the minimum evidence needed to reproduce or assess them. Avoid long quotations, repeated repository summaries, and transcripts of successful commands. State what remains unverified rather than spending repeated passes on the same evidence. Finish when the assigned scope has evidence-supported answers or clearly recorded limits.

Report the scope and version examined, checks actually executed, observations, interpretations, and remaining uncertainty. Do not report unperformed checks as completed. These instructions control resource use, not what to find: no particular outcome is required.
