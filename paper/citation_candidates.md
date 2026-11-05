# 论文引用候选与核对工作包

**日期：** 2026-11-05  
**执行：** Codex（AI）；未经组员本人复核。  
**用途：** 给后续写作 Agent 一个可直接执行的引用清单；不是已完成的 `references.bib`。所有条目的作者、年份、题名、期刊/会议、卷期、页码、DOI/URL 必须逐条核对后才能写入 BibTeX。

## 1. 目标与验收

- 目标 **20—25 条**，不是把 54 条来源全部搬进论文。
- 每条至少被正文引用一次；正文与 `references.bib` 双向一致。
- 数据、方法、分类、软件、复用代码分别有出处。
- 只读摘要/网页片段的来源，不用于支撑未读定理；只写它确实支持的具体事实。
- 验收命令：

```powershell
.\.venv\Scripts\python.exe paper\check_citations.py --strict
latexmk -xelatex -outdir=build main.tex   # 在 paper/ 下
```

## 2. 优先使用的现有来源

这些在[方法文献登记](../参考资料/方法文献/sources.json)中有记录；大多有本地 PDF。`状态` 指登记状态，不等于论文已读全文。

| Bib key（建议） | 作用 | 题名 | 作者 | 年份/出处 | 本地/登记来源 | 状态 | 主要章节 |
|---|---|---|---|---|---|---|---|
| `aronow2015dyadic` | 相依数据方差 | Cluster-Robust Variance Estimation for Dyadic Data | Aronow; Samii; Assenova | 2015; Political Analysis（待核对卷期） | `参考资料/方法文献/原文/Aronow_Samii_Assenova_2015_dyadic_v8.pdf` | downloaded | 2.4 |
| `cameron2015cluster` | 聚类稳健推断 | A Practitioner's Guide to Cluster-Robust Inference | Cameron; Miller | 2015; J. Human Resources（待核对卷期） | `.../Cameron_Miller_2015_cluster_robust.pdf` | downloaded | 2.4 |
| `abadie2022clustering` | 何时调整聚类 | When Should You Adjust Standard Errors for Clustering? | Abadie; Athey; Imbens; Wooldridge | 2022/2023; QJE（待核对） | `.../Abadie_Athey_Imbens_Wooldridge_2022_author.pdf` | downloaded | 2.4 |
| `romano2005stepwise` | 多重检验 | Stepwise Multiple Testing as Formalized Data Snooping | Romano; Wolf | 2005; Econometrica（待核对卷期） | `.../Romano_Wolf_2005_stepwise.pdf` | downloaded | 2.4 |
| `minka2001ep` | 期望传播 | Expectation Propagation for Approximate Bayesian Inference | Minka | 2001; UAI（待核对页码） | `.../Minka_2001_EP_UAI.pdf` | downloaded | 2.3 |
| `kull2019dirichlet` | 概率校准 | Beyond Temperature Scaling: Obtaining Well-Calibrated Multiclass Probabilities with Dirichlet Calibration | Kull et al. | 2019; NeurIPS（待核对） | `.../Kull_2019_Dirichlet_calibration.pdf` | downloaded | 2.4 / 4.3 |
| `shao2010dependent` | 相依 bootstrap | The Dependent Wild Bootstrap | Shao | 2010; JASA（待核对卷期） | `.../Shao_2010_Dependent_Wild_Bootstrap.pdf` | downloaded | 2.4 |
| `howard2020confidence` | 置信序列 | Time-Uniform, Nonparametric, Nonasymptotic Confidence Sequences | Howard et al. | 2020/2021; Annals of Statistics（待核对） | `.../Howard_etal_2020v5_confidence_sequences.pdf` | downloaded | 2.4 |
| `varma2006bias` | 模型选择偏差 | Bias in Error Estimation When Using Cross-Validation for Model Selection | Varma; Simon | 2006; BMC Bioinformatics | `.../Varma_Simon_2006_model_selection_bias.pdf` | downloaded | 2.4 |
| `gneiting2007scoring` | Proper scoring | Strictly Proper Scoring Rules, Prediction, and Estimation | Gneiting; Raftery | 2007; JASA（待核对卷期） | `.../FORECAST-P02` 网页 PDF | web_read_only | 2.4 / 1.2 |
| `hvattum2010elo` | 足球 Elo 预测 | Using ELO Ratings for Match Result Prediction in Association Football | Hvattum; Arntzen | 2010; Int. J. Forecasting（待核对卷期） | `FORECAST-P01` 网页 | web_read_only | 1.2 |
| `fifa_ranking` | FIFA 排名程序 | FIFA/Coca-Cola Men's World Ranking Procedures | FIFA | 2026; 官方网页（访问日期待填） | `Q5-M01` 网页 | web_read_only | 1.2 / 2.1 |
| `un_m49` | 国家分类 | Standard Country or Area Codes for Statistical Use (M49) | UN Statistics Division | 2026; 官方网页（访问日期待填） | `REGION-M01` 网页 | web_read_only | 2.1 |
| `worldbank_classification` | 国家分类补充 | How Does the World Bank Classify Countries? | World Bank | 2026; 官方网页（访问日期待填） | `REGION-M02` 网页 | web_read_only | 2.1（可选） |
| `martj42_data` | 主数据 | International Football Results from 1872 to 2026 | martj42 (GitHub) | 2026; GitHub; CC0 1.0 | `data/raw/international_results/` | local snapshot | 2.1 |

