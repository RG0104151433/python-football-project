# Question 2: how do friendlies differ from other matches?

[中文](README.md) | **English**


## Question and method

Compare home-win rates overall, after standardizing period composition, and over time. Use the same 24,917 matches as Question 1: overall and period-specific rates, a common period reference, and 36 overlapping ten-year windows.

## Findings and limits

The friendly home-win rate is 48.3955%, versus 51.6418% for other matches. The direct difference is −3.2463 percentage points; period standardization changes it to −2.8831 points.

Recent patterns differ, but Question 4 does not establish a stable reversal. Its model-conditional ranges for the overall difference, the recent comparison and the 36 windows cross zero. Overlapping windows share matches and are not independent replications. Classification differences do not identify a causal effect of match type.

## Materials and reproduction

- [Closeout and speaking outline, Chinese](收尾核查与汇报提纲.md).
- [Run manifest](../../outputs/logs/tournaments/tournaments-20261025T022318417600Z-78d8e623/run_manifest.json).
- [Local reproduction, Chinese](本地运行与复现.md), [script guide](../../scripts/README.en.md#q2).

```powershell
python scripts/analyze_tournaments.py --config config/tournaments.json
```

Select versions through [pipeline_state.json](../pipeline_state.json) and the [material index, Chinese](../../文档/05_团队协作/论文与汇报支撑材料索引.md).

Return to the [overview](../README.en.md) or [paper](../../paper/README.en.md).

## Historical notes

[Preserved original-language README, derivations and version history](../../文档/04_整理记录/README历史快照_20261112/研究/02_赛事类型差异/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.
