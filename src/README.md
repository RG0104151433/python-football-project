# 代码阅读地图：算法在哪里实现？

要运行某一问，先看[scripts导航](../scripts/README.md)；这里说明内部代码的分工。`src/`中的文件大多由入口调用，不能逐个右键运行。清洗和评分交接等明确提供模块入口的程序，用`python -m src.…`启动，保留包内导入关系。

## 从数据到研究结果

- **基础数据处理：** [snapshot.py](snapshot.py)登记/核对快照，[audit.py](audit.py)列异常，[clean.py](clean.py)清洗，[validate.py](validate.py)核对生成版本；[data_contract.py](data_contract.py)定义共享字段、版本和写出约定。
- **第一问：** [eras](eras/)负责选样本、整数统计、构成调整和导出。[analyze_eras.py](analyze_eras.py)保留早期基线；当前身份确认后的运行由[scripts/analyze_confirmed_eras.py](../scripts/analyze_confirmed_eras.py)调用同一统计实现，必须配当前采用配置。
- **第二问：** [tournaments](tournaments/)负责赛事分层、年代构成比较、滚动窗口及输出。
- **第三问：** [regions](regions/)负责输入/分组、总体和主客组合统计、共同参考与图表。
- **第四问：** [reliability](reliability/)同时包含方法开发和实际应用；`application.py`、`sensitivity.py`、`interpretation.py`、`reporting.py`分别负责采用方法的实际计算、变体、解释和输出。`models.py`等旧路线保留研究过程，不自动等于当前主方法。
- **第五问底层评分：** [strength](strength/)处理胜平负信息、双边实力更新、跳变与不确定性、概率校正和交接。重点阅读`collapsed_jump.py`、`filter.py`、`calibration.py`、`delivery.py`，再结合阶段数学说明；不能仅凭一个文件概括全部模型。
- **第五问含实力分析：** [strength_joint](strength_joint/)负责逐场接口、设计变量、概率积分、拟合、差异与校验；[strength_interpretation.py](strength_interpretation.py)和[strength_predictive_validation.py](strength_predictive_validation.py)分别整理解释与历史预测。
- **第五问可靠性：** [strength_inference](strength_inference/)保留两条路线、模拟世界、目标与比较；根目录的`strength_stage6_*.py`处理登记和敏感性，`strength_inference_numerics.py`及`strength_inference_report.py`补充最终数值重试与限定范围报告。[strength_q5_closeout.py](strength_q5_closeout.py)从已有结果制作图、HTML及论文支撑。
- **第六问：** [history_window](history_window/)把预测规律历史、评分历史、少量组合、有限检查和成本分开处理；统一运行入口在scripts目录。
- **第七问：** [regional_effectiveness.py](regional_effectiveness.py)汇总预测表现，[regional_diagnostics.py](regional_diagnostics.py)解释构成，[regional_stability.py](regional_stability.py)检查有限删除敏感性；读取既有预测，不重新评分。
- **第八问：** [future_predictions.py](future_predictions.py)接入近期真实比赛、续接评分状态并发布赛前预测；运行入口为`scripts/predict_future_matches.py`。
- **共享资料定位：** [artifact_store.py](artifact_store.py)根据已登记位置找到共享原件，保留旧资料指纹的追溯关系。

## 阅读时怎样与结果对照

先从[研究路线](../研究/README.md)确定问题和采用范围，再从[scripts导航](../scripts/README.md)找到入口与配置，最后读入口实际调用的模块。核对论文数字时回到[材料索引](../文档/05_团队协作/论文与汇报支撑材料索引.md)，不要把源码中的默认示例或早期实验当当前结果。

当前源文件可能晚于某次归档执行版本。需要精确复现旧结果时使用该结果绑定的源码快照和协议；当前工作区文件不自动代表所有历史运行的原代码。根目录[AGENTS.md](../AGENTS.md)规定实际修改、失败与采用决定的记录要求。
