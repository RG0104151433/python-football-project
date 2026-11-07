# 论文引用核实记录

**R20261107-02编辑说明：** 本轮沿用15条引用与原有阅读边界，没有新增外部来源、全文核读或模型比较；仅精简相关工作和重复表述，所有引用键仍实际使用。当前稿件指纹见`editorial_revision_manifest.json`，下方各次登记保留原日期。

## Introduction增补（R20261107-01）

2026-11-06开始、11-07完成，Codex（AI）；当前15条已用来源。本轮新增两条领域相关工作，11-06核对出版者文本，其余复用R06/R07已登记的有限主张，不把本轮称为全部原文重读。Abstract只汇总本组已有证据，不添加外部结论或新实验。

- **pollard2017qualification**：出版者[文章页](https://www.tandfonline.com/doi/abs/10.1080/24748668.2017.1304031?page=1)的搜索可见摘要与[官方卷期目录](https://www.tandfonline.com/toc/rpan20/17/1-2)；核实Richard Pollard、Vasilis Armatas、2017、17(1—2):121—135、DOI 10.1080/24748668.2017.1304031。正文仅使用“研究2006/2010/2014世界杯资格赛小组阶段”这一设置说明。文章直接打开返回403，实际依据为工具返回的出版者搜索可见文本；未绕过访问限制、下载原文、阅读全文或移用其原因/显著性/数值结果。相关工作用于说明国际比赛已有前人研究，不声称本组首次讨论主场问题。
- **hvattum2010elo**：出版者[ScienceDirect记录](https://www.sciencedirect.com/science/article/pii/S0169207009001708)的搜索可见元数据/摘要，核实Hvattum/Arntzen、2010、International Journal of Forecasting 26(3):460—470、DOI 10.1016/j.ijforecast.2009.10.002。支持“过去表现的Elo评级转为ordered-logit预测协变量”。直接打开返回403，未称全文已读、未引入其精确更新公式或实测领先幅度，更未宣称本组已比较或击败该系统。

最初搜索也出现Pollard2006的俱乐部地理差异论文和其他二手条目；本轮最终采用与国家队更直接相关的2017资格赛研究，未将2006的国家联赛误写成国家队证据。Bib条目和有限论断按可读出版者文本登记；访问限制保留为阅读边界，不为引用数量增加无关材料。

补入的Data and code availability仅说明CC0原数据及实际仓库材料，不声称已公开归档或完成独立复现。

引言的项目范围、三个问题与结论预告对应已定稿框架及Method/Results/Discussion；摘要的24,917、21,413、1990—2024、16.12%、0.42%、70.01%、52/49/3均来自已有正文及其证据登记。当前稿件指纹与检查见`content_draft_manifest.json`。

## Discussion增补（R20261106-07）

2026-11-06，Codex（AI）；当前共13条已用来源，未经成员本人独立复核。R06的10条及当时阅读范围保留在下方；本次只新增未来工作真正用到的3条，未实施对应优化。

- **herbrich2006trueskill**：[官方会议页面](https://proceedings.neurips.cc/paper/2006/hash/f44ee263952e65b3610b8ba51229d1f9-Abstract.html)与[原文PDF](https://proceedings.neurips.cc/paper/2006/file/f44ee263952e65b3610b8ba51229d1f9-Paper.pdf)。核实三作者和NIPS 2006、volume 19；按该官方会议年度记2006，未添加未核实页码/DOI。实际阅读摘要及第2节关于表现差、draw margin和Gaussian filtering的段落（PDF物理第1—3页），只在4.3支撑“平局区间是一种可参考构造”，不将多人游戏实验的性能结论移植到国家队，也不冒称全文复现。网页BibTeX接口因工具不支持application/x-bibtex未能读取；正文元数据从可读官方页面取得。
- **guo2017calibration**：[PMLR官方记录](https://proceedings.mlr.press/v70/guo17a.html)。核实Guo/Pleiss/Sun/Weinberger、ICML 2017、PMLR 70:1321—1330；阅读摘要和官方引用元数据，支持temperature scaling这一已发表校正示例。原实验为神经分类器，不证明本项目同样有效，正文已明确须另做按时间检验；未宣称全文公式审定或项目已试跑。
- **dixon1997scores**：[作者机构的论文记录](https://research.lancaster-university.uk/en/publications/modelling-association-football-scores-and-inefficiencies-in-the-f/)。核实Dixon/Coles、1997、Applied Statistics 46(2):265—280与DOI 10.1111/1467-9876.00065；阅读公开摘要，仅支持英格兰联赛/杯赛资料、Poisson回归及球队表现动态这一研究方向。未阅读全文，不引用低比分修正的具体公式或投注收益作为本组结果；与第九问原记录的阅读边界一致。

4.1复用Glickman与Gneiting/Raftery，分别定位动态不确定性和概率评价；不宣称本项目优于未比较的外部评级。4.1—4.2的项目发现和限制依据现有Results/Method证据，4.3四项候选依据第九问说明。稿件及来源绑定见`discussion_draft_manifest.json`。

## Method初始登记（R20261106-06，保留当时范围）

2026-11-06，Codex（AI）；未经成员独立复核。本轮仅录入实际Method需要的10条，未为20—25条建议凑数。`references.bib`记录正式元数据，`citation_map.csv`记录8个主张/用途映射，以下说明真实阅读范围。**核实元数据与有限主张，不等于完整读过或复现每篇论文的定理。**

- **martj42_data**：[原作者仓库](https://github.com/martj42/international_results)。核实源地址；当地快照的场数、截止、许可和未知获取时间按`data/raw/manifest.json`与LICENSE登记，不从当前网页反推本地版本。没有杜撰发布日期或上游commit。
- **un_m49**：[UNSD官方说明](https://unstats.un.org/unsd/methodology/m49/)。核实名称、统计分区及用途；论文覆盖的是基础地理依据，项目土耳其/伊朗/澳大利亚和非洲聚合规则是自定例外，不归给UN。未将网页写成2026年新出版的正式标准。
- **glickman1999dynamic**：[作者PDF](https://www.glicko.net/research/glicko.pdf)。核实作者、1999年、Applied Statistics 48(3):377—394；读首页摘要/方法定位，支持动态实力和估计不确定性的动机，不继承其算法为本组实现，不引用未核读的精确定理。未添加未核实的DOI。
- **minka2001ep**：[作者说明页](https://tminka.github.io/papers/ep/)。核实UAI 2001、362—369与修正版说明，阅读作者对EP/assumed-density近似及矩的介绍；仅支撑近似思想，本项目阻尼/共享球队/跳变实现由源码登记支持，不称作者理论证明本组完整滤波精确。
- **aronow2015dyadic**：[出版者页面](https://www.cambridge.org/core/journals/political-analysis/article/abs/clusterrobust-variance-estimation-for-dyadic-data/D43E12BF35240100C7A4ED3C28912C95)。核实三作者、Political Analysis 23(4):564—577、DOI 10.1093/pan/mpv018；阅读摘要/重复有向对局适用说明，作为双角色相依的动机，不把原文sandwich估计器或渐近定理套给本项目六核程序。仓库已有原文，未重复下载。
- **gneiting2007scoring**：[作者PDF](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf)。核实两作者、JASA 102(477):359—378、DOI 10.1198/016214506000001437；阅读评分规则定义和对数/二次评分的相关说明。Method仅据此解释概率评价原则，项目具体公式直接与评价源码核对，不从proper score推出未来表现保证。
- **howard2021confidence**：[作者arXiv记录及期刊信息](https://arxiv.org/abs/1810.08240)。核实四作者、Annals of Statistics 49(2):1055—1080、DOI 10.1214/20-AOS1991；阅读摘要/时间一致控制定位。仅支持顺序控制的一般原则，项目似然比预算和有限生成器承诺见原数学记录，不宣称其定理证明真实足球区间覆盖。此前v5来源记录继续保留，当前未冒称重读全文。
- **numpy2020**：[项目官方引用](https://numpy.org/citing-numpy/)。核实作者、Nature 585(7825):357—362与DOI；正文只认实际软件用途。Bib作者长表用前三位及`others`，不编造全作者名单。
- **scipy2020**：[项目官方引用](https://scipy.org/citing-scipy/)。核实作者、Nature Methods 17(3):261—272与DOI；同样用前三位及`others`，不把软件论文视为本项目数值最优性证明。
- **matplotlib2007**：[项目官方引用](https://matplotlib.org/stable/project/citing.html)。核实Hunter、Computing in Science & Engineering 9(3):90—95、DOI 10.1109/MCSE.2007.55；只支持实际绘图软件出处。旧`users/project`路由无可读内容，改用官方当前`project/citing`，未绕过访问检查。

Method中的状态转移、三分类信息混合、共同probit及年度惩罚目标均与已采用源码/配置核对；详见`method_evidence.json`。这些是本项目实现/适配的说明，不应仅凭引用把它们说成某篇外部论文的原样公式。未实施FIFA/Elo外部同场基线，故本轮不为它们填无用途引用；后续Introduction/Discussion若使用，应再核实并录入。

构建说明：Biber在当前Windows环境因DLL重定位错误无法启动。曾尝试biblatex的BibTeX兼容后端，但仍出现重跑提示；最终采用标准natbib + BibTeX（unsrtnat数字引用）处理相同文献数据，未安装或覆盖系统工具。切换时仅清理已验证位于paper/build的自动生成辅助文件，保留源文件和研究材料；最终核对引用/参考条目与编译日志，不能把键名检查代替元数据核实。
