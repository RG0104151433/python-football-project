# 补证批次 20261024-batch04：黑山/南非/克罗地亚定向取证结果

执行者：WorkBuddy agent（AI）。批次时间：2026-10-24 23:50—2026-10-25 00:30（北京时间）。
只登记实际新增/修订与必要复用；其余旧成果明确沿用（见 task_coverage.csv）。

## 开头直接回答

**新增可采纳依据：0 份**（无可复核 FIFA 原件；本轮新增 1 份线索级同代报道并已存原文）。**支持的比赛范围（新增/修订建议）**：立陶宛 10 场（冲突消解为两步序列，前 4 场 unresolved/后 6 场 member）、纳米比亚 5 场（新增 member/partial）、开曼群岛 1 场（新增 unresolved/partial）。**验证**：见下"检查"，全部通过。**新批次路径**：`data/external/team_identity/submissions/20261024-batch04/`。

## 三案实际结果

1. **黑山**：**未搜到**任何 inside.fifa.com/fifa.com 官方页（2007 大会决议、通告或官方回顾均未在线出现）；FIFA Financial Report 2007 唯一已知官方直链已死、镜像 403、Wayback 本网络不可达。官方依据缺口不变：入会确日（29 vs 31 May 冲突仍无官方裁决）。新增只有镜像噪音记录（一个 IPFS 维基镜像把 FIFA/UEFA 日期互换、搜狗百科重复 29 May），均已不入证据。
2. **南非**：**未搜到** fifa.com 官方回顾；但新获得第二家同代报道（LA Times 1992-07-04，已存原文）佐证 3 July 1992 国会恢复会籍（报道未给具体日）。7 场目标比赛的建议维持 member/partial，证据面多一家独立同代来源。
3. **克罗地亚**：**未搜到**官方记录；LA Times 列名克罗地亚为 7 月 3 日大会接纳国之一，与既有 UPI+HNS 一致，建议不变（沿用 batch03）。

## 本批真正的新增成果（超出三案）

- **波罗的海两步序列（AGB4-C001）**：LA Times 明确"granted provisional membership in December"——1991 年 12 月临时会员 → 1992-07-03 大会正式接纳。这与 UEFA 的 1991-12-09 和 FIFA 报告的 1992 年不再冲突，而是同一序列的两步。**立陶宛 batch03 的 conflict 建议据此消解**（AGB4-XR01）：前 4 场（1991-12-09 至 1992-07-03 之间的临时窗口内）改 unresolved、留待主线裁决"临时会籍是否满足会员标准"的政策问题；后 6 场 member/partial。拉脱维亚/爱沙尼亚 1991 年场次同样取得该序列说明（保留 unresolved，仅精化局限）。
- **1992-07-03 大会 14 国名单补全（AGB4-C004）**：UPI 未列名的 2 国由 LA Times 补齐为开曼群岛与纳米比亚。
- **纳米比亚（新覆盖任务）**：5 场目标比赛（1992-08-01 至 12-19）全部在入会日之后 → member/partial（AGB4-A003）。
- **开曼群岛（新覆盖任务）**：唯一目标比赛 1992-04-03 在入会日前 → unresolved/partial（AGB4-A004）。

以上全部为线索级（同代通讯社/报纸），**均不满足生产采纳标准**；立场内 policy 问题（临时会籍含义）与 246 场加入前记录无交集，未重裁。

## 检索与读取记录（search_log.jsonl 5 条，区分状态）

- 未搜到（no_result）：黑山官方页 ×1、2007 年通告 ×1。
- 打不开/受限（inaccessible）：Financial Report 2007（死链+Wayback 不可达）×1。
- 有线索（lead_only）：南非官方回顾检索（获 LA Times）×1、克罗地亚/博物馆检索（获同一文）×1。
- 在线全文读取并保存本地：LA Times（sources/latimes_19920704_fifa.html，SHA 实算一致）；UPI 为 batch03 复用。

## 数量与验证

- 任务覆盖表 148 行：本轮 touched 3 键（立陶宛 revised、纳米比亚/开曼 new_evidence），29 键 reviewed_no_new_evidence（沿用 batch03 建议与状态），116 not_reviewed 未变。
- 建议状态汇总：31 partial、1 not_found（北马其顿）、116 not_reviewed、resolved 0、**生产生效规则 0 条**。
- 机器检查（本批内联脚本，等价于前批 validate 流程）：五份 JSONL 解析（UTF-8/LF）、ID 唯一与闭合、corrections 旧 ID 均在 batch03、建议 match_ids 非空且属对应任务、覆盖表 148 行键值对账、本地原文 SHA 实算一致——全部通过；结果即本文件与各 JSONL 内容。
- 未执行：人工/独立复核；FIFA 原件获取；生产构建/重算/pytest。
