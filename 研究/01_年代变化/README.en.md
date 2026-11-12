# Question 1: does home performance change across periods?

[中文](README.md) | **English**


## Question and method

How did home-win rates change during 1980–2024? Do the differences change after applying the same mix of friendlies and other matches?

Use the same 24,917 matches across five periods. Calculate observed rates, then standardize match-type composition. Question 4 assesses uncertainty and sensitivity; Question 5 introduces pre-match strength.

## Findings and limits

Observed rates do not change monotonically. After composition adjustment, the 2010s and 2020–2024 are 0.5019 and 1.8100 percentage points above the 1980s. Both highlighted model-conditional ranges in Question 4 cross zero, so a directional improvement is not established.

The last period contains only five years. These are average match outcomes, not a causal home effect. Keep the descriptive and strength-adjusted analyses distinct.

## Materials and reproduction

- [Closeout and speaking outline, Chinese](收尾核查与汇报提纲.md).
- [Final review and handoff, Chinese](最终审查与后续衔接.md).
- [Adopted run](../../outputs/logs/team_identity/confirmed-eras-20261025T013539824757Z-45eb57c2/run_manifest.json).
- [Local reproduction, Chinese](本地运行与复现.md), [script guide](../../scripts/README.en.md#q1).

From the repository root:

```powershell
python scripts/analyze_confirmed_eras.py --config config/confirmed_eras_reviewed.json
```

The default older configuration is not the adopted 24,917-match analysis. Check [pipeline_state.json](../pipeline_state.json) and the [material index, Chinese](../../文档/05_团队协作/论文与汇报支撑材料索引.md).

Return to the [overview](../README.en.md) or [paper](../../paper/README.en.md).

## Historical notes

[Preserved original-language README, derivations and version history](../../文档/04_整理记录/README历史快照_20261112/研究/01_年代变化/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.
