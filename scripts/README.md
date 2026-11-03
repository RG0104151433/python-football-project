# 脚本导航：这一问应该运行哪个程序？

先按任务找下面的入口，再查看对应研究说明。全部123个现有脚本的中文用途见[完整脚本目录](脚本用途目录.md)；内部算法在哪里实现，见[src阅读地图](../src/README.md)。本次导航只说明既有程序，没有新增研究计算或改动算法。

## 先分清三种操作

- **看结论、写论文：** 打开[研究路线](../研究/README.md)和[材料索引](../文档/05_团队协作/论文与汇报支撑材料索引.md)，直接使用当前采用结果，无需重新计算。
- **复现某一问：** 配好自己的环境，找到本页该问的命令、配置和输入要求，再运行。每个研究阶段有自己的结果目录与版本。
- **核验或重新生成材料：** 使用该问指定的核验/材料脚本。核验程序可能写报告、更新核验记录；材料程序可能重建图表或页面，不能因为名字含audit/build就当成完全只读。

下面命令均在**仓库根目录**运行，使用本机项目解释器。PyCharm运行`src.*`时选择“模块名称”，运行`scripts/*.py`时才选择脚本路径，工作目录都为仓库根目录。环境配置见[快速上手](../文档/02_环境配置/克隆仓库后的快速上手.md)。

当前采用配置以[pipeline_state.json](../研究/pipeline_state.json)及阶段交接为准，不能自动取文件名中版本号最大者。有些程序内部固定配置，有些默认值还是早期版本，下面对此明确说明。

**只在确认程序支持时使用`--help`。** 例如`predict_future_matches.py`直接调用计算，不解析命令行；加上`--help`仍可能开始计算。完整目录标明“本文件有命令行解析”或“无独立帮助，不用--help探测”，后者须先读本页或源文件。

<a id="data"></a>
## 基础清洗：先检查，再生成数据

- 做什么：核对原始文件快照，列出异常，再输出可追踪的清洗版本。
- 配置：[根config.json](../config.json)。输入为[data/raw](../data/raw)及配置登记的补充规则；输出为`data/processed/<data_version>/`，报告在`outputs/logs/data_prep/`等对应运行目录。
- 顺序：快照核对 → 只读审计 → 清洗 → 对生成版本独立验证。

```powershell
.\.venv\Scripts\python.exe -m src.snapshot --verify --config config.json
.\.venv\Scripts\python.exe -m src.audit --config config.json
.\.venv\Scripts\python.exe -m src.clean --config config.json
```

`src.validate`需要`--data-version`，填写清洗程序实际显示的版本；不要将版本占位词原样运行。审计会写报告，发现异常候选不代表环境安装失败。`snapshot --register`会登记快照，日常核对使用`--verify`。

详细说明：[数据标准与清洗设计](../文档/01_项目方案/前三项研究的数据标准与清洗脚本设计.md)。

<a id="identity"></a>
## 数据再次确认：确认研究范围

- 当前入口：[adopt_membership_reviews.py](adopt_membership_reviews.py)，配置[membership_review_adoption.json](../config/membership_review_adoption.json)。它读取已经由组长采纳的逐场判断，发布成员范围覆盖，不是重新调查国家历史。
- 输入：已有清洗版本、身份规则与采纳记录；输出：`data/processed/team_identity/identity-reviewed-*/`及对应日志。
- 核验：[build_team_identity.py](build_team_identity.py)的`--verify`接收实际`identity_manifest.json`。

```powershell
.\.venv\Scripts\python.exe scripts/adopt_membership_reviews.py --config config/membership_review_adoption.json
```

[audit_team_identity.py](audit_team_identity.py)负责原名称盘点，[plan_team_identity.py](plan_team_identity.py)负责规则预演；本轮范围已确认，普通复现第一问不必先重做它们。说明见[数据再次确认](../研究/00_数据再次确认/README.md)。

<a id="q1"></a>
## 第一问：年代变化

- 正式入口：[analyze_confirmed_eras.py](analyze_confirmed_eras.py)。**当前采用配置必须显式填写[confirmed_eras_reviewed.json](../config/confirmed_eras_reviewed.json)**；脚本默认`confirmed_eras.json`仍是早期版本。
- 输入：已验证清洗表、当前身份采纳包和年代分析规则；配置会继续指向其所需文件。
- 输出：`outputs/tables/eras/<analysis_id>/`、`outputs/figures/eras/<analysis_id>/`，运行记录在`outputs/logs/team_identity/`。

```powershell
.\.venv\Scripts\python.exe scripts/analyze_confirmed_eras.py --config config/confirmed_eras_reviewed.json
```

