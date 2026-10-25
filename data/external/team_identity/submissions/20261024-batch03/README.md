# 补证批次 20261024-batch03：第三批强制要求执行结果

执行者：WorkBuddy agent（AI）。批次时间：2026-10-24 23:15—23:50（北京时间）。
依据：交接文档"第三批强制要求"、[第二批审核报告](../../../../outputs/logs/team_identity/batch-review-20261024-batch02/README.md)、研究日志 R20261024-18 至 R20261024-22。原 batch01/batch02 与生产数据未改动。

## 开头必须回答的问题

**1. 8项已知问题是否全部关闭？** 全部按"有据修正或明确撤回"处理，无"只加待核标签"的保留强断言（逐项见下方关闭表）。其中第4项（C006/C014）按规范撤回了不适配的 nonmembership 主张而非改写类型，并提出草案格式扩展建议。

**2. 新增 FIFA 原始依据几份？** **0 份。** 复用 16 份（其中 FIFA 主证据仍仅 2018 年报告 1 份）；本轮新增 7 份全部为线索级（UEFA 黑山官方页、FIFA 旧官网静态快照 5 页、kipdf 官方年报镜像摘要、官方文件门户页）。**"待主线采纳"个案：0 项**——没有任何建议达到"可复核 FIFA 原文支持目标比赛日期"的标准。

**3. 哪些仍只有新闻/年份/推断？** 全部 30 个已处理任务键都仍属此类：member 建议 19 行（152 场去重比赛）依赖同代报道+年份表；unresolved 22 行；conflict 1 行（立陶宛，双边来源已登记）；non_member 建议已全部清零。

**4. 下一步**：主线可先审核本批的**撤回与降级是否恰当**（无需等证据）；取证侧需要线下档案查询（请求草稿见下），公开网络路径已按个案穷尽并记录阻塞。**修订已完成，官方补证未完成。**

## 问题关闭表（8/8）

| # | 旧 ID | 问题 | 本批处理 | 新记录 | 仍缺 |
|---|---|---|---|---|---|
| 1 | AGB2-C015 及 A023–A031 | 1992 推迟 7 国≠1994 报告 7 国 | C015 改 event_date=null/precision=unknown，1994-06-16 降为候选日期写入 statement；A023–A031 逐行重写为"显式跨源推断、无 FIFA 决定记录" | AGB3-C015、AGB3-A023…A031 | 逐国决定原件 |
| 2 | AGB2-A025、AGB2-A027 | reason 称"FIFA decision record" | 重写：明确"尚未取得任何 FIFA 决定记录，仅有跨源推断"；A018–A021/A024/A026/A028–A031 同类措辞一并检查重写 | AGB3-A025、AGB3-A027 等 | 同上 |
| 3 | AGB2-A002/A010/A013/A016/A035/A040 | 批准前即判 non_member | 全部改 unresolved；reason 注明临时会员/先行生效/恢复未被排除；未以首秀或正式赛反推资格 | AGB3-A002/A010/A013/A016/A035/A040 | 临时会籍政策与原件 |
| 4 | AGB2-C006、AGB2-C014 | 申请推迟/被拒≠"该日期无任何会员资格"，且单日事件被扩为状态断言 | 两条 nonmembership 主张撤回（不改塞类型）；事实保留在 AGB3-E011/E006 的 supported_statement 与本 README；建议格式扩展 `application_postponement` | 无替代 claim（撤回） | 格式扩展的主线确认 |
| 5 | AGB2-A018、AGB2-A020 | 引用未登记"更早日期"当 conflict | 改 unresolved/partial；不再声称冲突；如未来取得双方全文再恢复 conflict | AGB3-A018、AGB3-A020 | FIFA 大会原件 |
| 6 | AGB2-E014 及引用 | "将于周四获接纳"是预期非批准 | E014 从 C001 支持证据中移除，定位为计划线索；C001 改为真冲突（31 May vs UEFA 官方页 29 May，双方均已登记保存） | AGB3-C001、AGB3-E017 | 大会决定原件 |
| 7 | AGB2-XR10/XR11 等修订格式 | 逗号拼 ID、"all rows" | 本批 corrections 23 行均为单一 previous_id；全局措辞修订已展开到 18 条受影响建议的替代行；README 统计修订标注文档位置不计入记录 ID | AGB3-XR01…XR23 | — |
| 8 | 旧审核问题回归 | — | validate_delivery.py 断言：无 German-dr 标签、无空 match_ids、东德退出日无假精度、北马其顿仅年份、波罗的海 1991 非 member、数量由文件计算 | 28 项检查 0 失败 | — |

## 官方取证结果与逐案阻塞（真实负结果）

选定个案：黑山（5 场）、南非（7 场，未再扩新证）、波黑（6 场，经旧官网路径）。逐案检索与阻塞：

