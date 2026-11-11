# 课堂展示：当前V5

当前使用14页V5。论文及材料已由组长确认在两个渠道提交；现在集中准备课堂讲解。真实比分尚未录入，三人实际计时彩排尚未完成。

## 直接用这几份

- [打开展示](index.html)：Chrome或Edge离线打开；同目录保留[结构图](repository_architecture.html)。
- [英文讲稿](PRESENTATION_SCRIPT_EN.md)：本次再压缩为约550词；英文引用块朗读，中文【操作】不读。含操作的计划8:25，留1:35机动，实际时长需合练。
- [赛果接入](RESULTS_DAY_CHECKLIST.md)与[CSV模板](results_template.csv)：展示前准备，不在台上录入；不修改封存预测。
- 本机整套取用：`交付材料/03_课堂展示/`，包含同版HTML、结构图、模板、讲稿与彩排安排。

## 操作与修改

底部Next/Back或左右方向键换页；子图使用页内按钮。正式投影关闭讲者备注；备注也会被投影。地图只切欧洲、实力只选巴西和中国、一场预测展示两种视图即可。

从完整仓库执行`python presentation/build.py`重建采用V5；构建源读取冻结V4并附加V5扩展。只修改讲稿不必重建HTML。`versions/v4_20261110/`继续冻结，`versions/v5_20261110/`保存采用版副本。

当前版本及指纹：[current_version.json](current_version.json)。现有浏览器检查：[V5悬停](v5_verification.json)、[赛果接口](v5_results_handoff_verification.json)。这些是先前运行记录，本轮只改讲稿和入口，未重新执行浏览器检查。

图片与数据来源：[VISUAL_SOURCES.md](VISUAL_SOURCES.md)。当前仓库图是原生SVG；旧Archify成品仅为历史来源。[旧10页讲义](archive/initial_10_screen/handout.pdf)已归档，不能当当前14页备用稿。

旧展示、Archify凭证及配图检索记录已集中到[展示存档](archive/README.md)。新旧路径见[执行记录](../文档/04_整理记录/仓库优化执行记录_20261111.json)。构建和验证脚本保留原路径，数据与正式展示内容不变。

<details>
<summary>历史版本、旧操作与之前的交付说明（按记录日期理解）</summary>

## 当前课堂交付位置（R20261110-07）

**讲稿压缩与提交确认（R20261110-08）：** 组长已确认邮件和python123均完成提交。现有逐页英文稿直接压缩为约820词，中文【操作】与英文朗读引用块分开；14页含操作的计划9分35秒，实际合练仍待进行。三份现有讲稿同步，已准备的三个提交ZIP不重打。

直接使用交付材料/03_课堂展示/index.html及同目录依赖、讲稿与结果模板；邮件附件另在01_邮件附件。重复展示ZIP已清理，V4/V5仓库源目录不变。彩排仍待三人实际进行。

## Git提交与本地缓存（R20261110-06）

V5仍为当前采用版；V4冻结文件、V5构建源、逐页英文稿、素材来源与核验JSON均保留。`_build/`中的旧截图、临时工具副本与虚拟比分导出已清除，原始素材的文字来源记录保留。过时的`versions/v5_20261110.zip`已删除，取用当前展示目录请到本机`交付材料/03_课堂展示/`；Git保留可用的V5目录，不重复收录其ZIP。根目录重复`交付材料.zip`已在R20261110-07清理，忽略规则继续保留。需要重新分享时可在本机打包，勿把大交付ZIP拖入Git提交。

# 当前采用V5，开始英文展示讲稿（R20261110-05）

主入口index.html及versions/v5_20261110/index.html现为采用版V5；V4继续原样冻结保存。python presentation/build.py默认生成并发布V5，不再退回V4。

**讲稿：PRESENTATION_SCRIPT_EN.md** 按14页对应，使用简单直白的英文，附操作提示和常见问答。当前是未计时的初稿，需试讲确认时长。第10页保留N/C/W/A/P可填位置，并提供“已录入核验比分”和“尚无核验比分”两种说法。

