# Question 4: how far can the first three findings be supported?

[中文](README.md) | **English**


## Question and method

Assess uncertainty and stability when matches share teams, years and common fluctuations. Fix the targets and references, compare and improve candidate models, test against simulations with known targets, then calculate conditional ranges and prescribed descriptive sensitivity analyses.

## Findings and limits

Conditional ranges are available for 198 targets; 94 unsupported targets remain blank. Sensitivity analysis adds 324 scenarios and 26,704 comparison rows. Highlighted period and match-type ranges cross zero, while some geographic contrasts retain conditional directional support.

These ranges depend on the selected model assumptions. They are not unconditional coverage guarantees for real football. Sensitivity variants do not automatically receive newly calibrated intervals. This question does not yet control pre-match strength.

## Materials and reproduction

- [Application and reproduction, Chinese](第四步_运行结果与复现.md).
- [Model iteration and selection, Chinese](第三步_联合模型选择与第四步交接.md).
- [Adoption record](../../outputs/logs/reliability/application-20261028/adoption.json).
- [Script guide](../../scripts/README.en.md#q4).

Use `scripts/analyze_reliability.py` as instructed in the application guide. Distinguish adopted application from historical method development; do not rerun every simulation to check an environment.

See [pipeline_state.json](../pipeline_state.json) and the [material index, Chinese](../../文档/05_团队协作/论文与汇报支撑材料索引.md).

Return to the [overview](../README.en.md) or [paper](../../paper/README.en.md).

## Historical notes

[Preserved original-language README, derivations and version history](../../文档/04_整理记录/README历史快照_20261112/研究/04_共同可靠性/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.
