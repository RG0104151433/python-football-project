# 方法文献：原文、用途与阅读记录

整理日期：2026-10-23。文献用于第一题的方法讨论，不代表其适配性已经通过本项目验证。

本机原文放在 `原文/`，下载版本、网址、时间、字节数、SHA-256 和成败状态登记在 [sources.json](sources.json)。首次下载失败后已对部分文件重试；以清单的最终状态为准。阅读副本未修改。

按用户确认，已取得并验证的 5 份 PDF 和 NIST 网页允许随仓库提交；来源、作者、版本和指纹继续保留。2026-10-24 核对时，这 6 份原文均已被本地 Git 跟踪；是否已同步远端未核验，队友克隆后应检查实际文件。此前“尚未提交”的文字只描述最初整理时的状态。下载失败或仅返回验证页的文件继续排除，清单保留实际状态。用户允许上传的决定不写成已核定所有来源的再分发许可。

## 核心论文

- **P01｜Aronow、Samii、Assenova，Cluster-Robust Variance Estimation for Dyadic Data。** [来源](https://arxiv.org/abs/1312.3398v8)，本地 `原文/Aronow_Samii_Assenova_2015_dyadic_v8.pdf`。重点读第 2—3 节：共享球队、重复及方向性观测的方差；不能单独作为正态近似区间的充分依据。
- **P02｜Tabord-Meehan，Inference with Dyadic Data: Asymptotic Behavior of the Dyadic-Robust t-Statistic。** [来源](https://arxiv.org/abs/1510.07074v6)，本地 `原文/Tabord_Meehan_dyadic_inference_v6.pdf`。保存的是 2017 年修订预印本；讨论正态近似、不均衡与正负相关抵消，不按最初提交年冒称期刊发表年。
- **P03｜Canen、Sugiura，Inference in Linear Dyadic Data Models with Network Spillovers。** [来源](https://arxiv.org/abs/2203.03497v5)，本地 `原文/Canen_Sugiura_network_spillovers_v5.pdf`。保存 2023 年修订预印本，期刊版为 Political Analysis 32 (2024), 311–328；用于检查共享球队以外的依赖，不是已经选定的替代估计器。
- **P04｜Cameron、Miller，A Practitioner's Guide to Cluster-Robust Inference，2015。** [作者原文](https://cameron.econ.ucdavis.edu/research/Cameron_Miller_JHR_2015.pdf)，本地 `原文/Cameron_Miller_2015_cluster_robust.pdf`。用于理解相关观测、有效信息与有限样本问题；泛用聚类公式不能直接替代成对结构。

## 方法说明与教材

- **M01｜Klein、Schoenborn，Age Adjustment Using the 2000 Projected U.S. Population，2001。** [CDC 原链接](https://www.cdc.gov/nchs/data/statnt/statnt20.pdf)，[CDC 官方存档](https://ftp.cdc.gov/pub/health_statistics/NCHS/Publications/DVD/DVD_3/Healthy_People_2000/Healthy_People_Statistical_Notes/statnt20.pdf)。官网直链返回 403 后，从官方存档保存 `原文/CDC_Klein_Schoenborn_2001_standardization.pdf`，两个地址的文件不能未经比对声称字节相同。用于共同参考构成与方差处理的区分。
- **M02｜CDC，Age adjustment。** [网页](https://www.cdc.gov/nchs/hus/sources-definitions/age-adjustment.htm)。工具可阅读，但本机直接下载返回 403，本轮没有网页原文副本；失败状态保留在清单。不影响 M01 技术原文的本地保存。
- **M03｜NIST，Confidence intervals。** [网页](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)，保存 `原文/NIST_Wilson_intervals.html`。说明 Wilson 的方法来源，不将其视为比赛相关性已经得到处理。
- **M04｜Hyndman、Athanasopoulos，Forecasting: Principles and Practice，The forecaster's toolbox。** [教材](https://otexts.com/fpp3/toolbox.html)。用于区分时间验证选参与回顾性标准化。本机下载得到反机器人跳转页，未取得教材正文，清单标 blocked；缓存响应不计作文献原文，不尝试绕过验证。

## 思路保存在哪里

[第一题阶段 README](../../研究/01_年代变化/README.md)负责向读者说明问题、方法、状态与成果入口；[五步规划](../../文档/01_项目方案/第一题_年代变化研究五步规划.md)保存详细理由与处理判断；[研究日志](../../文档/01_项目方案/研究日志与决策记录.md)按时间追加决定、更正和真实结果。不要再在此复制另一份结论。

后续增加文献时先登记来源与本地状态，再记录它支持或推翻哪个决定。新版本不覆盖旧版本；无法获得全文时只保留可核查链接与缺口说明。


## 第二问理论复核与阅读范围（2026-10-25）

理论判断与拟议实现保存在[第二问脚本设计](../../研究/02_赛事类型差异/脚本设计.md)第1—2节；不是新的统计结果或已验收的推断协议。

- 重新阅读[CDC直接标准化说明](https://www.cdc.gov/nchs/hus/sources-definitions/age-adjustment.htm)：支持共同构成的加权比较，不为足球指定最优参考或因果解释。
- 重新阅读[NIST Single Moving Average](https://www.itl.nist.gov/div898/handbook/pmc/section4/pmc421.htm)：窗口前移与平滑结构可用，本题采用场次加权的年度比例，不能照搬年度等权公式。
- 阅读[Zhang 2006官方文献页摘要](https://www.nist.gov/publications/calculation-uncertainty-mean-autocorrelated-measurements)：其区间针对平稳过程，未验证可直接用于本项目；本轮未阅读该论文完整推导。
- 重新核读[Aronow等正文的Setting及重复观测说明](https://arxiv.org/html/1312.3398v8)：共享单位结构相关，但随机单位抽样、非共享对子不相关及增长框架不由当前足球赛程自动满足。
- [Tabord-Meehan v6](https://arxiv.org/abs/1510.07074v6)和[Canen/Sugiura v5](https://arxiv.org/abs/2203.03497v5)本轮重读版本元数据与摘要，未重新验证全部证明。正态近似与非共享对子关联仍需共同阶段处理。

本轮网页可读不改变M02此前“本地下载失败”的历史状态；阅读事件单独追加到sources.json。未新增下载原文或改写已有PDF。FPP3_forecasting_toolbox.html是反机器人响应，不是教材正文；本次从论文支撑材料索引移除该错误引用，原失败登记和缓存不删除。