**比赛结果：RESULTS_DAY_CHECKLIST.md。** V5导入/二分类和三分类计数、待决排除、CSV导出、刷新保留与原概率不变均已通过临时测试，见v5_results_handoff_verification.json。点击结果格子原先会跳到已删除案例页的位置，本轮已修复为结果页内弹出详情。当前仍未录入真实比分；不要把测试虚拟比分用于汇报。

旧分享ZIP已在R20261110-07清理；当前使用交付材料/03_课堂展示/，历史V4/V5源目录仍在presentation/versions/。

下方为历史说明，之前“V5尚未采用/主入口V4”的状态已被本条取代。

---
# V4固定版与V5试验版（R20261110-04）

- **V4原样保留：** versions/v4_20261110/index.html；manifest.json核对冻结文件的SHA。主入口presentation/index.html也仍是V4内容，没有替换成试验版。
- **V5单独尝试：** versions/v5_20261110/index.html；只有第9页新增悬停放大信息框。复制任一版本时保留同目录repository_architecture.html。results_template.csv也已附带。
- 第9页两种模式都能悬停/键盘聚焦比赛方块，在上方看到队名、主客身份、比赛日期和当前模式的预测。胜平负条的某一段也可单独突出；主模型范围使用放大的红点/紫线，3场withheld不造数值。
- 移出方块区、按Esc或换页隐藏。信息框不拦截鼠标，仍能点击底下比赛或切换模式；日期来自封存记录，记录无具体开球时刻，当前不补造时刻。
- 新代码forecast_hover_v5.js；python presentation/build_v5.py只读冻结V4生成V5，正常V4构建与新版试验分离。node presentation/verify_v5.cjs核验52场×两种模式以及鼠标/键盘、退出、两种投影尺寸；v5_verification.json记录结果。
旧分享ZIP已在R20261110-07清理；当前使用交付材料/03_课堂展示/，历史V4/V5源目录仍在presentation/versions/。

以下说明为先前版本历史。

---
# 图片与目录树更新（R20261110-03）

当前主入口和versions/v3_20261110/index.html均已换入用户附件0.jpg（原字节保存在assets/wembley_user.jpg）。原始网站/许可未提供，不能把它写成公开授权素材。

第12页Repository structure仍用全屏覆盖打开repository_architecture.html，但当前图已重画为原生SVG目录树：8个真实一级目录、24个核对存在的代表子路径，彩色曲线、文件夹图标、可折叠/展开，悬停可查看被缩写的完整路径。不是三个概括文字卡片，也不把目录包含关系称为程序调用。目录不是完整文件清单。

生成源make_repository_visual.py，正常build入口会同步重画。新图是本项目原生SVG，不冒称Archify生成；原Archify成品另存repository_architecture_archify_legacy.html，原凭证archify_receipt_legacy.json只证明当时的旧图。当前检查见repository_visual_verification.json，数据/照片来源见repository_visual_manifest.json和assets/wembley_user_provenance.json。

旧版完整ZIP继续保留，不重写旧存档。以下说明按日期视为历史。

---
# 当前采用：V3细节修订（R20261110-02）

