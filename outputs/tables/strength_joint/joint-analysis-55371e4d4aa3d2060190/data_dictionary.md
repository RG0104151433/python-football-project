# 第五问第三环节共同分析输出

原24917场，主胜=1、平局/客胜=0，平局保留分母；五地理大区不是六足联。
model_metrics.csv：二元主胜样本内损失/准确率，不能与第二环节三结果损失直接比较；不称未来预测能力。
coefficients.csv及models.json：潜在尺度参数、三初值、秩、梯度和局部曲率；系数不是百分点或因果效应，无未经验证SE。
joint_predictions.csv：一场一行，原标签/地区/信息截止及各模型拟合概率；结果模型使用全期估计，不能当真正赛前预测。
contrasts.csv：32个原CORE目标的映射、两情景概率/百分点差、参考ID与外推诊断。原目录32项中27可算、5缺层；新参考不同，same_estimand_as_old=false。
strength_changes.csv：在同一新参考下无实力/有实力的率差及变化，不称解释比例。
support.csv：每个目标/模型的零单元、稀疏、评分范围外比例；细胞/极值检验不是充分的共同支持证明。
sensitivity.csv：明确记录变更什么、保留什么；初始化仅均值替换不是完整分布敏感性。
validation.json：数值/优化/反馈试算和统计推断分开，区间INFERENCE_NOT_ADMITTED时为空。
display_data.json：同版展示取数，不是最终HTML或论文。
所有CSV为UTF-8 BOM、LF、固定小数，缺项为空；原数据与前三问结果不覆盖。