1. **FIFA 旧版官方 PDF 直链**（`www.fifa.com/mm/document/affederation/administration/2007_fifa_financial_report_en_40741.pdf`，Financial Report 2007）：现返回 HTML 错误页，原件不可得。
2. **Wayback Machine**（该 URL 的存档）：本网络 curl exit 7、平台抓取亦失败——存档路径整体不可达。
3. **FIFA 官方文件门户**（fifa.com/about-fifa/official-documents，已存页面）：自述含"archived financial reports"，但文档列表为客户端渲染，本批无法枚举或下载 1992/1994/2007 年报。
4. **archives.fifa.com**：为视听档案（大会影像等），无会籍文书。
5. **FIFA 旧官网 fifa2.com 静态存活部分**（快照日期 2002-10-17，页脚 FIFA 版权 1994-2002；域名官方性无法从本网络核实，故按规范仅记线索）：可存 6 页；《Report to the 50th/51st Congress》与 1996 年 12 月起的媒体稿存档索引存在，但链接全部指向已死的 runisa.dll CGI（404）——1996 年波黑入会的 FIFA 原生记录路径实测断裂。
6. **kipdf 镜像的 FIFA Financial Report 2006**（提交第 57 届大会的 FIFA 原件镜像）：下载 403；其标题页证实大会日期为 2007-05-30/31（已记摘要级线索 AGB3-E022）。
7. **新登记的有价值线索**：UEFA 黑山官方页记 FIFA 入会"(29 May)" 2007——与 31 May 形成双边已登记的真冲突（AGB3-C001）；FIFA 旧官网快照含 2002-09-11 塔吉克斯坦暂停决定与"mid-2000 共 204 会员"（AGB3-C038，D 类语义观察）。

**档案查询请求草稿**（供本人使用，本批未发任何邮件）：
> 致 FIFA 档案/图书馆：请求 ①48th Congress (Zurich, 3 July 1992) minutes/decisions list 与 admission circulars；②49th Congress (Chicago, 16 June 1994) 同上；③57th Congress (Zurich, 30-31 May 2007) 同上（含 Montenegro admission agenda item 与决定）；④Executive Committee 1979-10-13 决议（China PR readmission）及 1980 年批准文件；⑤FIFA Financial Report 2007（en, 108pp）电子副本。

## 数量统计（由交付文件计算，validate_delivery.py 复算）

| 项 | 数 |
|---|---|
| 任务键/球队 | 148 / 145（覆盖 30 键/27 队） |
| 建议行数 | 42（member 19 / unresolved 22 / conflict 1；**non_member 0**） |
| 有建议去重比赛 | 298（member-only 152、双方建议不同 5 场——均为东德×苏联交叉赛，已单列） |
| 任务状态汇总 | 28 partial、1 conflict（立陶宛）、1 not_found（北马其顿）、118 not_reviewed、**resolved 0** |
| 证据 | 23 条（复用 16、新增 7；fifa_primary 1=复用 2018 报告；full_text_read 19、摘要 4） |
| claims / corrections / search_log | 36（撤回 C006/C014 后 35+新增 1）/ 23 / 4 |
| work_status | revised 15、new_evidence 1（黑山：新冲突证据）、reviewed_no_new_evidence 14、not_reviewed 118 |
| 生产生效规则 | **0 条，等待主线审核** |

说明：黑山任务的建议行均 partial，但 AGB3-C001 的入会日为未消解冲突（29 vs 31 May）；该冲突不影响任何一场目标比赛的相对位置（4 场在两候选日之后、1 场在两候选日之前），故任务状态记 partial 而非 conflict，冲突本身在 claim 层如实登记。沿用的 24 行建议内容与 batch02 逐字一致（脚本受控变换），其 NOTE 限定句即 batch02 XR11 修正后的合规措辞，无需再改。

## 已执行检查（validation_report.json，28 项全过）

五份 JSONL+覆盖表逐行解析（UTF-8/LF）；批次内五类 ID 唯一、AGB3 前缀一致；claims→evidence 及 locator 键闭合；撤回主张（C006/C014）不存在且无引用；42 行建议 match_ids 非空、属对应输入任务、标签与输入一致；8 项问题回归断言（German-dr/空列表/假精度/北马其顿/波罗的海 1991/C015 无日期/批准前 unresolved/修订单一旧 ID）；corrections 23 行旧 ID 均存在于 batch02、替代 ID 均存在于本批；覆盖表 148 行键值对账、覆盖数/剩余数复算一致；本地证据文件 SHA 实算（含复用 16 份）；batch01/batch02 提交文件与两次审核登记指纹逐一比对未变；生产三文件（清洗表、身份表、FIFA 报告）指纹记录在案。

## 未执行/不适用

- 内容与史实复查（日期语义、临时会员含义、来源权威性）为人工/内容审查，不在 validate_delivery.py 范围内——本 README 的关闭表即内容审查记录，由 AI 单方作出，**无人工复核**。
- 未取得任何 FIFA 大会原件；未运行生产构建/发布/重算/pytest；未联系任何外部机构；未验证 kipdf/wayback 之外的镜像完整性。
- 本批未重列全部旧建议以外的新增逐场建议；沿用/替代关系见 task_coverage.csv 的 previous/current 两列与上表。