- 新版可单独打开：`versions/v3_20261110/index.html`（旁边保留repository_architecture.html）；主入口index.html同步新版。旧版完整保存为archive/before_final_polish_20261110.zip，SHA见同名JSON，解压到独立文件夹即可使用旧版，未覆盖旧稿。
- 第2页圆环整体放大；第3页图表放大、单位写全percentage points并举例，去除pp缩写。
- 第4页Home subregions按主队研究分区；Opponent relationship按对手为洲外/同洲其他分区/同分区。这是两套不同分组，不要把西欧/西亚等理解为后一视图漏行。亚洲5区、欧洲4区完整。非洲/整个美洲没有对应的独立对手关系汇总，不显示重复按钮；绝不拿只涉及南美的B_SA冒充整个美洲。
- 英国和爱尔兰地图别名补齐，格陵兰按北美洲地图背景着色，不添加不存在的比赛数；三项既定Turkey/Iran/Australia研究覆盖继续保持。
- 第5页增加Previous factor；Venue图片嵌入并实际检查加载，五大联赛logo改为2×3大图组，可点开放大。
- 第8页Previous bar/Restart bars可回退或重置，包括动画播放期间取消计时器。
- 第11页Previous step/Restart flow/Back to opening分别回退步骤、重置第一步、返回开场；8步均有简短英文说明。
- 第12页展示完整仓库名和GitHub链接；Repository structure打开覆盖全屏的结构图页面，有返回按钮与Esc退出。第14页不再显示仓库链接。
- `node presentation/verify.cjs`当前转到verify_final_polish.cjs。实际检查见final_polish_verification.json；旧review/refinement验证记录保留其历史含义。本轮不改变结果录入协议、论文、原科研结果或Report/Code/Data包。

以下旧说明为版本历史。

---
# 11月10日精修版（R20261110-01）

当前14屏：开场封存信封 → 数据圆环 → 年代/赛事＋构成调整看板 → 地图分区/对手组率 → 四项配图因素 → 六国实力播放 → 年度准确率/三模型点图 → 真三维历史长度 → 52场概率/区间 → 赛果接口（本轮不改） → 八步流程 → Archify仓库结构 → 三结论 → Thank you。

- 圆环扩大内径，数字/名称字号不缩小；悬停弧线或键盘聚焦时，外侧和右栏同步显示类别。小扇区可用Tab聚焦。
- 年代曲线配色一一对应图例，横轴有与点位对齐的年代标签；右侧直接差值/年代构成调整看板读取原研究结果。Q4只用一个弹窗按钮，不占常驻内容区。
- 地图按同版study_team_registry分区着色，Turkey欧洲/南欧、Iran西亚、Australia亚洲/东南亚。右侧Home subregions与Opponent setting切换实际组率，显示n；美洲为同一整体研究范围。图示不是地区足球实力排名。
- 因素卡从左到右Next factor依次呈现：对手实力、场地、赛事重视程度、赛程。去掉意外赛果项。图片可点击放大。排名表和赛程为有来源的示意，非新增模型输入；联赛徽标用于对比俱乐部竞赛语境，不把五大联赛称为友谊赛。
- 六国：Brazil、France、Spain、Japan、China、South Africa。按地图或按钮切换，Play播放赛前年度状态；时间轴固定1980–2024并有刻度，缺年不伪造数据；离页停止播放。
- 三模型以紧凑点图呈现已存在的准确率/损失点估计，没有虚构性能置信区间。左边逐年曲线在固定1990–2024轴上增长，不会因新增年份反复挤压。
- 3D图由make_history3d.py使用Matplotlib mplot3d.bar3d实际投影生成60帧，Raise next bar逐根升起、旧柱保留。两条平面轴分别为rating/outcome记忆；竖轴是相对最差候选的损失改善×1000+0.1显示基底，精确loss另列，不误称预测准确率。六组结果未改。
- 52场区间用鲜红点/紫色线画在同一0–100%比例尺；3个主模型withheld保留。三分类概率仍来自辅助分支。
- 流程页Next step逐个点亮8框，含方向箭头。仓库树实际由Archify 3.2生成，按证据/执行/解释交付三组归纳8个真实目录，保留完整独立HTML。当前不是单文件分发：repository_architecture.html须与index.html放同目录，最好复制整个presentation或解压分享ZIP。

入口：index.html。构建：python presentation/build.py；模板review.template.html＋refinement.js；新版数据由build_review.py读取，3D重绘另运行make_history3d.py（不重训）。node presentation/verify.cjs检查新版。review_verification.json为历史版本，本版看refinement_verification.json和archify_receipt.json。

