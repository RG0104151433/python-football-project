# 国际足球分析课程项目

我们研究国际男子足球比赛的三个问题：主场表现的年代变化、友谊赛与其他赛事的差异、考虑赛前实力后的主场信号。

## 按什么顺序阅读和操作

**数据清洗 → 数据再次确认 → 第一问 → 第二问 → 两题共同可靠性与后续研究。** [研究流程索引](研究/README.md)和[当前版本登记](研究/pipeline_state.json)统一规定这条逻辑顺序；研究日志仍按实际日期保存，不改写历史。

1. **数据清洗。** 见[数据标准与清洗设计](文档/01_项目方案/前三项研究的数据标准与清洗脚本设计.md)。原始49,945条，保留48,102场、截止日后1,803条、隔离40条；基础清洗版本未变。
2. **数据再次确认。** 见[成员范围确认](研究/00_数据再次确认/README.md)。组长已人工核验并明确采纳117场及其余有效逐场建议。原26,055场候选中，**24,917场纳入、1,138场排除、当前范围待定0场**；采纳决定和逐场变化已保存，不再等待会员补证。
3. **第一问：年代变化。** 见[新版结果](研究/01_年代变化/README.md)。已使用新版样本重算并重复运行核对，92项测试、630项独立复算通过，19份核心表图在两次新版运行中一致。直接主胜率没有单调变化；统一赛事比例后，2010年代、2020—2024相对1980年代分别高0.5019、1.8100个百分点。这是描述结果，正式区间和实力控制仍未开展。
4. **第二问：赛事类型差异。** 见[完整研究逻辑](研究/02_赛事类型差异/README.md)。下一阶段沿用同一24,917场；90个年度×类型单元及36个十年窗口具备输入。仍需确认逻辑和脚本方案，尚未编写第二问程序。
5. **之后。** 两问描述完成后开展[共同可靠性与敏感性分析](文档/05_团队协作/分工与交付/04_两题共同可靠性与敏感性.md)，再进入赛前实力研究；地区差异、历史参考周期、俱乐部迁移仍是备选。

**当前唯一版本入口：** [pipeline_state.json](研究/pipeline_state.json)；[本次运行](outputs/logs/team_identity/confirmed-eras-20261025T013539824757Z-45eb57c2/run_manifest.json)；[独立核查](outputs/logs/team_identity/reviewed-q1-closeout-20261025/independent_audit.json)；[展示取数](outputs/logs/team_identity/reviewed-q1-closeout-20261025/display_data.json)。旧24,279场版和原26,055场基线保留用于追溯，当前数字、参考权重、图全部使用新版，不混用。会员采纳记录只针对本次研究范围，不自动合并历史球队或批准Elo全部早期比赛。

**写论文和做展示找材料：** [论文与汇报支撑材料索引](文档/05_团队协作/论文与汇报支撑材料索引.md)。按步骤只登记现有文件名与路径，不迁移文件；每完成一问或更新样本/结果版本，都须同步索引、阶段README、展示素材、版本登记和研究日志。上传GitHub由组长安排，本轮没有代为提交或推送。

新成员先按[快速上手指南](文档/02_环境配置/克隆仓库后的快速上手.md)创建自己的环境，再按本页顺序操作。成员职责见[分工与交付](文档/05_团队协作/分工与交付/00_先看这里.md)。课程为全组10分钟汇报、所有成员上台；HTML许可尚待老师确认，见[课程要求与展示规范](文档/05_团队协作/汇报要求与HTML方案.md)。

## 协作前必读：持续维护研究记录

本项目统一维护[研究日志与决策记录](文档/01_项目方案/研究日志与决策记录.md)，作为报告、答辩、复现和成员贡献说明的基础。所有成员及协助本项目的 AI，开始任务前应先阅读日志与[仓库协作要求](AGENTS.md)。

**有实质研究进展时及时追加日志，最迟在任务结束、提交或交接前完成。** 应记录研究决策、数据口径/来源变化、重要实现与检查、实验结果及失败、局限和下一步，引用实际证据；按日志模板区分计划与已完成，不改写历史、不虚构数字或复核。原始数据修改明细仍保存在结构化证据和修正记录中。

