# V5 presentation script — shorter classroom version

继续使用V5的14页；本稿直接替换此前约825词的版本。正式朗读552—556词（第10页只选一段）。只读英文引用段落，中文操作、计时和问答都不朗读。第10页两段赛果说明只选一段。

**【讲述｜读英文】** 是说的话；**【操作｜不读】** 是点击提示。按较慢的每分钟90—100词估算，另留90—120秒给操作、停顿和换人。逐页预算合计8分25秒，距离十分钟留1分35秒；这只是计划，尚未实际合练。

上台前：打开第1页，恢复动画初始状态；如已有核验比分，提前导入CSV并填好第10页。不要在台上导入文件。

## 1 · Our question｜30秒，累计0:30

**【操作｜不读】** 点击“Open the research question”，随即开始讲。

**【讲述｜读英文】**

> Hello everyone. Can past football results help us predict the next match? We studied home wins, estimated team strength, and saved fifty-two Nations League forecasts before kick-off. Here is how we did it.

## 2 · The data｜30秒，累计1:00

**【操作｜不读】** 依次指三个圆环；最多悬停一个分区，不逐项读数。

**【讲述｜读英文】**

> We checked almost fifty thousand matches. About twenty-five thousand were used to compare home-win patterns. About thirty-nine thousand helped estimate strength, including earlier and neutral matches. These samples overlap; they are not three separate datasets.

## 3 · Time and match type｜45秒，累计1:45

**【操作｜不读】** 开启赛事类型曲线，指图例与右侧差值；随后打开可靠性说明，讲最后一句后关闭。

**【讲述｜读英文】**

> Home-win rates vary across periods and match types. Friendlies had a lower rate. The gap fell from about three point two five to two point eight eight percentage points after adjusting for the mix of periods.
>
> Our uncertainty checks account for shared teams and conditions under stated assumptions. They do not prove cause and effect.

## 4 · Region and opponent｜40秒，累计2:25

**【操作｜不读】** 只选欧洲；先显示“Home subregions”，再切“Opponent relationship”。

**【讲述｜读英文】**

> We also compared regions. A region’s home-win rate depends on whom its teams play. High rates may reflect stronger teams or weaker opponents, as well as home advantage. This leads to our next question: what changes when we include team strength?

## 5 · Four factors｜30秒，累计2:55

**【操作｜不读】** 第一因素已显示；随讲述点“Next factor”三次。配图仅作解释，不是新增输入。

**【讲述｜读英文】**

> Our model considers the opponent, the venue, match importance, and time between games. Both teams provide learning information, and friendlies receive less weight.

## 6 · What strength means｜50秒，累计3:45

**【操作｜不读】** 点击巴西，播放约两秒后暂停；再点中国，指曲线和误差线。

**【讲述｜读英文】**

> Strength means expected ability before a match, on our model’s shared scale. It is not a world ranking or a score prediction.
>
> We predict first, then use the real result to update both teams. The small vertical lines show uncertainty. One surprising result has limited influence, but repeated surprises can signal a real change.

## 7 · Does it help?｜60秒，累计4:45

**【操作｜不读】** 年度曲线播放两秒后暂停；指右侧三模型，不切换指标。

**【讲述｜读英文】**

> We compared background only, strength only, and both together on the same historical matches.
>
> The combined model reached about seventy percent accuracy, compared with fifty-eight percent for background alone. Here, the target is home win versus non-home win; draws count as non-home wins.
>
> Strength supplied most of the improvement. Context added a small gain. We also checked probability quality. These records were reused during development, so this was not an untouched final test.

## 8 · How much history?｜45秒，累计5:30

**【操作｜不读】** 边讲边点亮六根柱子；不等每段动画结束。指精确loss值，不读全部方案。

**【讲述｜读英文】**

> Short histories lose evidence; very old results may describe a different team. We compared six history settings. Lower loss means better probability predictions; these bars are not accuracy percentages.
>
> We kept the full history as our default. Shorter windows could save computing time, but did not clearly improve overall predictions. We found no universally best number of years.