当前4类配图：排名表由Wikipedia的FIFA排名条目摘取（含时间标签）；温布利为实际场馆图片，尚不是专门的英格兰主场助威特写；五大联赛为各条目所载真实徽标组合；单月赛程从曼城赛季条目中提取严格日期匹配的November 2026比赛行。原始来源/图URL保存在assets/factor_sources_verified.json；不把logo或网页截图冒称公共领域素材。仅作具名来源的课程说明，所有权归各自权利人。Sources面板附说明。早先2010训练照已不出现在当前展示顺序中。

结果录入仍按下方CSV说明执行，本轮无真实结果。备用handout.pdf仍为旧版，不作为14屏新版讲义。待组长实际审看及教室计时试放。

---
## 以下为历史版说明

# 11月17日展示修订版（R20261109-03）

直接双击 `index.html`，离线播放。当前12个主屏＋1个可选模型原理附录，全英文，班级按用户要求保留中文。以下旧版说明均为11月8日历史；以本节为准。

## 新版怎么讲、怎么操作

1. 开场不再让观众预测已赛完的比赛：从“11月2日封存的预测能否接受事后核验”引入。
2. 数据页切换三个圆环，分区显示数量和比例。每个圆环有自己的分母，38,919和24,917重叠，不能相加。
3. 年代页点击Add friendly / other，在原折线上叠加友谊赛/其他比赛的逐年代实际胜率；不是复制两种赛事的总体平均值。
4. 地理页鼠标悬停/点击/键盘选择大洲看已规定的对比。前三问的可靠性按钮解释第四问的依赖、条件范围与未能确认的方向，不能说所有结论已被无条件证明。
5. 新增实力模型需考虑的因素页：双方信息、场地、友谊赛、意外赛果/跳变、缺赛与身份。
6. 实力定义举例后，用地图或国家按钮选择巴西、法国、西班牙、日本、尼泊尔、卢森堡。地图不跳走，右侧显示真实赛前均值与±1 SD，横轴按日历年，新增两队来自同版赛前状态文件。
7. 三模型依次出现，前面的柱子不重置。逐年播放的是实际历史准确率，允许波动，不能讲成逐年必然进步。
8. 历史长度用立体风格柱卡，从损失较高依次走向较低；顺序按log loss，不冒称准确率/统计显著性排名。柱高度是0.558以上的放大刻度。默认累计方案不能被讲成所有未来环境的最优年数。
9. 52场集中呈现，可切辅助胜平负概率和主模型的实力不确定性范围。方块是本项目设计，非官方UEFA徽标；国家缩写消除斯洛伐克/斯洛文尼亚等碰撞，悬停和点击看全名。
10. 赛果核验页导入CSV，正确亮绿、错误暗色、待核验保留灰色，统计正确/错误/分母/准确率。主二分类与辅助三分类规则分开。
11. 重点比赛页查看封存概率、导入的实际比分和当前核验规则，默认可选择全部52场，不只挑预测正确的场次。
12. 总结流程、三个主结论和实际GitHub仓库链接。原独立地区适用页省略，材料仍在仓库。
13. 可选附录为“预测→真实赛果→更新”的原理页，最后制作；点击推进图片/文字，不现场重训。

## 11月17日早上怎样录入

打开 `results_template.csv`，一行一个fixture_id。保留所有52行或导入部分行均可；导入视为替换本次整份结果集，未列的场次回到待核验，不做隐式合并。

- `status`：pending / final / postponed / cancelled。
- final必须填写非负整数 `home_score`、`away_score`，以及 `source_url` 和 `checked_at`（建议带时区ISO时间）。只录最终90分钟含补时的比分；不要把尚未踢完、未查证、加时/点球数据填成正式赛果。
- 以UTC/当地实际完赛时间为准。11月17日上午不一定全部结束；未完成不进入分母，不能为了凑52场猜填。
- 在第10屏Import results CSV选择文件，确认状态栏。模板全pending是有效的；当前没有真实赛果，不能报告任何实际准确率。
- 主二分类规则：p≥0.5判主胜，否则平/客胜；3场主模型未出值不进入主模型核验分母。辅助三分类选最大概率，并列按Home/Draw/Away固定顺序。两种准确率分别计算。
- 导入只存在当前浏览器本地，换机器前点Export imported CSV备份，再在教室机器导入。点击导出不会修改封存forecast CSV。失败导入不破坏已有结果。
- 浏览器测试用了临时虚拟比分，已销毁临时上下文；这些不是真实研究数据，未写入结果模板。

