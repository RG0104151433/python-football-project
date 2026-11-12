# Question 7: does the same method work equally well across regions?

[中文](README.md) | **English**


## Question and method

Could overall prediction scores conceal regional weaknesses? Reuse archived pre-match strength and forecasts, compare methods on the same matches, then examine strength composition, information support and limited leave-year/leave-team stability checks.

## Findings and limits

The small gains in Europe, Asia and the Americas are comparatively stable. Africa's gain is sensitive to sample deletion, and its probability bias warrants further investigation. South American rankings are not reliably established; Oceania has limited support.

This question diagnoses applicability, rather than repeating Question 3's home-win comparisons. It does not tune regional parameters and then claim independently established improvement. It provides neither unconditional real-world coverage nor a future-performance guarantee.

## Materials and reproduction

- [Plain-language closeout, Chinese](第七问_研究说明与收尾交接.md).
- [Explaining differences, Chinese](第四步_差异解释与第五步交接.md).
- [Stability checks, Chinese](第五步_可靠性检查与脚本规划.md).
- [Script guide](../../scripts/README.en.md#q7).

Distinguish the descriptive, composition-diagnostic and stability entry points. They read existing forecasts rather than refit strength. Resolve adopted versions through [pipeline_state.json](../pipeline_state.json) and the [material index, Chinese](../../文档/05_团队协作/论文与汇报支撑材料索引.md).

Return to the [overview](../README.en.md) or [paper](../../paper/README.en.md).

## Historical notes

[Preserved original-language README, derivations and version history](../../文档/04_整理记录/README历史快照_20261112/研究/07_地区有效性/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.