## 9 · The saved forecasts｜50秒，累计6:20

**【操作｜不读】** 悬停一场熟悉比赛，切换视图，再悬停同一场；只展示这一例。

**【讲述｜读英文】**

> These are our fifty-two saved forecasts. The supporting model gives home, draw, and away probabilities. The main model predicts home win.
>
> Its red point is the probability. The purple range reflects strength uncertainty, with other settings fixed; it does not cover every error. Three third-country-venue matches have no main prediction. Entering results will not change the saved forecasts.

## 10 · Check the results｜45秒，累计7:05

**【操作｜不读】** 保持“Main binary”。有赛果时提前填下面数字；两段只读一段。

**【讲述｜读英文】**

> We use a fifty percent cutoff and compare with the final ninety-minute result, including added time. Only verified matches with a main prediction enter the accuracy calculation.

**【讲述｜有核验赛果时读】**

> Of [N] checked predictions, [C] were correct and [W] were wrong: [A] percent accuracy. Another [P] fixtures remain pending.

**【讲述｜没有核验赛果时改读】**

> Verified scores have not been entered, so we cannot report accuracy for these fixtures yet.

## 11 · The research path｜20秒，累计7:25

**【操作｜不读】** 边说边连续点击“Next step”展示八步；不逐框读。

**【讲述｜读英文】**

> Our path runs from checked data to historical comparisons, uncertainty checks, strength estimates, and prediction tests. Making forecasts and checking results remain separate.

## 12 · The repository｜20秒，累计7:45

**【操作｜不读】** 打开“Repository structure”，两秒后返回；不现场打开GitHub。

**【讲述｜读英文】**

> Our GitHub repository provides the paper, presentation, code, data, results, and decision records.

## 13 · Three takeaways｜30秒，累计8:15

**【操作｜不读】** 指三个结论，放慢语速，不临时补充细节。

**【讲述｜读英文】**

> First, home-win rates depend on both strength and match composition.
>
> Second, strength gives most of the predictive information; context adds a smaller improvement.
>
> Third, predictions need uncertainty estimates and clear limits, not just a winning-team label.

## 14 · Thank you｜10秒，累计8:25

**【操作｜不读】** 面向观众，不再点击。

**【讲述｜读英文】**

> Thank you for listening. We welcome your questions.

---

## 彩排与现场控制（不朗读）

- 高睿懿：第1—4页，2:25；陈正林：第5—9页，3:55；江汶谕：第10—14页，2:05。换人直接接下一页。
- 只操作稿中写出的例子，不遍历地图、球队或52场预测。动画只播两秒。讲述与点击同步，不等动画全部结束。
- 第10页的N是已核验且有主预测的场数；C＋W＝N，A为该分母下的准确率，P是页面待核验场数。三场无主预测不算预测错误。实际填数以页面为准，不预填成绩。
- 先按此稿完整合练，包含操作与换人。若临场落后，跳过第12页结构图动画，只说该页一句话。不要加速读数。
- 各页时间是含操作的预算，不是实测；超时应继续压缩操作停留。英文词数与估时见本次记录，不把十分钟当已验收结论。

## Short answers — only if asked（不计入十分钟）

**Is seventy percent three-way accuracy?**
No. It is historical accuracy for home win versus non-home win.

**Is strength an Elo score?**
No. It is an uncertain estimate on our model’s shared scale.

**Did you use machine learning?**
Yes. The model learns from earlier results and updates after real outcomes arrive.

**What does the purple range mean?**
It propagates strength uncertainty while holding other settings fixed.

**How did you group Turkey, Iran, and Australia?**
Turkey is in Southern Europe, Iran in Western Asia, and Australia in Southeastern Asia under our study rules.

**Did club pictures provide model data?**
No. They illustrate the contrast with national-team football.