核验入口为[audit_confirmed_eras.py](audit_confirmed_eras.py)，需要明确当前配置、实际运行目录、比较目录和新的报告路径；不能沿用其旧版默认配置。[closeout_reviewed_eras.py](closeout_reviewed_eras.py)整理当前样本采用与展示取数。完整参数按[本地复现说明](../研究/01_年代变化/本地运行与复现.md)执行。

`python -m src.analyze_eras`、[audit_eras_outputs.py](audit_eras_outputs.py)、[prepare_era_display_data.py](prepare_era_display_data.py)保留早期基线用途，其默认结果不是当前24,917场版。

<a id="q2"></a>
## 第二问：赛事类型差异

- 正式入口：[analyze_tournaments.py](analyze_tournaments.py)，配置[tournaments.json](../config/tournaments.json)。
- 输入：清洗表、当前成员范围和第一问登记的共同参考；读取现有资料，不重新清洗或更改第一问。
- 输出：`outputs/tables/tournaments/<analysis_id>/`、`outputs/figures/tournaments/<analysis_id>/`及`outputs/logs/tournaments/<run_id>/`。

```powershell
.\.venv\Scripts\python.exe scripts/analyze_tournaments.py --config config/tournaments.json
```

核验用[audit_tournaments.py](audit_tournaments.py)，必须提供`--run`和新报告路径`--output`，可用`--compare`检查两次运行；主入口的`--verify-run`是核对已有运行，不等于重新估计结果。参数及实例见[本地复现](../研究/02_赛事类型差异/本地运行与复现.md)。

<a id="q3"></a>
## 第三问：地域差异

- 正式入口：[analyze_regions.py](analyze_regions.py)，配置[regions_study.json](../config/regions_study.json)。
- 输入：现有24,917场、已采用分组资料、正式比较清单与项目分类例外。
- 输出：`outputs/tables/regions/<analysis_id>/`、`outputs/figures/regions/<analysis_id>/`及`outputs/logs/regions/<run_id>/`。

```powershell
.\.venv\Scripts\python.exe scripts/analyze_regions.py --config config/regions_study.json
```

独立复算用[verify_region_analysis.py](verify_region_analysis.py)；空格、缺层和稀疏情况用[audit_region_support.py](audit_region_support.py)。两者都要求指定实际运行及报告路径，见[本地复现](../研究/03_地域差异/本地运行与复现.md)。

[prepare_region_mapping.py](prepare_region_mapping.py)、[build_region_roster.py](build_region_roster.py)属于分组准备；[build_region_protocol.py](build_region_protocol.py)生成比较配置，默认输出会指向正式配置。这些步骤已经做过，不是每次计算胜率前都要重做。[deduplicate_m49_sources.py](deduplicate_m49_sources.py)是既有来源去重工具，不属于日常分析。

<a id="q4"></a>
## 第四问：前三问的共同可靠性

- 正式应用入口：[analyze_reliability.py](analyze_reliability.py)，配置[reliability_analysis.json](../config/reliability_analysis.json)，由此绑定已采用的模型、目标和参数尺度。
- 输入：前三问同版设计与分组、已采用方法的验收包；不会因运行此入口就重新开发或挑选模型。
- 输出：`outputs/tables/reliability/applied-*/`、`outputs/figures/reliability/applied-*/`及独立时间戳日志。

```powershell
.\.venv\Scripts\python.exe -m scripts.analyze_reliability --config config/reliability_analysis.json --stage all
```

`--stage check`只做应用输入检查并写检查日志，不产生正式范围；分段运行须用`--run`延续同一运行。核验用[audit_reliability_analysis.py](audit_reliability_analysis.py)，按[实际结果与复现](../研究/04_共同可靠性/第四步_运行结果与复现.md)使用新的运行记录；它拒绝覆盖已有独立核验文件。

[validate_reliability.py](validate_reliability.py)、[refine_reliability.py](refine_reliability.py)、[develop_reliability_joint.py](develop_reliability_joint.py)等属于方法开发与模拟验收。里面既有失败历史，也有采用路线的证据；不是看到第四问就将这些程序全部再运行一遍。复现方法本身时先读[最终模型选择与交接](../研究/04_共同可靠性/第三步_联合模型选择与第四步交接.md)。

<a id="q5"></a>
## 第五问：赛前实力与共同分析

本问包含多种任务，不能用一个“第五问主程序”代替所有环节。依次是已有评分交接 → 含实力共同分析 → 比较解释/预测 → 敏感性与模型条件验收 → 材料。

