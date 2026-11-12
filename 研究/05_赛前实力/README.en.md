# Question 5: does context add information beyond pre-match strength?

[中文](README.md) | **English**


## Question and method

Estimate both teams using information available before kick-off, then ask whether period, match type and region retain information and improve prediction. Predict before learning each result; update both teams and retain strength uncertainty. Compare background-only, strength-only and joint models, followed by sensitivity analysis and two-route inference validation.

## Findings and limits

On the same 21,413 historical predictions, strength plus context reduces log loss by 16.12% relative to background alone and 0.42% relative to strength alone. Binary accuracy is 70.01%.

The adopted inference route is the full nonlinear Route A. Thirty targets qualify for model-conditional reference results; 24 geographic before/after changes do not qualify. Do not describe all 54 targets as passing.

Chronological historical prediction is not a new untouched test. Binary accuracy is not three-way accuracy, and conditional statistical evidence is not a causal context effect.

## Materials and reproduction

- [Closeout and handoff, Chinese](第五问_收尾与下一问交接.md).
- [Strength logic and operation, Chinese](实力评估_逻辑与运行说明.md).
- [Stage HTML](展示/index.html).
- [Rating handoff, Chinese](第二环节_验收与正式交接.md), [script guide](../../scripts/README.en.md#q5).

Select the rating, joint-analysis and inference entry points separately. Avoid rerunning all simulations for a basic installation check. Resolve adopted outputs using [pipeline_state.json](../pipeline_state.json) and the [material index, Chinese](../../文档/05_团队协作/论文与汇报支撑材料索引.md).

Return to the [overview](../README.en.md) or [paper](../../paper/README.en.md).

## Historical notes

[Preserved original-language README, derivations and version history](../../文档/04_整理记录/README历史快照_20261112/研究/05_赛前实力/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.
