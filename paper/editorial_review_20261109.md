# 审稿反馈修改说明（R20261109-02）

执行：Codex（AI），2026-11-09。采用源：paper/language_revision_20261107/main.tex。封面按用户要求保持原样，不翻译睿信班级，不补课程/教师/日期。

## 实际修改

1. 关键词移到abstract环境内，与摘要两侧对齐，分为两行，保留probabilistic prediction整词组，消除孤立断词。
2. tocdepth改为3，三级标题全部显示；Declarations独立为不编号一级节并纳入目录，数据/分工/AI声明不再属于Conclusion。
3. 公式(2)句末改句号；正文所有Equation引用使用eqref带括号。
4. 实力评价表生成器中的正负偏差列全部采用数学模式；修正生成源而非只修改导出的表。表1改紧凑居中，表2缺失区间居中。
5. study_design.tex使用TikZ和统一Stealth箭头，去掉字符拼接箭头；依赖在主文档中登记。
6. 图4—7去掉全图重复suptitle和底部细小说明；保留必要的子图名称、轴名、图例和数据标签，解释统一在原LaTeX图注。图4模型标签改水平分行；图2末年代改完整2020–2024并调整间距；比赛对阵名使用en dash，地区差值标签使用数学减号。
7. URL使用url替代xurl，文献左对齐；链接显示省略https协议前缀并优先独立起行，仅在斜线、连字符和下划线处换行，避免词中、年份中或扩展名中断行。完整https地址仍为可点击目标，Bib文件中的URL不缩写、不改写。
8. 文献Elo统一大小写，FIFA报告去重复年份/冗余来源备注，保留所用页码。作者正文统一favorable/favored/modeled/modeling/center/centered/labeled。被引论文的原题（例如Dixon论文中的Modelling）照录，不为拼写统一篡改原始书目标题。

## 检查与范围

- XeLaTeX/latexmk编译成功；最终日志无Warning/Overfull/Underfull/Missing character。
- 25页：封面1页，摘要i，目录ii，正文及文献1—22；7图5表12显示公式18引用。
- 渲染检查全部25页的版面缩略图，并放大检查图表及最终两页文献；无新裁切、重叠或孤立关键词。
- 引用检查18个条目与18个引用键一致。图表重绘读取原采用结果，不训练/重算科学模型，不改统计结果、概率、数值或研究结论。
- 正式PDF和现有main.pdf副本、Report.pdf、Report.zip（含当前TeX/Bib/共享图）及Code.zip同步，成员校验记录见交付材料/editorial_revision_verification.json。Data.zip和历史存档不覆盖。
- 早期manifest/审核说明是其日期的历史证据；当前入口以final_paper_manifest.json及本说明为准。未获组员独立复核，未上传或发送。