## 来源与复现

`python presentation/build.py`（或build_review.py）生成新版；`review.template.html`为当前可编辑模板，`deck.template.html`为历史初版，不能混用。`node presentation/verify.cjs`检查新版：离线、6国、52预测、两种图层、柱状态、结果导入/拒绝等。需本机Playwright/Chrome，仅开发核验需要。

数据见review_manifest.json（包括逐年指标、逐年代赛事率和新增球队的同版状态）；实际浏览器验收见review_verification.json。新地图与照片内嵌在HTML，单独复制HTML即可运行，但CSV模板须另带。原handout.pdf/figure_comparison.html为旧10屏历史材料，本轮未重做，不作为新版备用讲义。

世界轮廓为Natural Earth公共领域1:110m，来自nvkelso/natural-earth-vector；边界仅导航，不作历史身份或研究分组证据。照片为Marcello Casal Jr/Agência Brasil的2010年巴西训练照，CC BY 3.0 BR，来源和授权在Sources面板与VISUAL_SOURCES.md；同一历史照片用于因素、历史长度、可选原理三处，属于示意，不冒充不同年代/球队的实证照片。

旧分享ZIP已在R20261110-07清理；当前使用交付材料/03_课堂展示/，历史V4/V5源目录仍在presentation/versions/。

---
## 以下是历史10屏初版记录

# HTML汇报初版：从这里开始

本版用于讨论展示内容与交互方式，不视为已定稿或已试讲验收。主线为：从一场未来比赛提问 → 清理数据 → 看历史差异 → 估计动态实力 → 同场比较 → 历史周期/地区适用 → 回到赛前预测。

## 直接打开哪些文件

- `index.html`：**主汇报，10屏，全英文，班级保留中文。** 双击用Chrome或Edge打开。所有绘图数据、CSS和脚本都已嵌入，不用启动服务器、不用安装Python/Node、不用联网。单独复制这个HTML也能播放主体交互。
- `figure_comparison.html`：论文原图与新试图左右对照，同样可离线打开。主HTML的Sources面板可链接到它；若需要这个可选入口，应保留整个presentation文件夹。
- `handout.pdf`：10页静态备用讲义，供预习/投影故障备用，不是新论文。
- `SPEAKER_NOTES.md`：英文讲解要点、讲者建议和10分钟时间分配。
- `assets/model_comparison.*`、`assets/strength_trajectories.*`：两组静态试图，每组SVG/PNG/PDF，供后续挑选；当前论文和提交包没有被覆盖。
- `manifest.json`、`verification.json`：实际数据来源/指纹、外部绘图来源和已执行的检查。

旧分享ZIP已在R20261110-07清理；当前使用交付材料/03_课堂展示/，历史V4/V5源目录仍在presentation/versions/。

## 怎样一边讲一边操作

底部Next/Back、键盘左右箭头/空格用于推进；有些屏会先展开本屏内容，再进入下一屏。数字1—9/0可跳到第1—10屏。F切换全屏，若浏览器限制可直接用F11；N开关讲者备注；右上Sources & limits查看来源与适用范围；Print可另存PDF。

**备注显示在同一个页面上，会被投影。** N适合排练或自我审稿；正式讲解时默认关闭。底部计时器只计时，不会自动翻页。离开实力轨迹屏会停止年份播放。默认没有自动动画或自动播放整份汇报；尊重系统减少动态效果的设置。

