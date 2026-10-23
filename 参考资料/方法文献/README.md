# 方法文献：原文、用途与阅读记录

整理日期：2026-10-23。文献用于第一题的方法讨论，不代表其适配性已经通过本项目验证。

本机原文放在 `原文/`，下载版本、网址、时间、字节数、SHA-256 和成败状态登记在 [sources.json](sources.json)。首次下载失败后已对部分文件重试；以清单的最终状态为准。阅读副本未修改。

按用户确认，已取得并验证的 5 份 PDF 和 NIST 网页允许随仓库提交，队友克隆后可直接阅读；来源、作者、版本和指纹继续保留。当前只是调整文件收录规则，尚未执行 Git 提交或推送。下载失败或仅返回验证页的文件继续排除，清单保留实际状态。用户允许上传的决定不写成已核定所有来源的再分发许可。

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
