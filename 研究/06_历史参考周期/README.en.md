# Question 6: how much history should predict the next match?

[中文](README.md) | **English**


## Question and method

Distinguish history for estimating strength from history for learning outcome relationships. Compare 2, 4, 8, 12 and 20 years with cumulative history, then a small set of combinations and past-only adaptive selection. Supplement with simulations and limited stability checks. Assess probability quality and computing cost separately.

## Findings and limits

Within the tested method and sample, neither fixed short windows nor adaptive selection outperform the cumulative default. Restricting outcome-model history to 12 years saves approximately 66% of that computation, with roughly a 0.36% relative increase in the principal later-period mean loss; it does not replace the default.

No universally best number of years is established. The saving concerns the relevant computation, not the entire project; the loss change is not an accuracy change. The principal 2010–2024 comparison contains 9,727 matches, not the first three questions' denominator.

## Materials and reproduction

- [Plain-language closeout, Chinese](第六问_研究说明与收尾交接.md).
- [Rating memory and long simulations, Chinese](第五步_评分记忆与长模拟运行交接.md).
- [Stage HTML](展示/index.html), [script guide](../../scripts/README.en.md#q6).

Use `scripts/analyze_history_window.py` according to the staged instructions. Final match-level features and states remain; redundant intermediate checkpoints can be regenerated. Adopted versions are in [pipeline_state.json](../pipeline_state.json) and the [material index, Chinese](../../文档/05_团队协作/论文与汇报支撑材料索引.md).

Return to the [overview](../README.en.md) or [paper](../../paper/README.en.md).

## Historical notes

[Preserved original-language README, derivations and version history](../../文档/04_整理记录/README历史快照_20261112/研究/06_历史参考周期/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.
