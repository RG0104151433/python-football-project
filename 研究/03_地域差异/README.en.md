# Question 3: geography, opponent relationships and home performance

[中文](README.md) | **English**


## Question and method

How do outcomes differ by the home team's region, subregion and opponent origin? Fix classifications for both roles before calculating overall rates and directed home–away combinations. Compare supported targets under a common period-by-match-type composition. The study covers four geographic comparisons, rather than selecting only extremes.

## Findings and limits

There are 29 contrasts and 155 home–away combinations. Twenty-four full-period adjusted contrasts are estimable. Of the combinations, 153 have matches and 71 support complete adjustment. Under Question 4's assumptions, six of the 24 conditional contrast ranges lie on one side of zero; 18 cross zero.

These patterns reflect opponent composition and geography; they do not rank regions by pure home advantage. Turkey belongs to Europe/Southern Europe, Iran to Western Asia, and Australia to Asia/Southeastern Asia under explicit study conventions. Africa has three study groups; Oceania is not subdivided. Unsupported cells remain unavailable, never zero-filled.

## Materials and reproduction

- [Interpretation and presentation outline, Chinese](结果审读与展示提纲.md).
- [Scope and classification comparison, Chinese](两版计算范围对照.md).
- [Adopted run](../../outputs/logs/regions/closeout-20261027/regions-20261027T084412226301Z-f05899a3/run_manifest.json).
- [Local reproduction, Chinese](本地运行与复现.md), [script guide](../../scripts/README.en.md#q3).

```powershell
python scripts/analyze_regions.py --config config/regions_study.json
```

Use [pipeline_state.json](../pipeline_state.json) and the [material index, Chinese](../../文档/05_团队协作/论文与汇报支撑材料索引.md) for adopted versions.

Return to the [overview](../README.en.md) or [paper](../../paper/README.en.md).

## Historical notes

[Preserved original-language README, derivations and version history](../../文档/04_整理记录/README历史快照_20261112/研究/03_地域差异/历史说明.md) describe their own dates. This English edition covers the current guide; historical records remain in their original language.
