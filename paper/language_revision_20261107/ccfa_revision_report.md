# 基于CCFA-Skills反推论文标准与本轮修改说明

本轮日期：2026-11-08；记录：R20261108-01；执行者：Codex（AI）。当前修改对象为`paper/language_revision_20261107/`，上级原版源文件/PDF保留。

## 1. 先说明结论

从该技能的操作反推，好的论文首先是一条有具体对象和证据的论证：问题决定方法，方法产生可核对的结果，结果支持有范围的结论。语言和图表应帮助读者理解这条关系。它并没有要求所有论文都发明新算法、胜过全部SOTA、补齐固定数量的消融，或者把提醒全部删除。

本轮完成15处实质修改。重点不是改变研究或再加模块，而是把原稿已有的“历史差异能在赛前实力之外增加多少预测信息”放到更清楚的位置，并贯通摘要、引言、方法和结论。主要数字、18条文献、12个显示公式、7图5表以及重要负结果保留。

这是一轮作者侧的论证与写作修订，不是官方CCF-A评审、录用评分或新的模型性能证明。

## 2. 实际读取了什么，怎样避免凭README臆测

固定来源：[mikubaka88/CCFA-Skills](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/README.md)，commit `91ca9e2801698466f934b557a75ce46db8ba46b5`。固定版本README标为v0.12.1、18个技能；本轮不以网页缓存的另一版本作为依据。

本地来源保存在`文档/05_团队协作/论文写作技能/CCFA-Skills/91ca9e280169/`，含原LICENSE、18个技能入口及本轮使用的共享/写作参考。`source_manifest.json`登记文件、版本和获取情况。这是阅读材料摘录，不是全局安装或一个完整可部署插件。

主要依据为humanization、common、paper-writer、paper-reviewer、integrity-auditor、experiment-designer、visual-composer和submission-checker的入口规则，以及storyline、prose guardrails、review rubric和共享交付规则的相关段落；其余入口用于核对职责与流程。没有宣称逐条执行了所有技能或全文验证所有外链参考。

按入口要求先读取Humanization与Common，并运行了只读偏好解析。默认独立额外审查为off，本轮由同一执行者做写作与内部对齐，没有伪称多专家独立评审。你明确要求详细修改说明，因此报告按本次请求详述，不另开实验或评审打分。

语言检查器在阅读代码后以本地只读方式运行；没有全局安装、启动配置服务或上传论文内容。已复用本地Groll原文的摘要/引言来检查“目标—输入—操作—输出”的说明关系，没有复制其特色句子或引入其结果为我们的证据。

## 3. 从操作反推的十二项标准

以下每项分开列“技能直接规定”“反推的质量要求”“本项目如何落实”。后两项是本轮归纳和应用，不冒充技能原文或CCF官方统一标准。

### S1｜问题要具体到能决定分析怎么做

- 技能直接规定：storyline-blueprint先恢复研究问题、困难、操作和结论。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-paper-writer/references/storyline-blueprint.md#L7)
- 从这一步反推：好论文不能只有“分析足球数据”这样的主题；应有能区分方法和结果的具体问题。
- 本项目应用：本项目以“历史背景能在赛前实力之外增加多少预测信息”为主轴，保留三个RQ作为分解。 对应修改：E01, E02, E03, E04, E14。

### S2｜贡献类型必须与证据相称

- 技能直接规定：review rubric要求先识别理论、实证、系统或资源等贡献类型；writer禁止凭措辞创造更强贡献。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-paper-reviewer/references/universal-review-rubric.md#L17)
- 反推：不能用顶会算法创新的叙事包装一个未证明首创的整合研究，也不能因为没有首创就否认实证价值。
- 本项目应用：定位为数据整理、动态实力与语境的整合以及共同样本实证比较；不新增“首次”“最优”或外部模型领先主张。 对应修改：E04, E11, E14。

### S3｜方法必须解释操作为何回应困难

- 技能直接规定：storyline要求定义对象/输入输出，解释操作及其信息依据，再在需要的位置给公式；研究工程技能要求机制与实际计算对应。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-paper-writer/references/storyline-blueprint.md#L40)
- 反推：列出Gaussian、Poisson、EP等名称不够。读者应能说明每部分处理什么问题、如何把信息交给下一步。
- 本项目应用：连通不规则比赛、渐变/突变、场地解释、实力不确定性和联合预测；用公式已定义的梯度说明责任权重作用。 对应修改：E05, E06, E07, E09, E15。

