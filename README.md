# 国际足球分析课程项目

当前研究方向：国际男子国家队主场表现的年代变化、赛事类型差异，以及考虑赛前 Elo 实力差异后的主场信号。本轮暂不开展修正预测增益的比较；此前完整方案保留为历史与后续扩展参考。

## 协作前必读：持续维护研究记录

本项目统一维护[研究日志与决策记录](文档/01_项目方案/研究日志与决策记录.md)，作为报告、答辩、复现和成员贡献说明的基础。所有成员及协助本项目的 AI，开始任务前应先阅读日志与[仓库协作要求](AGENTS.md)。

**有实质研究进展时及时追加日志，最迟在任务结束、提交或交接前完成。** 应记录研究决策、数据口径/来源变化、重要实现与检查、实验结果及失败、局限和下一步，引用实际证据；按日志模板区分计划与已完成，不改写历史、不虚构数字或复核。原始数据修改明细仍保存在结构化证据和修正记录中。

使用不会自动读取 AGENTS.md 的 AI 工具时，请主动将该文件和研究日志加入上下文，并要求其结束任务前更新。Cursor 的始终适用规则位于 `.cursor/rules/research-log.mdc`。规则、日志与相关工作应一起提交到仓库，队友拉取后才能获得最新版本；记录要求不等于所有工具都能自动执行。

## 文件导航

```text
python项目/
├── README.md                         项目导航与常用命令
├── AGENTS.md                         AI 与成员协作、研究日志维护要求
├── check_env.py                      环境验收入口
├── requirements.txt                  团队锁定依赖
├── requirements.in                   直接依赖清单
├── 文档/
│   ├── 01_项目方案/                  当前实施路线、研究设计与风险
│   ├── 02_环境配置/                  AI 协作指南、PyCharm 与 VS Code 教程
│   ├── 03_选题存档/                  脑暴、历次推荐与选题比较
│   ├── 04_整理记录/                  文件移动清单与原文件 SHA-256
│   └── 05_团队协作/                  环境配置交接包等协作资料
├── 参考资料/
│   └── 课程原始截图/                 课程要求与报告模板的原始照片
├── data/raw/international_results/  已有原始比赛数据及来源说明
├── data/processed/                  按版本保存的清洗结果
├── data/external/                   已生成的球队表、赛事分组及后续核验资料
├── src/                             登记、审计、清洗与验证程序
├── tests/                           人工小样例的清洗规则与流程测试
├── notebooks/                       探索分析
├── outputs/
│   └── environment_check/            CSV、PNG 与本机环境验收报告
├── .venv/                            本机虚拟环境
├── .idea/                            PyCharm 项目配置
└── .workbuddy/                       已有工具配置
```

## 从哪里开始

- 看当前研究与实施安排：[实施路线与风险](文档/01_项目方案/足球分析项目_实施路线与风险.md)。其中早期环境版本建议以环境配置文档和实际已验收的 Python 3.14.8 为准。
- 接续当前工作与记录新进展：[研究日志与决策记录](文档/01_项目方案/研究日志与决策记录.md)。
- 实施数据准备：[全流程指南](文档/01_项目方案/数据准备全流程指南.md)、[补充数据获取清单与爬虫需求](文档/01_项目方案/补充数据获取清单与爬虫需求.md)。
- 当前三项研究的字段、脚本与错误处理约定：[数据标准与清洗脚本设计](文档/01_项目方案/前三项研究的数据标准与清洗脚本设计.md)；第 12 节为队友任务，第 13 节为已实现范围与运行结果。
- 给队友介绍配置方式：[AI 协作指南](文档/02_环境配置/队友环境配置_AI协作指南.md)。
- 自己操作 PyCharm：[PyCharm 配置文档](文档/02_环境配置/环境配置_PyCharm.md)。
- 自己操作 VS Code：[VS Code 配置文档](文档/02_环境配置/环境配置_VSCode.md)。
- 发给队友：[环境配置交接包](文档/05_团队协作/交付包/足球项目_环境配置交接包.zip)。
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

PyCharm 解释器继续选择根目录 `.venv\Scripts\python.exe`，运行入口继续为根目录 check_env.py。环境检查使用人工小数据，不是足球研究结果。

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
- [队友 A 预填表](outputs/logs/data_prep/clean-20261021T143720171975Z-7cf580f2/team_handoff/A/)、[队友 B 预填表](outputs/logs/data_prep/clean-20261021T143720171975Z-7cf580f2/team_handoff/B/)：请先复制到各自提交目录，再填写；程序生成内容不代表已经人工核验。

事实修正重放、跨源球队别名及新增比赛尚未实现；这些输入一旦非空会明确报错，不静默跳过。第一版能做的是格式统一、分类、候选隔离、点球关联与逐行追踪。Elo、图表和第三项实力分析尚未实现。

## 后续资料放置规则

- 当前方案放 `文档/01_项目方案/`，不再把新方案混入历史选题资料。
- 环境操作说明放 `文档/02_环境配置/`。
- 课程原始文件放 `参考资料/` 对应子目录。
- 环境交接包放 `文档/05_团队协作/交付包/`，运行生成的图表和结果放 `outputs/`。
- 比赛原始数据使用 `data/raw/`，清洗数据使用 `data/processed/`，补充资料使用 `data/external/`，业务模块使用 `src/`；目录骨架已经创建，待实现对应流程。
- 不移动或转发 `.venv`，不为整理资料更改其绝对位置；它与 PyCharm 配置留在根目录。

本次整理移动了 20 个文件，原文件内容未改动，移动前后已核对 SHA-256。具体路径映射见 [文件整理记录](文档/04_整理记录/文件整理记录_2026-10-20.json)。