使用不会自动读取 AGENTS.md 的 AI 工具时，请主动将该文件和研究日志加入上下文，并要求其结束任务前更新。Cursor 的始终适用规则位于 `.cursor/rules/research-log.mdc`。规则、日志与相关工作应一起提交到仓库，队友拉取后才能获得最新版本；记录要求不等于所有工具都能自动执行。

## 文件导航

```text
python-football-project/
├── README.md                         项目导航与常用命令
├── AGENTS.md                         AI 与成员协作、研究日志维护要求
├── .gitattributes                    固定输入/产物字节与源代码行尾
├── config.json                      当前参数和处理政策
├── check_env.py                      环境验收入口
├── requirements.txt                  团队锁定依赖
├── requirements.in                   直接依赖清单
├── 文档/
│   ├── 01_项目方案/                  当前实施路线、研究设计与风险
│   ├── 02_环境配置/                  AI 协作指南、PyCharm 与 VS Code 教程
│   ├── 03_选题存档/                  脑暴、历次推荐与选题比较
│   ├── 04_整理记录/                  文件移动清单与原文件 SHA-256
│   └── 05_团队协作/
│       ├── 分工与交付/               分阶段的 A/B 任务和验收说明
│       └── 交付包/                   历史环境配置分发快照
├── 研究/                            按逻辑顺序阅读，含当前版本登记
│   ├── 00_数据再次确认/              会员准则、六步审查、前后影响和展示素材
│   ├── 01_年代变化/                  第一问及旧基线说明
│   └── 02_赛事类型差异/              第二问规划与共同输入要求
├── scripts/                          盘点、预演、身份包发布与第一题接入入口
├── 参考资料/
│   ├── 课程原始截图/                 课程要求与报告模板的原始照片
│   └── 方法文献/                     引用清单、版本指纹及本地阅读副本
├── config/eras.json                 独立年代分析配置，不改根清洗配置
├── data/raw/international_results/  已有原始比赛数据及来源说明
├── data/processed/                  按版本保存的清洗结果
├── data/external/                   已生成的球队表、赛事分组及后续核验资料
├── src/                             数据准备程序、analyze_eras 入口和 eras 模块
├── tests/                           人工小样例的清洗规则与流程测试
├── notebooks/                       探索分析
├── outputs/
│   ├── environment_check/            本机环境验收，不是研究结果
│   ├── tables/eras/                  按分析身份保存的年代统计与字典
│   ├── figures/eras/                 描述性图与权重敏感性图
│   ├── logs/eras/                    年代分析运行、对账及复现证据
│   └── logs/data_prep/               审计/清洗报告及队友预填表
├── .venv/                            本机虚拟环境
├── .idea/                            PyCharm 项目配置
└── .workbuddy/                       已有工具配置
```

## 从哪里开始

- 看当前研究安排：[前三项研究设计](文档/01_项目方案/前三项研究的数据标准与清洗脚本设计.md)。[早期完整路线](文档/01_项目方案/足球分析项目_实施路线与风险.md)包含已暂缓的扩展，不能全当作当前必交范围。
- 接续当前工作与记录新进展：[研究日志与决策记录](文档/01_项目方案/研究日志与决策记录.md)。
- 实施数据准备：[全流程指南](文档/01_项目方案/数据准备全流程指南.md)、[补充数据获取清单与爬虫需求](文档/01_项目方案/补充数据获取清单与爬虫需求.md)。
- 当前三项研究的字段、脚本与错误处理约定：[数据标准与清洗脚本设计](文档/01_项目方案/前三项研究的数据标准与清洗脚本设计.md)；第 12 节为队友任务，第 13 节为已实现范围与运行结果。
- 新克隆仓库的配置方式：[快速上手指南](文档/02_环境配置/克隆仓库后的快速上手.md)。需要 AI 帮助时再读[AI 协作指南](文档/02_环境配置/队友环境配置_AI协作指南.md)。
- 自己操作 PyCharm：[PyCharm 配置文档](文档/02_环境配置/环境配置_PyCharm.md)。
- 自己操作 VS Code：[VS Code 配置文档](文档/02_环境配置/环境配置_VSCode.md)。
- 历史环境资料：[环境配置交接包](文档/05_团队协作/交付包/足球项目_环境配置交接包.zip)。ZIP 不会随仓库更新；当前以快速上手指南及根目录依赖清单为准。
- 核对课程硬性要求：查看 `参考资料/课程原始截图/`；早期选题打分属于小组评估，不是教师评分标准。