### S4｜核心主张必须能回到已有证据

- 技能直接规定：integrity-auditor逐项追溯主张、数字、引用；reviewer要求先重建主张与支持再判断。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-integrity-auditor/SKILL.md#L27)
- 反推：文字不能比表格、推导或实验更强；同一主张在摘要、结果和结论中应有同一证据强度。
- 本项目应用：保留原核心数值和推导；明确实力相关差异较大、语境增量较小，不能由相对损失直接分配信息份额。 对应修改：E01, E07, E10, E11。

### S5｜比较的完整方法、对象和口径必须一致

- 技能直接规定：experiment-designer要求已报告比较核完整配置，并说明数据、指标与实验条件。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-experiment-designer/SKILL.md#L33)
- 反推：比较是否可信，取决于是否在相同目标和可比条件下比较，而不是基线数量。
- 本项目应用：保留21,413场同场比较、各自分母和完整跳变输入；分清“背景模型换成实力模型”与“在实力上增加语境”。 对应修改：E08, E10。

### S6｜不确定性应说清对象与覆盖范围

- 技能直接规定：humanization要求保留相关假设、校准不确定性和技术术语；integrity要求区分不可比较与矛盾。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-humanization/SKILL.md#L25)
- 反推：实力后验、结果随机性和条件比较范围不能混称为“模型有置信度”；限定应解释一个具体推断问题。
- 本项目应用：图中边际均值/标准差不等于完整预测输入；保留混合积分、条件生成器、固定系数范围与实际损失差无相依区间的边界。 对应修改：E07, E09, E13。

### S7｜负结果和开发选择应解释结论怎么来的

- 技能直接规定：writer和humanization要求保留负结果、协议事实及已观察/拟议区别；engineer区分运行失败与科学负结果。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-humanization/SKILL.md#L25)
- 反推：最终版本不是脱离迭代的成功故事。影响选择和适用范围的失败要保留，但不必逐句重复“不能保证”。
- 本项目应用：保留低信息友谊赛偏差、数值近似失败、近年不及固定步长、初始化敏感和历史复用；把重复提醒改为选择风险的具体原因。 对应修改：E05, E12, E13。

### S8｜各章要共同回答同一个问题

- 技能直接规定：writer的整稿检查核摘要与结论是否描述实际工作；storyline按读者理解安排不同章节。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-paper-writer/references/storyline-blueprint.md#L102)
- 反推：一串研究题的流水账不等于完整论证。摘要提出的问题应在方法中落实，在结果中回答，在结论中解释意义。
- 本项目应用：用“历史差异→日期相关实力→相同比赛预测→增量的地区/历史条件→前瞻使用”连接已有五部分结构。 对应修改：E01, E02, E04, E10, E11, E14。

### S9｜实验与检查要最小充分，而非清单越长越好

- 技能直接规定：experiment-designer明确要求能够区分中心假设与合理替代解释的最小充分实验包，不为模板强加实验。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-experiment-designer/SKILL.md#L33)
- 反推：好论文需要能回答问题的证据，不需要为了“显得严谨”不断增加无关消融或重复交叉验证。
- 本项目应用：本轮复用既有数值/模拟/运行结果，不新增模型训练、消融或外部基线；未完成的未来成绩仍未完成。 本项检查后不追加实验。

### S10｜语言应直接表达研究，而不是内部验收或防御

- 技能直接规定：humanization逐句恢复事实与作用，删除没有科学信息的辩护；prose guardrails规定检查器不是词语黑名单。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-humanization/references/humanization-policy.md#L25)
- 反推：正式语言不等于更多抽象名词、否定句或流程术语。限定要改变解释，词语是否保留取决于技术含义。
- 本项目应用：改写配置身份、开发风险与结果意义的衔接，删除重复提醒；将leverage明确为对对数似然梯度的贡献。 对应修改：E06, E08, E12, E13, E15。

### S11｜图表要展示科学对象并与文字同义

