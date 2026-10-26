# M49网页原件与引用说明

这两份HTML是本项目地理分类使用的网页原件，各保留一份。2026-10-26的去重只删除相同内容副本，没有删除这两份原件；不计入GitHub代码语言占比不等于文件不存在。

## 写论文或汇报时怎样注明来源

- United Nations Statistics Division. *Standard country or area codes for statistical use (M49)*. https://unstats.un.org/unsd/methodology/m49/ （访问日期：2026-10-26）。本地原件：[m49_page.html](m49_page.html)。同页FAQ用于解释标准的统计代码及口径。
- United Nations Statistics Division. *M49 overview table (countries or areas)*. https://unstats.un.org/unsd/methodology/m49/overview/ （访问日期：2026-10-26）。本地原件：[m49_overview.html](m49_overview.html)。用于代码与父级地区层级。

访问日期沿用原来源登记，不是本次去重重新下载日期；未核定网页出版日期，不将2026冒称出版年。若学校指定参考文献格式，按其要求排版，上述作者、题名、网址、访问日期仍保留。

可用于方法段的表述：本研究参照联合国统计司M49分类建立球队的地理统计标签，并对历史球队和地区代表队另行记录项目约定；该分类不用于判定国家地位、FIFA会籍或历史球队继承关系。

**不要写成“联合国提供了本项目全部历史球队的官方地理归属”。** 1980—2024使用固定框架是本项目决定；历史实体载体和分段未知的解释见[第三问说明](../../../../研究/03_地域差异/README.md)。

## 原件与修改过程如何核对

[sources.csv](sources.csv)汇总原来源ID、作者、网址、原访问日期、用途、旧路径、当前唯一路径、字节数和SHA；FAQ与完整页面共用同一HTML，不另复制。信息来自已有v3来源清单，没有虚构新的下载或审核。

[relocations.json](relocations.json)保留18个旧路径与共享原件的精确对应；旧包sources.csv、运行manifest及其输入指纹未改写。需要读取旧位置时使用仓库现有artifact_store解析器；手工查阅直接打开本目录两份原件。

全仓当前HTML保留情况与来源关联检查另见[资料核对记录](../../../../outputs/logs/regions/design-review-20261026/review.json)。其中检索缓存、失败响应与正式证据分开登记，不能因为文件扩展名是HTML就当作可引用正文。