**评分交接。** `src.strength.delivery`读取已归档的底层评分，内部使用[strength_final_delivery.json](../config/strength_final_delivery.json)和[strength_global_v3.json](../config/strength_global_v3.json)，生成`data/processed/strength/strength-delivery-*/`的赛前特征与校正结果；它不是重新从1950年学习底层评分。

```powershell
.\.venv\Scripts\python.exe -m src.strength.delivery
```

核验和重复交接分别为[audit_final_strength_delivery.py](audit_final_strength_delivery.py)、[repeat_strength_delivery.py](repeat_strength_delivery.py)。如确实要从头复现底层评分，用[replay_archived_jump.py](replay_archived_jump.py)并指定采用版目录；完整条件见[第二环节验收](../研究/05_赛前实力/第二环节_验收与正式交接.md)。这一步可能耗时较长。

**含实力共同分析。** [analyze_strength_joint.py](analyze_strength_joint.py)使用[strength_joint.json](../config/strength_joint.json)，读取已准备的同版逐场资料，结果包输出到`outputs/tables/strength_joint/joint-analysis-*/`；当前指针为[analysis_pointer.json](../outputs/logs/strength_joint/analysis_pointer.json)。

```powershell
.\.venv\Scripts\python.exe scripts/analyze_strength_joint.py --config config/strength_joint.json --stage analysis
```

[audit_strength_joint.py](audit_strength_joint.py)独立复算指定目录；[reproduce_strength_joint.py](reproduce_strength_joint.py)用于专门重复比较。[analyze_strength_interpretation.py](analyze_strength_interpretation.py)整理第四/五环节的对比与解释；[analyze_strength_predictive_validation.py](analyze_strength_predictive_validation.py)重新进行逐年只用过去的历史预测，结果包输出到`outputs/tables/strength_joint/rolling-prediction-*/`，登记在`outputs/logs/strength_inference/prediction_pointer.json`，没有独立`--help`。这些用途不同，运行共同分析并不自动重做全部历史预测与验收。

**敏感性与最终方法验收。** [prepare_strength_stage6.py](prepare_strength_stage6.py)、[analyze_strength_stage6_sensitivity.py](analyze_strength_stage6_sensitivity.py)、[analyze_strength_stage6_paired.py](analyze_strength_stage6_paired.py)分别负责对象登记、评分/样本敏感性、配对变化。[run_strength_inference_final.py](run_strength_inference_final.py)、[confirm_strength_inference.py](confirm_strength_inference.py)、[report_strength_inference.py](report_strength_inference.py)参与最终双路线演算、顺序确认与限定范围应用，属于专门长流程，按[第六环节数学与迭代记录](../研究/05_赛前实力/第六环节_清单评分敏感性与数学方法.md)选阶段，不作为快速上手操作。

**只整理材料。** [build_strength_q5_materials.py](build_strength_q5_materials.py)构建采用结果的图、页面与论文支撑；[audit_strength_q5_final.py](audit_strength_q5_final.py)核对最终交付，[audit_strength_q5_html.py](audit_strength_q5_html.py)检查页面资源/控制。生成材料不等于重新估计模型，静态页面检查也不等于真人投影验收。当前成果统一见[第五问收尾](../研究/05_赛前实力/第五问_收尾与下一问交接.md)。

<a id="q6"></a>
## 第六问：历史参考周期

正式入口统一为[analyze_history_window.py](analyze_history_window.py)，用`--stage`区分任务。不要给不同任务都传同一份配置。

- `outcome`＋[history_window_analysis.json](../config/history_window_analysis.json)：改变总结预测规律的资料长度；输出年度预测、评分与成本表。
- `rating`＋[history_window_rating.json](../config/history_window_rating.json)：重建不同历史范围的球队判断及模拟；这是较长的计算。
- `joint`＋[history_window_joint.json](../config/history_window_joint.json)：组合前两步已有结果，比较少量联合政策。
- `joint-review`＋[history_window_joint_review.json](../config/history_window_joint_review.json)：汇总组合方案的评分与分类成本。
- `reliability`＋[history_window_reliability.json](../config/history_window_reliability.json)：读取已完成预测并作本问规定的有限检查；包含少量评分探针，不是完全只读统计。

例如只复现预测规律资料长度这一层：

```powershell
.\.venv\Scripts\python.exe scripts/analyze_history_window.py --stage outcome --config config/history_window_analysis.json --resume
```

`outcome`、`rating`、`joint`等任务可用其支持的计划模式先列任务；`joint-review`和`reliability`不支持`--plan-only`。完整阶段规则以程序帮助和[第六问收尾](../研究/06_历史参考周期/第六问_研究说明与收尾交接.md)为准，不能把计划输出当结果。

