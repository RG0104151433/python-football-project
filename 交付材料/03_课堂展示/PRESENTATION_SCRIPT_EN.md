# V5 presentation script — ten-minute version

这是在原逐页讲稿上直接压缩的版本，仍对应V5的14页。

**【讲述｜读英文】**后的英文引用段落是要说的话；**【操作｜不读】**后的中文只提醒展示者操作。标题、计时、括号中的填数位置和文末问答均不计入正式朗读。第10页两段赛果说明只能选一段。

正文约820个英文词（只读一段赛果说明），另给填入数字预留约25词。按每分钟110词，加上70—90秒点击、停顿和换人，预计约9分钟；若每分钟约100词，则接近9分半至10分钟。各页提示合计9分35秒，留25秒余量。仍须三人合练计时，这不是实际彩排记录。

上台前：打开第1页；恢复动画/步骤到初始位置；如已有可靠比分，先导入CSV并填好第10页。实际赛果尚未提供时，使用“无赛果”备选段，不能临时编数。

## 1 · A prediction saved before the match｜35秒，累计0:35

**【操作｜不读】** 进入第1页，点击“Open the research question”。停一秒，让开场画面出现。

**【讲述｜读英文】**

> Hello everyone. Before a football match, we ask: who will win? Our project asks how past results can help us answer that question, and how sure we should be.
>
> We saved fifty-two Nations League predictions before the matches. Today, we will explain the evidence behind them and show how to check the results.

## 2 · Where our data come from｜35秒，累计1:10

**【操作｜不读】** 进入第2页，依次指向原始数据、实力学习、主胜率比较三个圆环。只悬停一个分区，不逐个介绍。

**【讲述｜读英文】**

> We started with almost fifty thousand international matches. We checked dates, scores, team names, and venues.
>
> About twenty-five thousand matches were used to compare home-win patterns. About thirty-nine thousand helped us estimate strength, including earlier and neutral matches. These samples overlap, so we cannot add them together.

## 3 · Time and match type｜55秒，累计2:05

**【操作｜不读】** 进入第3页，先指蓝色总线，再开启赛事类型对比，指橙色友谊赛与绿色其他比赛；随后指右侧调整前后差值。

**【讲述｜读英文】**

> Home-win rates change over time, but match type also matters. The blue line shows all matches, orange shows friendlies, and green shows other games.
>
> Home teams won less often in friendlies. The overall gap was about three point two five percentage points. It fell to about two point eight eight after we gave both groups the same mix of periods.

**【操作｜不读】** 点击第四问可靠性说明按钮；讲完下一句立即关闭，不朗读整个弹窗。

**【讲述｜读英文】**

> Matches share teams and conditions. We checked uncertainty under stated model assumptions; these patterns do not prove cause and effect.

## 4 · Region and opponent｜50秒，累计2:55

**【操作｜不读】** 进入第4页，将鼠标移到欧洲，展示“Home subregions”；再点“Opponent relationship”。不遍历其他大洲。

**【讲述｜读英文】**

> Geography gives us another view. We compare the home team’s region and the opponents it faces. These are different questions: a region’s win rate also depends on its opponents. A high rate may reflect strong teams, weaker opponents, or home advantage.
>
> Our grouping places Turkey in Southern Europe, Iran in Western Asia, and Australia in Southeastern Asia. The map shows sample results, not a ranking of regions. This is why we next consider strength.

## 5 · What the model needs to consider｜35秒，累计3:30

**【操作｜不读】** 进入第5页。第一张卡片已显示；随着四个关键词依次介绍，点击“Next factor”三次。

**【讲述｜读英文】**

> A useful strength model needs four things: the opponent’s strength, the venue, the importance of the match, and the timing of past results.
>
> It learns from both home and away teams. Friendlies receive less weight. The club pictures illustrate the contrast with national teams; they are not extra data used by our model.

## 6 · What strength means｜55秒，累计4:25

**【操作｜不读】** 进入第6页，点击巴西，播放约两秒后暂停；再点击中国，指实力曲线及误差线。保持年份横轴可见。

**【讲述｜读英文】**

> Our strength value estimates ability before a match. It is neither a world rank nor a predicted score. A higher value means a stronger expected performance against the same opponent under the same conditions.
>
> The line changes as results arrive. The small vertical lines show uncertainty. We predict first, observe the real result, and then update both teams. No match uses its own result to predict itself. One unexpected result need not redefine a team, but repeated surprises may signal a real change.

## 7 · Does strength improve prediction?｜65秒，累计5:30

**【操作｜不读】** 进入第7页，播放约两秒年度曲线后暂停；指右侧三种模型。保持同一种评价指标，不反复切换。

**【讲述｜读英文】**

> We compared three methods on the same historical matches: background only, strength only, and both together. Background includes period, match type, and region.
>
> The combined method reached about seventy percent accuracy for home win versus non-home win, compared with about fifty-eight percent using background alone. Draws count as non-home wins here. Strength provided most of the improvement; background added a smaller gain.
>
> We also checked whether the probabilities matched outcomes over many matches, rather than just counting correct picks. These historical records helped us develop the model, so they are not an untouched final test.

