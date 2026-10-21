# 清洗数据字典

UTF-8 BOM、LF 行尾；每行一场比赛；空字符串表示缺失。原始文件不覆盖。

场地与赛事类别仍需团队核验；自动检查通过不等于全部历史事实正确。

- `match_id`：文本；不允许空值。比赛内容版本 ID，未改原始记录跨快照不变；不是现实比赛永久身份。
- `source_record_id`：文本；不允许空值。文件指纹与数据记录序号，定位该快照内一条输入。
- `row_content_sha256`：文本；不允许空值。
- `source_file`：文本；不允许空值。
- `source_sha256`：文本；不允许空值。
- `source_record_no`：整数；不允许空值。整数，数据记录序号从 1 起，不含表头。
- `date`：文本；不允许空值。
- `date_precision`：文本；不允许空值。
- `home_team_raw`：文本；不允许空值。原始文本值，未按规范名覆盖；可通过来源记录复查。
- `away_team_raw`：文本；不允许空值。原始文本值，未按规范名覆盖；可通过来源记录复查。
- `home_team_id`：文本；不允许空值。
- `away_team_id`：文本；不允许空值。
- `home_team`：文本；不允许空值。
- `away_team`：文本；不允许空值。
- `home_score`：整数；不允许空值。
- `away_score`：整数；不允许空值。
- `outcome`：文本；不允许空值。home / draw / away，含加时不含点球。
- `goal_difference`：整数；不允许空值。整数，第一方比分减第二方比分，不可用于本场赛前预测。
- `result_basis`：文本；不允许空值。固定 after_extra_time_excluding_shootout，不能称为 90 分钟赛果。
- `shootout_status`：文本；不允许空值。matched / no_record / unresolved；no_record 不证明从未有点球。
- `shootout_winner_id`：文本；允许空值。
- `tournament_raw`：文本；允许空值。原始文本值，未按规范名覆盖；可通过来源记录复查。
- `tournament`：文本；允许空值。
- `tournament_group`：文本；不允许空值。friendly / non_friendly / unknown；不代表官方比赛资格。
- `city`：文本；允许空值。
- `country`：文本；允许空值。
- `neutral_raw`：文本；允许空值。原始文本值，未按规范名覆盖；可通过来源记录复查。
- `is_neutral`：布尔；允许空值。可空布尔，true/false/空；空值不得参加场地分析。
- `venue_basis`：文本；不允许空值。
- `year`：整数；不允许空值。
- `decade_start`：整数；不允许空值。
- `time_split`：文本；不允许空值。warmup / train / valid / test，来自配置时间边界。
- `eligible_elo`：布尔；不允许空值。true/false；只有 true 才能进入相应用途，场地分析另筛选非中立场。
- `eligible_venue_analysis`：布尔；不允许空值。true/false；只有 true 才能进入相应用途，场地分析另筛选非中立场。
- `eligible_tournament_analysis`：布尔；不允许空值。true/false；只有 true 才能进入相应用途，场地分析另筛选非中立场。
- `review_status`：文本；不允许空值。clear 表示通过自动规则，不表示逐场人工核验；limited_use 表示用途受限。
