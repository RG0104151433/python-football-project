# 方法文献：原文、用途与阅读记录

**R20261028-01候选方法初筛：** [第三步前四项论证](../../研究/04_共同可靠性/第三步_条件论证与候选方法验收方案.md)给出自包含的条件界推导与显式关联二元模型候选。Q4-P09 [Janson2004](https://doi.org/10.1002/rsa.20008)本轮只取得出版者摘要/元数据，全文抓取未成功，未冒称已验收其具体定理；Q4-P10 [Zhao/Zhang2016](https://www.intlpress.com/site/pub/files/_fulltext/journals/sii/2016/0009/0001/SII-2016-0009-0001-a005.pdf)在线读第2—3节，只借边际/关联分离，不移植其样本重抽样保证。[两份本地下载均失败](../../outputs/logs/reliability/theory-20261028/source_retrieval.json)（证书链、403），没有新增可用PDF；旧原件不变。完整范围见sources.json，不把数学准入/模型可构造说成真实区间已验证。

**R20261027-09模拟验收流程讨论：** Q4-P08，[Morris、White、Crowther 2019](https://doi.org/10.1002/sim.8086)提供模拟研究规划、蒙特卡洛精度和失败报告的指导，已用于[第三步建议流程](../../研究/04_共同可靠性/README.md)；它不为本项目选择依赖模型。[UCL托管PDF](https://discovery.ucl.ac.uk/id/eprint/10066118/1/2019%20-%20Morris%20-%20simulation%20studies%20tutorial%20-%20stat%20med.pdf)可由网页工具阅读，但本机下载返回403，未取得本地原件；[失败登记](../../outputs/logs/reliability/method-planning-20261027/source_retrieval.json)与sources.json如实保留，不列为本地已保存PDF。流程为讨论稿，无新模型或模拟。

**R20261027-08第四问第二步：** 已补齐[目标、数据特征与方法适配资料](../../研究/04_共同可靠性/第二步_目标清单与模型适配资料.md)，重读成对/网络文献关键条件；原件不等于方法已适配。新增三份已验证原文：

- [Abadie等2022作者稿](原文/Abadie_Athey_Imbens_Wooldridge_2022_author.pdf)：抽样与分配机制；不是本项目固定赛程随机结果的现成方差公式。QJE期刊卷期为2023。
- [Cameron/Gelbach/Miller 2009作者稿](原文/Cameron_Gelbach_Miller_2009_multiway.pdf)：多向聚类与数值问题；未冒称保存2011排版版。
- [Romano/Wolf 2005 Econometrica](原文/Romano_Wolf_2005_stepwise.pdf)：联合错误控制；区别同作者2005 JASA文章，不能修复无效的单项分布。

下载状态/指纹及阅读范围见[sources.json](sources.json)与[实际下载记录](../../outputs/logs/reliability/literature-20261027/download_attempts.json)。P03在线HTML封面日期与固定v5 PDF不同，本轮使用固定v5 PDF判断具体版本，既有本地原件未覆盖；没有验收全部证明或选择新估计器。

**R20261027-04研究价值讨论新增阅读：** FORECAST-P01足球Elo及基线比较（仅出版社摘要/预览）、FORECAST-P02概率预测评分（摘要/导言/定义）、FORECAST-M01时间顺序验证。网址、阅读范围与未实现状态见[sources.json](sources.json)；均为在线阅读，无新增本地原文副本。用于讨论第五至第九问的价值与评价要求，不代表相关方法已适配、已有新预测结果或已证明创新。


**R20261027-01新增分类背景来源：** REGION-M06，UEFA土耳其协会官方历史页，2026-10-27在线阅读，未下载HTML。该页记载1962年加入UEFA；仅支持欧洲足球组织背景。土耳其归南欧是用户确认的项目研究约定，伊朗西亚及澳大利亚亚洲/东南亚亦为项目例外，不冒称官方地理分类或全历史足联表。见[sources.json](sources.json)、[本次例外来源登记](../../data/external/geography_sources/study-overrides-20261027/sources.json)和[当前研究分区名单](../../研究/03_地域差异/两版计算范围对照.md)。既有数学文献的推断适配局限与第四问未验收状态保持，不因新增来源而视作已完成可靠性。


**研究分组与原标准分开（R20261026-20）：** 伊朗归西亚、澳大利亚归亚洲/东南亚是用户指定的项目规则，非M49原归类；原标准和HTML原件不修改。旧v3尚未采用这两项。总体分区率差与主客组合条件率是不同统计对象，新增组合先核对支持，不能借用旧整体组的非空覆盖证明。

**第三问实际应用（R20261026-19）：** 直接标准化已经用于同版地域描述，欧洲四组共参考、六对完整输出；[结果与限制](../../研究/03_地域差异/结果审读与展示提纲.md)只作描述解读。没有新增文献、下载或声称成对推断已验收；后续可靠性/敏感性仍归第四问。

**多组描述更新（R20261026-18）：** 直接标准化按每个组分别应用，不要求只有两个组。欧洲四组共用一个参考后再计算6个差值；恒等式Δ_ab+Δ_bc=Δ_ac说明只有3个独立方向，尚不提供总体检验或区间。第四问再决定相关性与多比较方法。未新增论文或宣称已有方法自动适用，原引用范围保持。以下旧六指标表述按所引日志时点理解。

**资料保留复核（R20261026-17）：** 两份M49原件的[引用格式与用途](../../data/external/geography_sources/m49-20261026/README.md)、[当前来源清单](../../data/external/geography_sources/m49-20261026/sources.csv)已整理。旧来源和下载失败记录不改写。[HTML核对记录](../../outputs/logs/regions/design-review-20261026/review.json)逐文件保存路径、SHA与来源登记；10个无独立证据登记的检索缓存只作留痕，不新采纳为引用依据。FPP3缓存仍不是教材正文。未重新联网下载或重审会员事实。

## 正式分区及四项研究结构（R20261026-16）

核读M49欧洲四区及国家条目：本标准没有单列Central Europe，中欧常见国家分属西欧、东欧或南欧；项目不混入第五个重叠组。各大区项目分区来自最深非空层级，不把非洲/美洲的中间层与欧洲次区域冒称同层。完整215球队中文/原名和217日期规则已从验收表导出，原始身份与历史载体政策不变。

当前四项研究包含欧洲/亚洲内部的子项，六个差值不因目录合并而变成四个独立估计；数学方法与推断边界仍见下方。M49两份原文现各保留一份于data/external/geography_sources/m49-20261026/，旧路径由迁移索引解析；未重新下载页面或更改字节/来源版本。完整说明见[阶段第13—15节](../../研究/03_地域差异/README.md#13-当前正式术语代表队范围与四项研究r20261026-16)。

## 当前地域协议已固定（R20261026-14）

第三问[第12节](../../研究/03_地域差异/README.md#12-分组验收三项决定与正式研究清单r20261026-14)及[配置](../../config/regions_study.json)采用固定M49地理框架，加入地理南美005。核读[UNSD overview](https://unstats.un.org/unsd/methodology/m49/overview/)及[Concacaf官方范围](https://es.concacaf.com/inside-concacaf/about-concacaf/index)（REGION-M05），区分圭亚那/苏里南的地理与组织归属；不据当今组织页回填1980—2024足联历史，不改会员裁定，不按实力删除地区成员。没有下载新原件；理论局限及第四问边界仍见下方R11。

## 第三问数学依据复核（R20261026-11）

技术结论及证明见[第三问第10节](../../研究/03_地域差异/README.md#10-数学依据复核方法成立条件和适用边界)：分层比例、共同参考的直接标准化、标准化率差；其成立条件与因果/外推/可靠性分开。参考、主比较及正式推断仍未冻结，没有地域胜率或新检验。

- M02（CDC）本轮重读直接标准化及其比较指标解释；支持公式，不提供足球唯一参考或成对相关区间。
- **REGION-M03｜Westreich、Cole（2010），Invited Commentary: Positivity in Practice。** [期刊页](https://doi.org/10.1093/aje/kwp436)，AJE 171(6):674–677。读取出版者公开摘要及检索返回正文片段，区分结构性/随机缺失与限制样本改变目标；PMC直接访问触发验证，没有下载全文。只借用支持条件辨析，不宣称足球暴露可随机化或已验收全文。
- **REGION-M04｜Hernán、Robins（2006），Estimating causal effects from epidemiological data。** [原文入口](https://pmc.ncbi.nlm.nih.gov/articles/PMC2652882/)，JECH 60(7):578–586，DOI 10.1136/jech.2004.029496。读取公开摘要及检索正文/附录片段，支持标准化的描述计算与因果识别假设分开；BMJ直接访问403、PMC验证页，没有本地全文。此前尝试作者教材PDF，旧哈佛链接重定向个人主页、作者站PDF超工具大小上限；不声称已读整本或绕过验证。
- P01（Aronow等v8）本轮重读正文第2—3节及结论：共享成员、重复和有方向观测有联系，但随机单位抽样、非共享对子无相关和增长框架不由国家队赛程保证。未重验全部证明，第四问估计器、正态近似和模拟仍未验收。

本轮新增的是文献登记及适配判断，没有下载新原件；原有六份本地原件保留。第9节前轮数学讨论原记R20261026-09，与并行Agent新日志冲突，已将主对话前轮条目重分配为R20261026-10并修复可编辑引用，详见R11。

## 当前第三问范围与分类准备（R20261026-05）

用户确认只新增地理分类，主队背景、双方关系和洲内细分的主线及逐步准备见[当前第三问](../../研究/03_地域差异/README.md)。本轮复读M49的地区树、父子层级及更新说明，补充标准快照/分析层级的准备要求；尚未下载分类表或制作球队地理映射。经济来源继续保留为历史阅读，不是当前必采指标；完整历史足联归属不再是前置任务。未新增原文，未开展论文方法验收。

## 第三问因素定位与第四问前置准备（R20261026-04）

[第三问](../../研究/03_地域差异/README.md)已整合主队背景、客队来源与方向性关系，[第四问任务](../../文档/05_团队协作/分工与交付/04_两题共同可靠性与敏感性.md)记录需预先固定的目标、比较范围、逐场结构、参考与方法验收。因素定位仍为建议，不是已经选择所有指标或完成数据准备。

- **REGION-M02｜世界银行国家/经济体分类说明。** [官方页面](https://datahelpdesk.worldbank.org/knowledgebase/articles/378834-how-does-the-world-bank-classify-countries)。核读地理/收入分组的区别、人均GNI定义及按年度更新、历史分类入口；本轮未选择收入阈值或下载经济数据。引用仅说明经济背景是另一测量维度，不能替代地理或足球实力，也不能用当前标签回填全部历史。
- M49分组目的、Liu出版者摘要及Van Damme/Baert作者机构摘要作限定范围复读；未新增全文或重验统计模型。分类标准不保证足球同质性，俱乐部研究也不作为国家队方法已验收的证据。阅读事件追加sources.json；既有原件和下载失败记录保留。

## 第三问：地域含义、对阵关系与洲内细分（2026-10-26）

阅读结论与拟议分组见[第三问当前讨论](../../研究/03_地域差异/README.md)，记录R20261026-03。以下支持问题值得研究，不代表分类已批准、论文方法已验收或本项目已发现地区差异。

- **REGION-M01｜UNSD M49。** [官方分类及问答](https://unstats.un.org/unsd/methodology/m49/)。实际读取大区/次区域、北非/撒哈拉以南、土耳其归类、统计便利说明及修订历史；作为地理标签候选标准，不证明分区内足球、文化或气候相同。没有下载完整历史映射或应用到球队。
- **REGION-P01｜McSharry，2007，Effect of altitude on physiological performance: a statistical analysis using results of international football games。** [大学托管的原文PDF](https://jhanley.biostat.mcgill.ca/bios602/b-d-II-ch-1-2-3/altitude-football.pdf)，DOI 10.1136/bmj.39393.451516.AD。通过网页工具实际读到原文摘要、方法、海拔差定义、模型表和局限，研究南美10支国家队1,460场，说明双方环境关系有实证研究先例；不直接支持用同/跨洲代理距离、也不移植其系数或区间。**本机原文下载两次均失败（沙箱网络权限、获准联网后SSL EOF），没有可用本地PDF副本**，状态和尝试保留在sources.json，不能把URL当成本机已有原件。
- **REGION-P02｜Liu，卷期2024、在线2023，Home Advantage and its Influencing Factors in FIFA World Cup Asian Qualification。** [出版者页面](https://journals.sagepub.com/doi/10.1177/10693971231176149)。本轮只读受限论文的公开摘要及元数据：涉及亚洲预选赛508场及洲内次区域，是洲内差异值得考察的国家队先例。未取得全文，不称已审核其完整分组/模型；其得分及主场优势指标不当作本项目的主胜率。

另核对了[Van Damme和Baert 2019的作者机构说明](https://biblio.ugent.be/publication/8653769)：标题中的international实际指欧冠/欧联俱乐部样本，未将其误作国家队证据。Pollard相关文献及海湾气候研究检索结果可作后续线索，本轮未取得其可充分核读的原文，不据它们给本项目效应数字或方法保证。原有六份下载成功的阅读原件不变。

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
