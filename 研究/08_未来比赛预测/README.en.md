# Question 8: archive genuine forecasts before kick-off

[中文](README.md) | **English**


## Question and method

Apply the historical research to the 12–17 November 2026 Nations League fixtures. Ingest available results, extend strength estimates and issue both rounds at a single information cutoff. Separate the joint binary main model from the rating model's auxiliary three-way probabilities, then archive sources and forecasts.

## Findings and limits

All 52 forecasts are archived: 49 main predictions and three withheld for special third-country venues, plus auxiliary home/draw/away probabilities for all 52. Of the 49 main forecasts, 21 favor a home win and 28 a non-home win. Thirty-two conditional strength ranges cross 50%. These counts are forecast properties, not actual prediction scores.

Both rounds use the information available on 2 November. Round 6 does not incorporate the then-unplayed Round 5. A conditional strength 90% range is not a real-world 90% coverage guarantee. The research submission did not depend on waiting for match results; the classroom deck separately supports verified-result entry.

## Materials and reproduction

- [All 52 forecasts and operation, Chinese](运行结果与预测清单.md).
- [Research explanation and closeout, Chinese](第八问_研究说明与收尾交接.md).
- [Adopted forecast pointer](../../outputs/logs/future_predictions/current.json).
- [Script guide](../../scripts/README.en.md#q8).

The forecast entry point is `scripts/predict_future_matches.py`; independent checks use `scripts/audit_future_predictions.py`. Never overwrite a sealed forecast with an after-the-event version. Use [pipeline_state.json](../pipeline_state.json) and the [material index, Chinese](../../文档/05_团队协作/论文与汇报支撑材料索引.md) for adopted materials.

Return to the [overview](../README.en.md) or [paper](../../paper/README.en.md).

## Historical notes

[Preserved original-language README, derivations and version history](../../文档/04_整理记录/README历史快照_20261112/研究/08_未来比赛预测/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.
