# 英文论文定稿源

**中文** | [English](README.en.md)


这是当前可编辑源：25页、7图、5表、12个显示公式、18条文献。References为第5节，Declarations独立置后；组长已确认邮件和python123均提交。

## 文件与编译

主入口[main.tex](main.tex)，正文在sections/，封面为[cover.tex](cover.tex)，文献为[references.bib](references.bib)。图表共用上一级figures/。正式PDF为[final_paper.pdf](../final_paper.pdf)，指纹见[最终清单](../final_paper_manifest.json)。

封面按用户要求保留“睿信2526班”；封面不编号，摘要/目录i–ii，正文22页。用XeLaTeX和BibTeX编译本目录main.tex，输出至build/；不要把../main.tex当当前稿。与paper父目录一并保留，避免图源路径失效。

引用核查在仓库根目录运行：python paper/check_citations.py --paper-dir paper/language_revision_20261107 --strict。不指定目录时检查旧父目录版本。

## 语言与证据

使用正式学术英文及一致美式拼写，说明实际操作和依据，保留推导、分母、12个公式、引用、真实失败及限制。不把有限检查写成普遍正确，不把拟议改善写成实测收益；语言修改不重训。

旧差异、CCFA及课程核查按各自日期理解，不用旧页数或待提交状态描述当前稿。技能不是CCF-A质量认证，文件存在也不代表成员已独立复核。

## 历史说明

[完整旧README、推导和版本记录](../../文档/04_整理记录/README历史快照_20261112/paper/language_revision_20261107/历史说明.md)按当时日期阅读，不代替当前状态。