文档现在集中在文档文件夹，解释器、依赖和脚本仍位于项目根目录。教程内涉及的安装、运行命令，都应在根目录执行，不能切换到文档文件夹后运行。

交接包是独立的分发快照，ZIP 内文件采用平铺结构。队友应解压到自己的项目根目录；包内不包含组长的虚拟环境、编辑器配置或本机运行输出。

## 环境与常用命令

本机已验证：Windows、Python 3.14.8（64 位），使用 `.venv`；团队依赖以根目录 requirements.txt 为准。

在项目根目录的 PowerShell 中验证环境：

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe check_env.py
```

新组员创建自己的虚拟环境后安装：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PyCharm 解释器选择自己的根目录 `.venv\Scripts\python.exe`。check_env.py 是环境验收入口；正式清洗使用模块 src.clean，二者不要混淆。

## 数据准备：已有可运行的第一版

### 在 PyCharm 中运行清洗

`src/clean.py` 使用包内导入，不能直接右键作为单独脚本运行。打开“运行 → 编辑配置”，新增或修改 Python 配置：

- 启动类型从“脚本路径（Script path）”切换为“模块名称（Module name）”，填 `src.clean`，不要填文件路径或 `.py`。
- 参数（Parameters）填 `--config config.json`。
- 工作目录（Working directory）选择本仓库根目录，即包含 README.md、config.json 和 src 的目录，不能选 src。
- Python 解释器选择本仓库的 `.venv/Scripts/python.exe`；项目解释器和这条运行配置均要检查，不沿用移动前目录的解释器。
- 保存后选择这条配置运行，不再右键 clean.py 创建直接脚本配置。

第一次可以将参数设为 `--help` 验证入口；看到帮助后改回正式参数。正式启动命令应包含 `-m src.clean --config config.json`。只改工作目录或重新安装依赖不能解决“attempted relative import with no known parent package”。

### 在终端中运行

在项目根目录执行，整个过程不联网、不覆盖原始 CSV：

```powershell
.\.venv\Scripts\python.exe -m src.snapshot --verify --config config.json
.\.venv\Scripts\python.exe -m src.audit --config config.json
.\.venv\Scripts\python.exe -m src.clean --config config.json
.\.venv\Scripts\python.exe -m src.validate --config config.json --data-version prep-3fab808178cf8ad71d88
.\.venv\Scripts\python.exe -m pytest -q
```

`data/raw/manifest.json` 已登记。仅在明确注册新输入时使用 `src.snapshot --register`；已登记文件变化会报错，不会自动重置清单。审计发现关键待核验项时退出码为 1，表示报告已生成，不是程序崩溃。清洗按 config 中 `isolate-v1` 政策隔离这些记录。

2026-10-21 的版本为 `prep-3fab808178cf8ad71d88`：原始 49,945 场，纳入 48,102 场，截止日之后 1,803 场，隔离 40 条候选。数据通过程序校验，仍待团队事实核验，尚未冻结。程序/配置变化会生成新版本；届时验证命令应使用清洗输出实际显示的版本号，不能照抄旧值。

- [清洗数据](data/processed/prep-3fab808178cf8ad71d88/matches_clean.csv)、[字段字典](data/processed/prep-3fab808178cf8ad71d88/data_dictionary.md)、[版本清单](data/processed/prep-3fab808178cf8ad71d88/dataset_manifest.json)。
- [本轮清洗报告](outputs/logs/data_prep/clean-20261021T143720171975Z-7cf580f2/clean_log.md)、[程序验证报告](outputs/logs/data_prep/clean-20261021T143720171975Z-7cf580f2/validation_report.json)。
- [赛事与候选记录预填表](outputs/logs/data_prep/clean-20261023T014412125078Z-82241e6c/team_handoff/A/)、[八场比赛预填表](outputs/logs/data_prep/clean-20261023T014412125078Z-82241e6c/team_handoff/B/)：A/B 是程序早期目录名，不代表最新负责人，以任务清单为准。先复制再填写，程序预填不代表人工核验。

事实修正重放、跨源球队别名及新增比赛尚未实现；这些输入一旦非空会明确报错，不静默跳过。第一版清洗能做格式统一、分类、候选隔离、点球关联与逐行追踪。第一题描述图已实现，Elo、正式区间与第三项实力分析仍未实现。

## 再次确认数据，再运行第一题

本阶段操作无需重新下载资料；先重放人工采用决定或验证当前成员包，再运行第一问。完整含义、采用范围、输出位置及六步审查见[数据再次确认](研究/00_数据再次确认/README.md)。

```powershell
.\.venv\Scripts\python.exe scripts/adopt_membership_reviews.py --config config/membership_review_adoption.json
.\.venv\Scripts\python.exe scripts/analyze_confirmed_eras.py --config config/confirmed_eras_reviewed.json
```

当前研究成员版本 `identity-reviewed-29d880765c1623764940`，第一问 `eras-fifa-dddf11dd6dc0b7531b88`；24,917场、友谊赛共同占比38.5199%。组长已人工采纳本次范围；正式推断和最终冻结尚未完成。

## 复现再次确认前的第一题基线

以下入口刻意保留原26,055场版，供比较和追踪；它不会自动读取新的会员覆盖包，不作为当前确认流程的替代入口。


在仓库根目录、使用自己的虚拟环境运行：

```powershell
.\.venv\Scripts\python.exe -m src.analyze_eras --prep-config config.json --analysis-config config/eras.json --stage all
```

参考分析版本 `eras-7f332ed60ac443228960`，样本为 26,055 场，合并友谊赛占比 38.5339%。结果为探索性描述，输入尚未人工冻结，未计算置信区间。输出在 `outputs/tables/eras/<analysis_id>/`、`outputs/figures/eras/<analysis_id>/` 与控制台显示的 `outputs/logs/eras/<run_id>/`。

PyCharm 改用模块 `src.analyze_eras`，参数与上述命令一致、工作目录为仓库根目录；解释器选项留空。详细验证、文件解释及 A 的手算要求见[本地运行与复现](研究/01_年代变化/本地运行与复现.md)。当前全仓库测试参考为 92 项通过，以本人实际输出为准。

## 后续资料放置规则

- 当前方案放 `文档/01_项目方案/`，不再把新方案混入历史选题资料。
- 环境操作说明放 `文档/02_环境配置/`。
- 课程原始文件放 `参考资料/` 对应子目录。
- 环境交接包放 `文档/05_团队协作/交付包/`，运行生成的图表和结果放 `outputs/`。
- 当前任务集中放 `文档/05_团队协作/分工与交付/`；成员实际提交放 `data/external/review_submissions/A|B/`，不直接改正式数据表。
- 比赛原始数据使用 `data/raw/`，清洗数据使用 `data/processed/`，补充资料使用 `data/external/`，业务模块使用 `src/`；目录骨架已经创建，待实现对应流程。
- 不移动或转发 `.venv`，不为整理资料更改其绝对位置；它与 PyCharm 配置留在根目录。

历史整理曾移动 20 个文件并核对 SHA-256，见[2026-10-20 整理记录](文档/04_整理记录/文件整理记录_2026-10-20.json)。2026-10-23 本轮新增独立任务目录、统一上手入口并补充行尾/缓存规则；不移动 .venv、业务代码或版本化数据，不删除原始资料与运行历史。无实际内容的报告、图表和成员提交文件不提前堆放。