1. **开场比赛：** 让观众猜英格兰—克罗地亚“主胜”或“平/客胜”；点选只记录本页猜测，不显示或篡改封存概率，第9屏再揭晓。
2. **数据流程：** 点Next逐步显出清洗结果、研究样本及实力学习分支。24,917与38,919重叠，不能相加，也不是依次减少的两级漏斗。
3. **历史描述：** 切Eras/Match types/Geographic contrasts；Show composition adjustment逐步加入构成调整。Eras可选择全刻度或明确标注的放大刻度。10分钟内不建议把所有分支全讲一遍。
4. **模型流程：** Next或点五个阶段，指示点沿“过去→估计→预测→观察→更新”移动。**这是原理示意，不是现场重训。** 用真实观测结果更新后续实力，不把预测标签当真赛果。
5. **实力轨迹：** 选巴西/法国/西班牙/日本，Play years按历史年份逐步画出已存赛前估计，可暂停/拖年份/隐藏SD。没有新增观察的年份不生成虚构状态；线只连接所选日期。
6. **同场三模型：** Add strength/Add context依次出现条形，可Replay；切概率损失/二元准确率。16.12%与0.42%采用不同基准，不能相加。比较图用完整零基线，避免用截断条形夸大改善。
7. **历史长度：** 点六个已运行组合；左图标明放大的损失刻度，右边只引用两项R10同批控制成本，不混合非标准化计时。
8. **地域适用：** 点地区突出相应结果及限制。非洲突出增量对删年/删队的敏感，大洋洲突出148场和缺层；不把损失排名说成地区足球水平排名。
9. **实际预测：** 52场都可选。Show uncertainty逐步展开90%潜在实力范围；Ukraine—Georgia等特殊场地案例明确主模型未出估计。Auxiliary three-way view是独立辅助评分分支，不是假称主模型已经完整胜平负预测。
10. **结尾：** Next逐条揭示三点贡献与后续方向，回到“可追踪的概率判断”。未等到未来赛果，不宣布预测已被实际检验。

## 图片工具究竟怎样用了

截图对应的是 **ChenLiu-1996/figures4papers**，固定commit `b709de17da7e8f9a72e51a5de5bced924a01eeab`。它提供Matplotlib绘图脚本和科学作图指南，不是一个一键网页动画引擎。

本轮按该仓库的字号层级、简洁轴线、配色和矢量导出方式，试作了模型比较和实力轨迹两组图；**实际导入并调用**了其 `figure_ophthal_review/plot_trend.py` 中的 `mark_events`，用我们的真实2010年标记点作注释。上游原脚本、对应指南、完整CC BY-NC 4.0许可、获取URL和SHA已保存于vendor/。

HTML的SVG图形、点击揭示、年份播放、图形过渡和概率范围动画由本项目本地实现，不冒称是上游直接提供的交互功能。仅作课业非商业试作，保留作者/项目/版本/许可及改动归属。

“更好”不等于新的研究性能：新图字体更大、矢量可缩放、对比图零基线、重点和交互更适合讲解；是否比原论文图更适合最终汇报，由你比较后决定。没有生成新显著性、误差条或置信结论；原论文图保留。

## 如何重新生成与核验

完整研究仓库内，使用原Python环境运行 `python presentation/build.py`。它只读取已采用结果并生成展示材料，不重新计算模型；额外引用的dateutil已在团队完整环境中。仅拿汇报ZIP播放不需要这些原始研究文件，但从数据重新构建需要完整仓库。

浏览器开发核验为 `node presentation/verify.cjs`，需已有Playwright及Chrome；本机使用应用自带Node依赖，路径通过PRESENTATION_NODE_MODULES提供，没有把Node或浏览器安装成汇报运行依赖。核验会导出handout.pdf和_build下检查图/记录。

本轮实际：离线浏览器10屏/52赛程交互检查，零JS报错/零HTTP资源请求；1600×900和1366×768无页面溢出；移动端导航可用；新旧图4张均加载；查看全部屏幕总览和打印页。PDF为10页。**尚未在教室投影机上试放，也没有三人计时试讲。**

此前Report/Code/Data三个提交包保持R20261108-06快照；本版不自动混入正式交付，避免讨论稿与论文定稿混淆。

</details>
