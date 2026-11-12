# 正式论文图表目录

**中文** | [English](README.en.md)


当前论文为7图5表；目录也保留候选图，文件名中的数字不直接等于图号。

## 正式图序

1. 研究流程：study_design.tex，随论文编译。
2. 历史概览：fig_historical_overview.pdf。
3. 实力轨迹：fig_strength_states.pdf。
4. 模型比较：fig3_model_comparison.pdf。
5. 历史长度：fig4_history_windows.pdf。
6. 地区诊断：fig5_regional_metrics.pdf。
7. 未来预测例子：fig6_forecast_examples.pdf。

以[Results源](../language_revision_20261107/sections/results.tex)和其调用的strength_development.tex为准，[来源说明](../图表来源说明.md)解释数据；strength_validation_rows.tex供表格使用。旧fig2_era_rates和五张候选清单是历史，不是尚待选图。

## 来源与重绘

[历史概览清单](../historical_overview_manifest.json)、[实力图清单](../strength_evidence_manifest.json)、[结果证据](../results_evidence.json)登记来源版本和选取行。make_paper_figures.py只生成早期候选集，不是全部正式图；另两个生成器分别负责历史概览和实力图。不为阅读而重绘。

论文优先矢量PDF，PNG供预览；图注写样本、时期、单位与边界，条件范围不等于无条件置信保证或因果结论。字体/库可能改变图像字节，应核对来源及实际指纹。研究流程和最终选图已经完成。

## 历史说明

[完整旧README、推导和版本记录](../../文档/04_整理记录/README历史快照_20261112/paper/figures/历史说明.md)按当时日期阅读，不代替当前状态。
