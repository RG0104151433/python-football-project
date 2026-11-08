# 英文论文定稿源（当前R20261108-08）

**封面定稿R20261108-08：** `main.tex`加载新增`cover.tex`，使用`../figures/bit_school_header.jpeg`（示例中原图）。独立封面无页码，后接摘要i、目录ii与正文1—22，共25页；不要漏传封面源和JPEG。[当前PDF](../final_paper.pdf)、[24页旧版存档](../archive/pre_cover_20261108/README.md)。

**最终稿R20261108-02：** [下载定稿PDF](../final_paper.pdf)，[最终审阅说明](../final_review_20261108.md)，[当前清单](../final_paper_manifest.json)。本目录`main.tex`/`sections/`为定稿源，`build/main.pdf`与交付PDF一致。24页/7图5表/12公式/18引用；姓名学号与责任安排已补，班级已按R20261108-03补为中文“睿信2526班”。本轮差异见`final_changes.diff`；下方CCFA及课程核查均是各自历史时点。 R20261108-04已加入独立Contents页，前置页为i/ii、正文1—22，目录覆盖摘要/一级二级标题/参考文献，正文内容未改。

**当前修订（R20261108-01）：** 以CCFA-Skills固定版本反推12项写作标准，完成15处实质修订；详见[完整修改说明](ccfa_revision_report.md)、[本轮逐行差异](ccfa_changes.diff)、[当前核查清单](ccfa_revision_manifest.json)。当前PDF仍23页、7图5表/12公式/18引用；全部公式、数字、引用及原18项文件指纹保留。技能来源只作写作方法参考，不构成CCF-A质量认证。下方R11及R10说明为历史核查；当前以本轮清单为准，署名和最终提交验收继续后置。

**当前核查（R20261107-11）：** 已对照教师原图88/89/90/92/93号修订新版，当前23页、7图5表/12公式/18引用。补明本项目贡献、计算流程、FIFA/UEFA数据出处与2024集成预测的方法对照，进一步收紧统计措辞。详细判定见[课程要求与语言核查](requirements_language_review.md)，当前指纹见`requirements_language_review.json`。原版不覆盖；R10的revision_manifest.json/content_preservation_checks.json保留历史，不认证当前PDF。姓名/学号/班级按组长安排继续后置，正式提交/实际复现尚待验收。

本目录保存单独的语言修订版，原稿没有覆盖。

- **修订版源文件：** `main.tex`、`sections/`；当前参考文献为`references.bib`（18条；比原版增加3项）。
- **修订版PDF：** `build/main.pdf`（23页）。
- **保留的原版：** 上一级`../main.tex`、`../sections/`及`../build/main.pdf`（22页）。
- **逐行对照：** `language_changes.diff`；`-`为原句，`+`为修改句，也包含独立目录必要的图源相对路径调整。
- **核查记录：** 当前使用`ccfa_revision_manifest.json`及`ccfa_revision_report.md`；R11的`requirements_language_review.md/.json`与R10文件保留历史。原18个源文件/PDF/共享图表的SHA见`original_version_fingerprints.json`。

## 本轮语言标准

沿用课程全英文、写作简洁且避免重复的要求。未指定某一期刊或出版社的语言规范，本轮按正式学术英语处理，不将编辑结果称为官方认证。

1. 用明确的研究对象、操作和结果替代空泛评价，删除模板式过渡与内部汇报口吻。
2. 方法中的已执行操作使用适当过去时，数学关系、图表指向及一般性质使用现在时；保留必要的第一人称表达。
3. 统一实力、背景/语境、概率质量、偏差、条件范围与预测评价的含义。不能将可用、通过有限检查写成普遍正确或优于所有模型。
4. 保留上一轮补全的推导、候选取舍、真实失败和限制；对结尾重复概述和未来展望去冗，不删研究方向或改变其未实施状态。
5. 核对各文件数值、多项比较的分母、全部12个显示公式、引用顺序与标签；语言编辑不重新计算模型。

## 编译与图表

本版复用上一级`../figures/`的原图、流程图与生成表，以免重复复制或改变已有结果。共享文件已经登记SHA，因此本目录须和上级paper目录一并保留。

在LaTeX编辑器中打开本目录`main.tex`，将其设为根文档，使用XeLaTeX + BibTeX；输出到本目录`build/`。不要以原版`../main.tex`为本版的编译入口。当前字号、边距和图注样式与原版相同。

`build/`保存PDF、编译日志和页面检查缓存，不纳入版本管理；提交源文件后可重新编译。PDF已经本地生成并逐页检查；目录存在不代表成员已独立复核。


引用核查在仓库根目录运行：`python paper/check_citations.py --paper-dir paper/language_revision_20261107 --strict`。工具按所选版本检查，避免将原版和新版引用混算；默认不带目录仍检查上级原版15条。