- 技能直接规定：visual-composer要求保留值、单位、不确定性、标签与拓扑，并检查实际导出。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-visual-composer/SKILL.md#L33)
- 反推：图形不仅要好看，也要让人知道画了什么、能解释什么；不能把摘要图当完整分布或独立真实实力。
- 本项目应用：7图5表保留原值，强化实力图的阅读方式并指回完整混合分布；未因通用建议重绘已有正确图。 对应修改：E09。

### S12｜交付状态必须以实际产物区分通过/失败/未核查

- 技能直接规定：submission-checker要求读真实构建与PDF，区分passed、failed、not applicable、unverified；common保留原始证据。 [定位](https://github.com/mikubaka88/CCFA-Skills/blob/91ca9e2801698466f934b557a75ce46db8ba46b5/ccf-submission-checker/SKILL.md#L62)
- 反推：论文写好了、编译过了、模型被现实验证了是不同状态。编辑报告必须说明实际做了哪些检查。
- 本项目应用：更新当前源/PDF、差异和记录；保留原版与基线；不把本轮写作核查说成真人复核、完整复现或课程提交完成。 对应修改：E08。

## 4. 修改前，哪些问题真实存在

原稿的数值、主要公式和多数限定已经有记录支持。这一轮的主要问题是表达层次，而不是把此前研究全部判错：

- 中心问题存在，但分散在“历史率”“实力”“背景”等段落，读者容易把整篇理解为多项分析的集合。
- 方法的数学细节较充分，但读者在进入公式前不容易概括各部分为何需要、怎样衔接。
- 对比结果已经正确，但“用实力代替背景”和“在实力上增加背景”的关系还可以说得更准确。
- 若干限定在不同章节重复，末尾又停在“记录与文档齐全”，削弱了对研究发现本身的解释。
- 实力图只画边际摘要，需要更明确地说明联合模型仍使用完整的实力差混合分布。

这些判断先对照了原稿中能够回应疑问的最强段落，因此没有将“说明埋得深”说成“没有推导”，也没有把已有的参数/初始化/地区检查判为不存在。

## 5. 十五项实际修改及理由

### E01｜摘要先提出增量信息问题

位置：`paper/language_revision_20261107/main.tex`，本轮结束时约第55行。对应标准：S1, S4, S8。

修改前节选：Historical home-win rates in international football may reflect team strength, match composition, and venue-related conditions. This study assesses their contribution to pre-match prediction. Comparisons across eras, match types, and regions use…

修改后节选：Historical home-win rates combine differences in team strength, opponent composition, and match context. We assess whether context contributes predictive information after accounting for uncertain pre-match strength. The descriptive analysis use…

修改理由：把研究问题放在办法和数字之前，使所有数字都在回答同一件事，同时保留回顾性评价和未来尚未评价的边界。

### E02｜引言开场聚焦实际研究问题

位置：`paper/language_revision_20261107/sections/introduction.tex`，本轮结束时约第6行。对应标准：S1, S8。

修改前节选：Historical home-win rates in international football are sensitive to the teams, opponents, competitions, and periods included in a sample. A high rate may reflect a strong home team or a relatively weak set of opponents. Comparisons across regio…

修改后节选：A national team's home-win rate depends on its ability, the opponents it faces, and the matches included in the sample. Regional or historical differences can therefore arise from changes in match composition as well as performance. The forecast…

修改理由：将泛泛的开场收束为现有比较真正能回答的问题，不借“研究很少”制造空泛缺口。

### E03｜解释为何需要实力与同场比较

位置：`paper/language_revision_20261107/sections/introduction.tex`，本轮结束时约第8行。对应标准：S1, S3, S5。

修改前节选：Descriptive comparisons identify differences in observed home-win rates; predictive analysis assesses their value for subsequent matches. An aggregate difference may provide little additional information once team strength is included, while agr…

修改后节选：Descriptive rates and rating models address different parts of this question. Rates summarize observed outcomes but do not distinguish a strong home team from favourable opposition. Ratings summarize previous results, but their predictive value …

修改理由：明确历史比例、实力估计和同场预测比较分别解决什么，说明为什么这些步骤需要同时存在。

### E04｜把贡献和主要发现接成研究路径

位置：`paper/language_revision_20261107/sections/introduction.tex`，本轮结束时约第29行。对应标准：S2, S4, S8。

修改前节选：We compare background-only, strength-only, and joint predictions on the same matches, examine historical-window length and regional applicability, and archive a prospective prediction release. In the aggregate probability-score comparison, stren…

修改后节选：The study combines a common cohort for historical comparisons, a model of evolving and uncertain pre-match strength, and chronological evaluation of contextual information. Background-only, strength-only, and joint predictors are compared on ide…

修改理由：先给出相互关联的贡献，再给出发现和使用含义，使三个RQ服务于同一条主线。

### E05｜把时间模型与不规则/突变问题对应

位置：`paper/language_revision_20261107/sections/model_selection.tex`，本轮结束时约第7行。对应标准：S3, S7。

修改前节选：Dynamic paired comparisons~\cite{glickman1999dynamic} distinguish latent ability from uncertainty in its estimation. Gaussian evolution provides a tractable starting point: inactivity increases uncertainty without changing expected strength. A s…

修改后节选：Dynamic paired comparisons~\cite{glickman1999dynamic} distinguish latent ability from uncertainty in its estimation. Gaussian evolution accommodates irregular intervals by increasing uncertainty during inactivity without imposing a decline in ex…

修改理由：把时间模型与不规则赛程、突变风险对应，同时保留平稳模拟中简单模型可能误差更小的负结果。

### E06｜说明TrueSkill/EP能借什么及怎样适配

位置：`paper/language_revision_20261107/sections/model_selection.tex`，本轮结束时约第9行。对应标准：S2, S3, S10。

修改前节选：TrueSkill~\cite{herbrich2006trueskill} incorporates uncertain skill, noisy performance, and a draw region, all relevant to an archive of home wins, draws, and away wins. Its application to game ratings does not establish its validity for nationa…

修改后节选：TrueSkill~\cite{herbrich2006trueskill} represents uncertain skill through noisy performances and a draw region. These concepts suit an archive with home wins, draws, and away wins. National-team application additionally requires explicit time ev…

修改理由：直接解释可借用的构造和国家队场景所需的适配，保留近似推断的性质，减少无对象的自我辩护。

### E07｜补齐从评分到联合预测的关系

位置：`paper/language_revision_20261107/sections/model_selection.tex`，本轮结束时约第15行。对应标准：S3, S4, S6。

修改前节选：The remaining methods address distinct inferential tasks. Direct standardization compares observed rates under a common match composition. Proper scoring rules~\cite{gneiting2007scoring} evaluate probabilities assigned to subsequent outcomes. Si…

修改后节选：The analysis assigns separate roles to match composition, strength, and context. Direct standardization compares historical rates under common compositions. The rating model interprets earlier results using both teams' latent strengths and a sha…

修改理由：用实际依赖关系连接带场地项的评分、排除该项后的实力差分布、语境模型与概率评价，避免只列工具名称。

### E08｜用科学配置说明输入身份

位置：`paper/language_revision_20261107/sections/method.tex`，本轮结束时约第94行。对应标准：S5, S10, S12。

修改前节选：These parameters define the full-jump ratings used in the joint analysis. The archived rating report specifies these parameters. An earlier rule-evaluation exercise used a separate zero-jump special case. Table~\ref{tab:predictive-models} uses t…

修改后节选：The joint analysis uses the full-jump specification recorded in the archived rating report. The zero-jump special case used in an earlier rule-evaluation exercise is a separate reference, rather than the input to Table~\ref{tab:predictive-models…

修改理由：保留完整跳变与零跳变参考版本的关键区别，把内部交接术语改成清楚的配置和输入关系。

### E09｜强化实力图含义并保留完整分布

位置：`paper/language_revision_20261107/sections/strength_development.tex`，本轮结束时约第5行。对应标准：S3, S6, S11。

修改前节选：The strength model was evaluated separately before its inclusion in the joint predictor. Its primary output is a time-indexed distribution of latent ability; true team strength is not observed. Figure~\ref{fig:strength-states} illustrates this o…

修改后节选：The strength model produces a time-indexed distribution of latent ability for each team. Figure~\ref{fig:strength-states} illustrates the output for four teams selected for presentation rather than predictive performance. Each point is a pre-mat…

修改理由：先说明实力图的科学对象，并明确图示边际摘要不是联合预测的完整输入；正式预测继续使用原混合分布。

### E10｜分清两种模型比较及损失分母

位置：`paper/language_revision_20261107/sections/results.tex`，本轮结束时约第74行。对应标准：S4, S5, S8。

修改前节选：Including strength produced the larger reduction in loss (Table~\ref{tab:predictive-models}; Figure~\ref{fig:predictive-models}). Mean log loss declined from $0.671936$ for background alone to $0.566020$ for strength alone and $0.563630$ for the…

修改后节选：The largest loss difference was between context-only and strength-only prediction (Table~\ref{tab:predictive-models}; Figure~\ref{fig:predictive-models}). Mean log loss was $0.671936$ for background alone, $0.566020$ for strength alone, and $0.5…

修改理由：分清从背景单独预测转到实力单独预测，与在实力上增加语境这两种比较，保留所有指标和各自分母。

### E11｜讨论结果怎样回答主课题

位置：`paper/language_revision_20261107/sections/discussion.tex`，本轮结束时约第8行。对应标准：S2, S4, S8。

修改前节选：For RQ2, adding strength to background produced a larger aggregate loss reduction than adding context to strength. The relative reductions have different denominators and cannot be interpreted as additive shares of information or as results for …

修改后节选：For RQ2, the larger reduction in aggregate loss was associated with strength, while context provided a smaller increment. Dynamic paired comparisons~\citep{glickman1999dynamic} convert earlier results into estimates of ability and uncertainty; t…

修改理由：解释模型对比怎样回答最初的主胜率问题；外部排名未比较和分母不可加等事实仍在方法/结果中保留。

### E12｜把开发反馈与选择风险连起来

位置：`paper/language_revision_20261107/sections/discussion.tex`，本轮结束时约第22行。对应标准：S7, S10。

修改前节选：Model revision introduces selection risk. Numerical-reference failures led to a revised integration order, and residual probability bias led to separate shape and drift corrections. These changes brought the system within the documented operatio…

修改后节选：Development results changed both the integration procedure and probability correction: numerical-reference failures prompted a new integration order, and residual bias prompted separate shape and drift corrections. These revisions addressed obse…

修改理由：说明哪些实际缺陷促使方法修订、为什么因此仍有历史选择风险，减少泛化的重复提醒。

### E13｜分清不同检验留下的具体问题

位置：`paper/language_revision_20261107/sections/discussion.tex`，本轮结束时约第24行。对应标准：S6, S7, S10。

修改前节选：Chronological prediction excludes the current result from its own inputs, while development and model selection still reuse the archive. The historical evaluation is therefore not an untouched final test. Simulation results apply to the specifie…

修改后节选：Chronological prediction excludes each match's own outcome from its inputs, but it does not make a reused development archive an untouched final test. Simulation results apply to their specified generators, and no dependence-adjusted interval fr…

修改理由：把按时预测、模拟和固定预测删年/删队检查的限制分别接到其影响的结论，不把它们混成一个“可靠性”。

### E14｜结论回到发现和使用条件

位置：`paper/language_revision_20261107/sections/discussion.tex`，本轮结束时约第40行。对应标准：S1, S2, S8。

修改前节选：Pre-match strength provided the larger reduction in aggregate predictive loss, with a smaller increment from context. Historical-window and regional analyses qualify its application. The archived prospective release permits future evaluation, su…

修改后节选：Within this international-football archive, strength provided the larger reduction in predictive loss, and context supplied a smaller increment whose stability varied across regional checks. Historical-window comparisons favoured cumulative hist…

修改理由：让结论回到实际发现、历史周期/地区条件和预测使用，而不以文档与记录齐全代替科学结论。

### E15｜把笼统影响明确到似然梯度

位置：`paper/language_revision_20261107/sections/method.tex`，本轮结束时约第88行。对应标准：S3, S10。

修改前节选：An outcome very unlikely under a particular state has small responsibility there, reducing its leverage relative to the informative likelihood alone.

修改后节选：An outcome very unlikely under a particular state has small responsibility there, reducing its contribution to the log-likelihood gradient relative to the informative component alone.

修改理由：将责任权重作用从笼统的影响明确为公式中的对数似然梯度；不改变公式或更新算法。

## 6. 没有为了套技能而改什么

- 保留老师要求的五部分结构和全英文交付；没有套用NeurIPS/ICLR模板、匿名制或9页建议。
- 保留原研究问题、模型、参数、训练信息范围和全部科学结果；没有增加模型、训练、消融、交叉验证或未来赛果检验。
- 保留2020—2024不及固定步长基线、初始化敏感、缺层、部分区域变化未获得条件区间、历史复用和前瞻尚未评价等负面或未决事实。
- 没有把0.42%的小幅损失改善包装成统计显著、未来已验证或优于FIFA/Elo；也没有据此否定其作为有限历史证据的价值。
- 保留全部原数学推导；没有把实力分布简化成一个分数或正态标准差。
- 没有因泛化写作规则删除项目实际使用的快照/版本登记。技能反对用校验和装饰论证，但允许真实实现依赖；这些记录也是原有协作和对照要求。
- 原图和表中数据未重画；本轮重点是解释，不把“图更复杂”当作质量提升。

## 7. 检查结果怎样理解

本轮以当前TeX及实际PDF为准检查论证、公式、数字、引用、跨节对应和受影响版面。实际计数、源/PDF指纹与工具结果保存于`ccfa_revision_manifest.json`，不把文件存在当成运行成功。

技能自带的prose checker先后对整稿运行。提示只是候选，不能当作论文分数、语法错误清单或“AI痕迹率”。修改后仍可能提示分号密度：本稿分号包括图注、定义和并列资格条件，不应为了归零批量改掉。责任权重的leverage一词改成了其实际影响的对数似然梯度，依据是公式含义而非黑名单。

完整推导和原负结果已经在正文，模型/模拟和数值核对结果复用已有采用文件。本轮只对改动文本和导出作相应检查，没有以写作审查冒称新实验证据。

## 8. 仍需明确的研究与交付边界

这套标准能改善论文的论证和表达，不能凭修改文字补齐以下证据：

- 小幅语境增益尚无真实相依结构下的损失差区间，也未在新的实际未来比赛中检验。
- 主要性能比较仍针对内部预测器，外部FIFA/Elo或Groll集成方案未实测。
- 模拟条件范围依赖指定生成器；不能据此保证真实足球全过程覆盖。
- 论文适合作为有完整数据和计算链的课程实证研究；本轮没有证明其达到CCF-A方法创新或录用要求。
- 姓名、学号、班级仍按此前要求暂缓；成员独立复现、真实个人贡献确认及最终提交包验收依旧待办。

## 9. 当前文件和对照入口

- 当前源：`main.tex`、`sections/`；当前PDF：`build/main.pdf`。
- 本轮详细说明：`ccfa_revision_report.md`；本轮对照：`ccfa_changes.diff`；当前核查：`ccfa_revision_manifest.json`。
- 从最早保留原稿至当前的累计对照仍为`language_changes.diff`。
- 本轮输入版本在本地`build/ccfa_review/input/`；原始上级`paper/main.tex`、`paper/sections/`、`paper/build/main.pdf`继续保留。
- 技能来源与许可证位于本报告第2节所列固定版本目录；根项目研究日志和材料索引同步更新。

## 10. 最终验证与实际交付状态

- XeLaTeX/BibTeX实际编译退出0；当前23页，7图、5表、12个显示公式、18条文献。TeX日志无Warning、undefined、Overfull或Underfull；编译包装器有Perl locale回退提示，未影响编译。
- 独立版本引用检查实际通过：18条文献、18个引用键、7个TeX文件。
- 与本轮输入逐文件比较：显示公式全文、数字标记、引用顺序、标签和图表标题保持一致；参考文献字节不变。数字标记检查是编辑保护检查，不代替重新计算模型。
- 原版源/PDF/共享图表等18个文件SHA-256全部不变；PDF的29项字体均已嵌入。
- 当前23页均已渲染并通过6张总览逐页检查，未见裁切、重叠或浮动图表打断完整段落。参考文献末页较短是自然延续，不以压缩字号消除。
- 语言检查剩余1类advisory：分号密度；未当作错误、质量分数或AI检测结论。Git差异空白检查通过。
- README、论文入口/框架/图源、材料索引、交接、任务板、pipeline和研究日志同步；未重跑模型、模拟或完整跨机器复现，成员本人尚未独立核验。