## 3. BibTeX 格式模板（字段占位，不要照抄）

```bibtex
@article{authorYearTopic,
  author  = {Last, First and Last, First},
  title   = {Exact Title},
  journal = {Journal Name},
  year    = {YYYY},
  volume  = {VV},
  number  = {NN},
  pages   = {PP--PP},
  doi     = {10.XXXX/XXXXX}
}

@book{authorYearBook,
  author    = {Last, First},
  title     = {Book Title},
  publisher = {Publisher},
  address   = {City},
  year      = {YYYY}
}

@misc{sourceKey,
  author       = {{Organization}},
  title        = {Page or Dataset Title},
  year         = {YYYY},
  howpublished = {\url{https://...}},
  note         = {Accessed YYYY-MM-DD}
}
```

## 4. 需要新增/核对的经典来源

这些是论文相关工作/方法定位需要的方向；**不要直接复制下面的简写为 BibTeX**，先核对元数据。

| Bib key（建议） | 作用 | 题名/方向 | 作者 | 年份/出处 | 优先级 | 主要章节 |
|---|---|---|---|---|---|---|
| `elo1978rating` | Elo 评级 | The Rating of Chessplayers, Past and Present | Elo | 1978; Arco（待核对） | A | 1.2 |
| `glickman1999dynamic` | 动态配对比较 | Parameter Estimation in Large Dynamic Paired Comparison Experiments | Glickman | 1999; JRSS C（待核对） | A | 1.2 / 2.2 |
| `herbrich2007trueskill` | TrueSkill | TrueSkill: A Bayesian Skill Rating System | Herbrich; Minka; Graepel | 2007; NIPS（待核对） | A | 1.2 |
| `dixon1997modelling` | 足球比分模型 | Modelling Association Football Scores and Inefficiencies in the Football Betting Market | Dixon; Coles | 1997; JRSS C（待核对） | A | 1.2 / 2.3 |
| `guo2017calibration` | 校准 | On Calibration of Modern Neural Networks | Guo et al. | 2017; ICML（待核对） | A | 4.3 |
| `koopman2015dynamic` | 动态双变量 Poisson | A Dynamic Bivariate Poisson Model for Analysing and Forecasting Match Results in the English Premier League | Koopman; Lit | 2015; JRSS A（待核对） | B | 1.2 / 4.3 |
| `karlis2003bivariate` | 双变量 Poisson | Analysis of Sports Data by Using Bivariate Poisson Models | Karlis; Ntzoufras | 2003; JRSS D（待核对） | B | 1.2（可选） |
| `ley2019ranking` | 足球排名 | Ranking Soccer Teams on the Basis of Their Current Strength: A Comparison of Maximum Likelihood Approaches | Ley et al. | 2019; Statistical Modelling（待核对） | B | 1.2（可选） |
| `numpy2020` | 软件 | Array Programming with NumPy | Harris et al. | 2020; Nature（待核对） | C | 2.5 |
| `scipy2020` | 软件 | SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python | Virtanen et al. | 2020; Nature Methods（待核对） | C | 2.5 |
| `matplotlib2007` | 软件 | Matplotlib: A 2D Graphics Environment | Hunter | 2007; Computing in Science & Engineering（待核对） | C | 2.5 |

## 5. Agent 执行步骤

1. **建立候选表：** 复制本文件第 2—3 节到 `paper/citation_candidates.csv`（或直接在 BibTeX 工作区维护），每条填 `status = verified / partial / rejected`。
2. **核对元数据：** 打开本地 PDF 首页/DOI 页或出版方页面，核对 authors、year、title、venue、volume、pages、DOI/URL。网页来源加 `urldate`。
3. **写 BibTeX：** 在 `paper/references.bib` 中每条只写一次；key 用 `authorYearTopic`；字段完整、大小写一致；不要写没有核对的页码。
4. **建立引用映射：** 在 `paper/citation_map.csv` 写 `section, claim_id, bib_keys, note`，把正文段落与来源绑定；每个 claim 至少一个来源。
5. **插入正文：** 按 `paper/论文规划审查与开工准备_v2_20261105.md` 第 2 节提纲在对应小节加 `\cite{...}`；不要在 Introduction 堆一批与正文无关的文献。
6. **检查：** 运行 `python paper/check_citations.py --strict`；再在 `paper/` 下运行 `latexmk -xelatex -outdir=build main.tex`（biber 会自动执行），确认 0 undefined citations。
7. **报告：** 在 `paper/citation_report.md` 写：已核对条目、拒绝条目、仍不确定的条目、每条支撑的章节/claim。

## 6. 引用边界

- `sources.json` 的 54 条是资料登记，不是 54 篇已读全文；只引用真正支撑论点的条目。
- 只读摘要的来源（如 TrueSkill、部分 REGION 资料）只能支撑“该方法存在/官方说明如此”这类事实，不能支撑未读的定理细节。
- 数据引用写清快照日期、版本/哈希、许可（CC0 1.0）；不要复制上游 README 的旧计数（49,459/截止 2024）。
- 图全部是自制：写“generated by the authors from [data/version]”，不要给不存在的来源。
- 复用代码：本次未发现外部代码版权头；若实际借用了代码/模板，补引用并在 Author Contributions 说明自身实现；若全部自己写，明确写“code implemented by the team; libraries cited”。
- 不把 AI 写成作者；工具辅助按实际说明。