输入为第五问已确认评分、逐场表及本问前序结果。表图在`outputs/tables/history_window/`、`outputs/figures/history_window/`，阶段日志与各`*_pointer.json`在`outputs/logs/history_window/`。

[audit_history_window.py](audit_history_window.py)按`--stage outcome/rating`核对对应结果；默认`pilot`仅指早期可行性。`--refit-examples`会重新计算代表例子。[check_history_window.py](check_history_window.py)也是前三步可行性入口，不是完整第六问。[build_history_window_materials.py](build_history_window_materials.py)只整理已采用材料。

已删除的是完成任务不再读取的中途checkpoint；最终features、状态与失败证据仍保留。重算长任务应按[本次整理记录](../文档/04_整理记录/仓库整理记录_20261103.json)理解缓存与最终产物的区别。

<a id="q7"></a>
## 第七问：地区适用性

三个入口按顺序处理三个不同任务：

```powershell
.\.venv\Scripts\python.exe scripts/analyze_regional_effectiveness.py --config config/regional_effectiveness.json
.\.venv\Scripts\python.exe scripts/analyze_regional_diagnostics.py --config config/regional_effectiveness_diagnostics.json
.\.venv\Scripts\python.exe scripts/analyze_regional_stability.py --config config/regional_effectiveness_stability.json
```

第一项描述各地区预测表现，第二项结合实力/信息构成解释，第三项检查删年删队后的稳定性；读取既有预测与评分，不重新训练实力或共同模型。

核验分别为[audit_regional_effectiveness.py](audit_regional_effectiveness.py)、[audit_regional_diagnostics.py](audit_regional_diagnostics.py)、[audit_regional_stability.py](audit_regional_stability.py)。它们支持`--run-id`，没有填写时会按程序的既定来源取值；复现时建议记录并明确实际ID。

配置、输入和阶段指针分别见[三个配置](../config/)与`outputs/logs/regional_effectiveness/`，各版本表在`outputs/tables/regional_effectiveness/`，正式整理材料从[closeout_pointer.json](../outputs/logs/regional_effectiveness/closeout_pointer.json)取。[build_regional_effectiveness_materials.py](build_regional_effectiveness_materials.py)只包装已有材料；[完整说明](../研究/07_地区有效性/第七问_研究说明与收尾交接.md)保留结论边界。

<a id="q8"></a>
## 第八问：未来比赛预测

- 正式入口：[predict_future_matches.py](predict_future_matches.py)，内部默认读取[future_predictions.json](../config/future_predictions.json)，没有`--config`或独立`--help`参数。
- 输入：该配置绑定的新比赛、赛程、已归档实力状态和历史共同模型资料；不会凭空生成未来赛果。
- 输出：`outputs/tables/future_predictions/<run_id>/`及`outputs/logs/future_predictions/<run_id>/`；[current.json](../outputs/logs/future_predictions/current.json)定位采用预测。

```powershell
.\.venv\Scripts\python.exe scripts/predict_future_matches.py
```

[audit_future_predictions.py](audit_future_predictions.py)独立核算给定`--run-id`，会写核验报告；[build_future_prediction_materials.py](build_future_prediction_materials.py)只从封存结果整理图和讲解材料。本次提交以赛前预测为边界，现有版本不需要因打开仓库就重发。

[evaluate_future_matches.py](evaluate_future_matches.py)是**赛后扩展**：需要真实、已确认的结果文件，经`--results`传入，再按既有封存版本评分；当前没有实际赛后成绩。完整规则见[预测清单与运行说明](../研究/08_未来比赛预测/运行结果与预测清单.md)。

<a id="q9"></a>
## 第九问与可选第十问

[第九问](../研究/09_预测优化展望/README.md)只有方法分析与展望，没有新脚本或计算；第十问实际俱乐部实验未实施。不能从本目录里挑一个旧脚本冒充这两问已有实验。

## 其余脚本为什么保留

完整[脚本用途目录](脚本用途目录.md)将准备、正式分析、核验、复现、材料、方法开发/验收、历史阶段交接和赛后扩展分别标注。历史开发里有真实失败和最终方法的形成证据，不能把“不日常运行”理解成“没用可以删”。

`seal_*`、`sync_*`、`finalize_*`等会封存材料、同步说明或发布决定，不是普通检查命令；应在相应研究/交付流程中使用。普通读者先读当前材料，需复现时再按阶段说明选择。

本次仅核对目录、源文件中的参数与默认配置、文档链接，以及少量明确支持的帮助入口；没有重新计算研究结果。目录会随新增、改名或用途变化同步维护，记录见[代码导航核对](../文档/04_整理记录/代码导航核对_20261103.json)。
