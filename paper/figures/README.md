# 论文选图目录

**2026-11-05 准备状态：** 已生成 5 张英文**候选图**（fig2—fig6），由 `paper/make_paper_figures.py` 从当前采用结果 CSV 重绘，尚未作为最终论文选图。fig1（研究流程）仍需手工/Agent 绘制。

## 已生成候选图

| 文件 | 内容 | 数据来源 |
|---|---|---|
| `fig2_era_rates.pdf/.png` | 年代主胜率：观测 vs 共同构成调整 | `era_estimates.csv`、`era_summary.csv` |
| `fig3_model_comparison.pdf/.png` | M0/M1/M3 同场预测比较 | `yearly_metrics.csv` |
| `fig4_history_windows.pdf/.png` | 历史窗口组合的表现与成本 | `combination_metrics.csv`、`cost_components.csv` |
| `fig5_regional_metrics.pdf/.png` | 地区概率质量与校准偏差 | `regional_metrics.csv` |
| `fig6_forecast_examples.pdf/.png` | 四个赛前预测代表例 | `forecasts.csv` |
| `manifest.json` | 生成时间、脚本 SHA-256、每张图 PDF/PNG SHA-256、源 CSV 路径 | 自动生成 |

生成命令（仓库根目录）：

```powershell
.\.venv\Scripts\python.exe paper\make_paper_figures.py
```

## 仍需手工完成

- **fig1_study_design：** 数据→清洗→研究人群→四套样本→九问的五部分论文映射；建议用 TikZ/PPT 画，不用截图。建议版面：
  - 左侧纵向：Raw snapshot 49,945 → Cleaned 48,102（1,803 outside / 40 quarantined）→ Study population 24,917（26,055 candidates / 1,138 excluded / 117 owner-approved）。
  - 中间横向：Four analysis samples（24,917 descriptive；21,413 historical prediction；16,599/9,727 window evaluation；52 prospective）。
  - 右侧：Five paper parts（Introduction；Method 2.1—2.5；Results 3.1—3.4；Discussion；References）与九问的对应箭头。
  - 必须在 48,102→24,917 之间标“date / identity / venue / tournament eligibility”，不要画成单一漏斗；52 场单独标“prospective, outcomes unknown”。
- **最终选图：** 从 5 张候选中选 4—5 张主文图；未选中的可放附录或不用。
- **图注与正文解释：** 每张图写明样本/时期/n、指标/单位、能说明什么、不能说明什么。
- **图表来源说明：** 选定后把实际文件、源 SHA、目标 SHA、版本登记到[图表来源说明](../图表来源说明.md)；`manifest.json` 已保存当前候选图的 SHA，可作为起点。

## 规则

- 正文优先 PDF 矢量图；PNG 只作预览或网页/幻灯片。
- 图内不出现中文、内部版本号、脚本名或 `pooled_matches` 等术语。
- 图内不写“significant”“causal”“95% CI”。
- 每张图只表达一个信息；不要把 29 项差值、52 场全塞进一张图。
- 重跑脚本可能因字体/库版本改变 PNG 字节；以 manifest 的源 CSV 和脚本 SHA 为准，不把不同环境的图片字节当同一文件。