## 8 · How much history should we keep?｜50秒，累计6:20

**【操作｜不读】** 进入第8页，按顺序点亮六个柱子，讲述时完成点击，不等待全部动画结束；指旁边的loss数值。

**【讲述｜读英文】**

> How much history should we keep? Short histories lose useful evidence, while old matches may describe a different team.
>
> We tested six combinations for estimating strength and converting it into a match probability. Lower loss means better probability predictions. The bars are not accuracy percentages. Keeping the full history remained our default, without proving a universally best number of years. Shorter windows could save computing time, but did not clearly improve the overall predictions.

## 9 · The saved forecasts｜55秒，累计7:15

**【操作｜不读】** 进入第9页，悬停一场熟悉的比赛，显示上方大框；切换预测视图，再悬停同一场。不要逐场介绍。

**【讲述｜读英文】**

> Here are our fifty-two saved forecasts. One view shows home-win, draw, and away-win probabilities from the supporting model.
>
> The main model answers the simpler home-win question. Its red point shows the probability; the purple range shows uncertainty from team strength, with other settings fixed. It does not cover every possible error. Three matches are at third-country venues, which our main model does not cover. These probabilities were saved before kick-off and will not change when we enter the results.

## 10 · Checking real results｜55秒，累计8:10

**【操作｜不读】** 上台前导入已核验CSV；台上只进入第10页，选择“Main binary”，指正确、错误和准确率。不要现场导入文件。

**【讲述｜读英文】**

> We judge the main prediction using a fifty percent cutoff. We compare it with the score after ninety minutes, including added time. Unverified matches and cases without a main prediction are excluded.

**【讲述｜有核验赛果时读这一段】**

> We checked [N] matches: [C] correct and [W] wrong, giving [A] percent accuracy. Another [P] fixtures are pending.

**【讲述｜没有核验赛果时改读这一段】**

> Verified scores have not been entered, so we cannot yet give an accuracy figure for these fixtures.

**【操作｜不读】** 以上两段只选一段朗读。有赛果时提前填入N/C/W/A/P；没有赛果就读备选段。保持主模型二分类，不临时切换分母。

**【讲述｜读英文】**

> A few matches cannot prove that a model always works. Wrong predictions are shown too.

## 11 · The research path｜25秒，累计8:35

**【操作｜不读】** 进入第11页，一边说一边连续点“Next step”，让八步依次出现；不逐框朗读。

**【讲述｜读英文】**

> Our workflow connects checked data, historical comparisons, uncertainty tests, strength estimates, and prediction checks. We then examine history length and regional limits before saving new forecasts. Checking actual results stays separate from making those forecasts.

## 12 · Where to find our work｜20秒，累计8:55

**【操作｜不读】** 进入第12页，打开“Repository structure”，停约两秒后返回。不要现场浏览GitHub网页。

**【讲述｜读英文】**

> Our GitHub repository contains the data, code, results, paper, and main decisions. This structure shows where to find them.

## 13 · Three takeaways｜30秒，累计9:25

**【操作｜不读】** 进入第13页，依次指向三个结论，放慢语速收束。

**【讲述｜读英文】**

> Three points to remember.
>
> First, home-win rates reflect both strength and the mix of matches.
>
> Second, strength provides most of the predictive information; context adds a smaller improvement.
>
> Third, history length and region matter, so we should explain uncertainty and the limits of our evidence.

## 14 · Thank you｜10秒，累计9:35

**【操作｜不读】** 进入最后一页，面向观众，不再点击。

**【讲述｜读英文】**

> Thank you for listening. We welcome your questions.

---

## 彩排与时间控制（不朗读）

- 第1—4页：高睿懿；第5—9页：陈正林；第10—14页：江汶谕。沿用已分配的讲解范围；换人时直接接下一页，不再做自我介绍。
- 三人按自己实际语速完整合练一次，计入点击、页面切换、停顿和换人。目标约9分半，留30秒余量。
- 若超时，先少切地图、少播年份、缩短仓库结构停留；不要加速念数字。仍超时可省去第4页三个国家分组的例子，以及第5页关于俱乐部图片的一句。
- 不展示所有球队，不逐场读52个预测，不现场导入文件，不朗读弹窗全部文字。
- 第10页填数后，重新核对主模型二分类的分母：N是已核验且已有主预测的场数，C/W为其中正确/错误，A为页面准确率，P为页面待核验场数。主模型未出值的三场不是错误预测。

## Short answers — only if asked（不计入十分钟）

**Is seventy percent the three-way accuracy?**
No. It is historical accuracy for home win versus non-home win.

**Is the strength value an Elo score?**
No. It is an uncertain estimate on our model’s own shared scale.

**Did you use machine learning?**
Yes. The model learns from earlier results and updates as real outcomes arrive. We did not use a large neural network.

**What does the purple range mean?**
It shows how uncertain team strength affects the home-win probability, with other model settings fixed.
