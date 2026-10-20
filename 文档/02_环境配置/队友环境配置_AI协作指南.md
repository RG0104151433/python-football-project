# 足球分析项目：队友环境配置与 AI 协作指南

版本：2026-10-20。适用 Windows 10/11 的 Intel/AMD 64 位电脑。推荐以 PyCharm 为主，VS Code 也可以。本文同时写给组员和协助配置的 AI。

## 先读这一页

本次任务只配置开发环境，不下载比赛数据、不训练研究模型、不修改足球项目研究方案。

你可以选择：

- **方法 A：对话式 AI 指导。** AI 解释步骤，你自己点击和执行命令。适合 ChatGPT 等不能操作你电脑的聊天工具。
- **方法 B：本地 AI Agent 自动配置。** 能访问项目文件、运行终端命令的 Agent 执行检查与配置。只有聊天能力的 AI 不能使用此方式，即使它声称已经安装也不算成功。

两种方法目标完全相同，不需要都执行。组员可以使用不同编辑器，但必须用本项目自己的虚拟环境和团队统一依赖。

## 一、配置目标：最终应该得到什么

### 必须完成

1. 安装可用的标准 CPython **3.14，64 位**，优先与已验证基线 **3.14.8** 一致。不要安装免费线程构建、嵌入式包或抢先体验版。
2. 在自己选择的项目根目录内创建 `.venv`。项目路径不必与组长相同，不能照抄组长的用户名或解释器路径。
3. 使用发来的 `requirements.txt` 安装团队已锁定依赖，不自行升级或另选版本。
4. `python -m pip check` 通过，没有依赖冲突。
5. 使用提供的 `check_env.py` 完成计算、CSV 读写和出图验收。
6. 在 PyCharm 或 VS Code 内运行同一个脚本，确认编辑器也使用此项目 `.venv`。
7. 保留本机验收记录，向组长说明使用的 Python 版本、编辑器以及检查结果。

### 可选

Notebook/Jupyter 内核配置。只有计划使用 `.ipynb` 才需要；脚本开发不依赖此步骤。

### 无需配置

GPU、CUDA、深度学习框架、数据库、Node.js、Java、远程服务器或网站部署。本阶段不要求注册 GitHub、Kaggle 或其他账号，也不需要购买编辑器功能。

本机已验证基线：Windows、Python 3.14.8（64 位），numpy 2.5.4、pandas 3.0.6、matplotlib 3.11.2、seaborn 0.13.2、scipy 1.18.1、scikit-learn 1.9.1。完整依赖以同包附带的 requirements.txt 为准，而非只安装这里列出的几个库。

如果只能安装其他 3.14 补丁版本，记录差异并运行全部验收；不要宣称与基线完全一致。若是 macOS、Linux 或 Windows ARM 电脑，先告知组长和 AI：本包按 Windows Intel/AMD 基线制作，不能直接套用其路径、二进制依赖或锁文件并保证兼容。

## 二、接收与整理文件

建议组长发送完整的 `足球项目_环境配置交接包.zip`。解压到你自己选择的文件夹，确保不是在压缩包预览窗口内运行。

应能看到：

```text
队友环境配置_AI协作指南.md       本文
requirements.txt               团队锁定依赖，优先使用
requirements.in                依赖用途清单，不用于日常替代锁文件
check_env.py                   验收脚本，必须保留原样
环境配置_PyCharm.md             详细菜单说明
环境配置_VSCode.md              VS Code 详细菜单说明
SHA256SUMS.txt                 原文件哈希，便于确认收到的文件一致
```

包内不会包含 `.venv`、研究数据、账号信息或组长的验收输出。每个人创建自己的 `.venv`。收到更新版本时，以组长明确指定的包为准，不要混用旧脚本和新锁文件。

**只转发本文不能保证自动配置成功。** 对话式 AI 至少应读到本文，并由你保存其余配套文件；本地 Agent 必须能够读取 requirements.txt 和 check_env.py。缺文件时应补齐，不能让 AI 猜测版本或临时伪造验收脚本。

如果你已有足球项目目录，将文件放进该目录；同名文件已存在时先比较，不要直接覆盖自己的改动。其他组员通常建议使用简单路径，例如 `D:\Projects\football-elo`；没有 D 盘就选择 C 盘自己的普通文件夹。无需为了本项目移动组长现有目录，中文路径也可以正常使用。

## 三、方法 A：让对话式 AI 一步步指导

### 1. 把下面这段发给 AI，并附上本文

```text
我要配置一个足球分析 Python 课程项目，请根据附件《队友环境配置_AI协作指南.md》逐步指导我。

请先只确认：我的操作系统、电脑架构、我准备使用 PyCharm 还是 VS Code、项目文件解压到了哪里，以及我是否已经安装 Python。不要一次给出整套长命令。

你不能操作我的电脑，请明确区分“让我执行”和“你已经执行”。每轮只安排一个小阶段（通常 1—3 个命令或几个点击），写清楚在哪里操作、预期看到什么；等待我反馈，再继续。

本项目使用标准 Python 3.14 64 位，优先 3.14.8；项目根目录内 .venv；安装团队 requirements.txt。不要改依赖版本，不要通过改 check_env.py 放宽验收。不要让我删其他 Python、改系统执行策略或用管理员权限反复试错。

完成顺序：确认文件与现有环境 → 缺少时安装 Python → 创建/复用正确 .venv → 安装锁定依赖 → pip check → 运行 check_env.py → 配置编辑器并在编辑器中再次运行 → 汇总完成状态。Notebook 可选。

如果发生错误，先解释错误发生在哪一步，再给最小修复；未通过的步骤不能跳过，也不要因为 pip 显示安装成功就宣布全部完成。
```

不能上传附件时，把本文文本复制给 AI。不要把 requirements.txt 的内容贴进 PowerShell 当命令执行；它是文件，由 pip 读取。

### 2. 你与 AI 配合的规则

- 命令在 PowerShell/编辑器 Terminal 中执行；Python 代码在 `.py` 或指定 Notebook 中执行。不要把 PowerShell 命令粘贴到 `>>>` Python 控制台。
- 复制命令时不要带 `PS C:\...>` 提示符、Markdown 的三个反引号或 AI 的解释文字。
- 如果输出很多，至少提供命令本身、最后约 30 行以及完整错误回溯；单独截取“下载中”不能判断最终成功。
- 遇到与预期不同的输出先反馈，不要连着运行下一阶段。
- 发截图或日志前检查是否包含账号口令、令牌或带认证信息的代理地址；环境配置通常不需要这些信息。

### 3. 标准命令顺序（供你和 AI 对照）

先打开解压后的项目文件夹，在文件资源管理器地址栏输入 `powershell` 回车，即可从该文件夹启动终端；也可通过 IDE 在项目根目录打开 Terminal。

确认位置与配套文件：

```powershell
Get-Location
Test-Path -LiteralPath '.\requirements.txt'
Test-Path -LiteralPath '.\check_env.py'
py -0p
py -3.14 --version
```

两个 Test-Path 应为 True。py 输出 Python 3.14.x 后才进入创建步骤。只有 launcher 不代表安装了 Python。

缺少 Python 时：从 [Python 官方 Windows 下载页](https://www.python.org/downloads/windows/) 找 3.14 系列标准 Windows installer (64-bit)，优先与基线相同版本；保留 pip/launcher，勾选 Add python.exe to PATH。安装后重开终端。不要盲目安装页面顶部的其他大版本；若找不到指定版本，让 AI 核对官方页面并说明差异。

创建前检查：

```powershell
Test-Path -LiteralPath '.\.venv'
```

仅当 False 时执行：

```powershell
py -3.14 -m venv .venv
```

如果 .venv 已存在，先验证下面的解释器。若目录存在但解释器缺失，或版本不符，交给 AI 排查，不在原目录上重复创建，也不要直接删除。

```powershell
.\.venv\Scripts\python.exe -c "import sys, struct; print(sys.executable); print(sys.version); print(struct.calcsize('P') * 8); print(sys.prefix != sys.base_prefix)"
```

应为当前项目的 .venv 路径、3.14.x、64、True。依赖安装：

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe check_env.py
```

逐条执行，每条成功后再下一条。不必激活环境；全程明确使用 .venv 的 python.exe，避免裸 pip 安装到错误环境。

requirements.txt 已由组长锁定。**队友不应按旧文档首次建基线的流程覆盖它。** 如需留存本机包列表，验收通过后另存为：

```powershell
.\.venv\Scripts\python.exe -m pip freeze | Set-Content -LiteralPath local-requirements.txt -Encoding utf8
```

### 4. PyCharm 最后怎么配

1. 用 Open 打开项目根文件夹。
2. 若自动选对解释器，无需重新设置；直接运行脚本验收即可。
3. 若不正确：Ctrl+Alt+S → 搜索 Python Interpreter → Add Interpreter / Add Local → 选择已有环境 → 选本项目 `.venv\Scripts\python.exe`。
4. 在左侧打开 check_env.py，右键 Run 'check_env'。
5. 输出正确路径和 ENVIRONMENT CHECK PASSED、退出码 0，即编辑器验收通过。
6. 若有运行配置，工作目录设为项目根目录，不要选择其他项目的解释器。

更详细菜单见同包的《环境配置_PyCharm.md》。那份文档包含组长早期安装过程；**队友安装依赖以本文的 requirements.txt 流程为准**。

VS Code 用户：打开项目文件夹，安装 Microsoft Python 扩展，Ctrl+Shift+P → Python: Select Interpreter → 本项目 `.venv\Scripts\python.exe`；运行 check_env.py 时使用 Run Python File in Terminal。不要假设 `code` 命令一定属于 VS Code；组长电脑上它曾指向 Qoder。

## 四、方法 B：将文件交给本地 AI Agent 自动配置

### 1. 使用前的准备

将交接包解压到独立项目目录，在 Agent 中打开该目录。确认它具备本地文件读取和终端执行能力；如果没有 GUI 能力，安装器交互和编辑器点击由你完成。无需把整个桌面或个人文件目录开放给它。

### 2. 将下面的任务原样发给 Agent

```text
请在当前足球项目目录中完成开发环境配置，先读取《队友环境配置_AI协作指南.md》、requirements.txt、requirements.in 和 check_env.py，按其中“方法 B”执行，而不是只输出配置建议。

目标：标准 CPython 3.14 64 位（优先 3.14.8），项目目录内 .venv，按团队 requirements.txt 安装，pip check 与 check_env.py 通过，再核对 PyCharm（优先）或用户现有 VS Code 的解释器。

先用只读检查识别系统/架构、项目绝对路径、文件完整性、已有 Python、现有 .venv 和编辑器。不要照抄组长的 C:\Users\EasonG 路径。当前文件夹若不是明确的项目根目录，先问我位置。非 Windows Intel/AMD 环境先说明与基线差异，不要直接执行 Windows 命令。

我授权你在本项目目录内创建虚拟环境、安装锁定依赖、执行验收、保存本机配置记录，以及新增必要的项目级编辑器配置。系统软件缺失时可准备官方安装方案，并按工具权限正常申请安装；已有合适版本则复用，不需要重复安装。不得删除/重建已存在环境、卸载软件、改全局系统策略或覆盖团队文件。遇到损坏/版本错误的旧环境，先给出其路径和修复方案再问我。

请按只读审计 → 缺少的前置软件 → .venv → 锁定依赖 → 检查 → 编辑器绑定 → 汇总推进。每阶段检查退出码，失败时停止依赖该结果的后续操作，诊断后最小修复。不得为通过检查修改 check_env.py、requirements.txt，也不得用 requirements.in 替代锁文件安装。不要开展足球数据采集或研究代码开发。

保留配置日志及本机验收记录，最终区分“终端验收通过”“编辑器验收通过”“Notebook 可选/未做”。有权限或工具限制请明确告诉我需要执行的具体动作，不得声称完成未实际执行的步骤。
```

### 3. Agent 的执行规范

**A. 审计与防覆盖**

- 确认当前项目路径和交接包文件；可用 SHA256SUMS.txt 核对团队文件。
- 识别系统架构、可用解释器的实际位置、版本、位数；不要只看命令名称。WindowsApps 入口与 launcher 本身不是已验证的运行时。
- 检查 .venv 目录是否存在以及实际版本、sys.prefix、sys.base_prefix。已经正确的环境可复用；部分创建或不匹配的环境不能直接覆盖。
- 不修改/卸载其他项目环境，不全局安装项目依赖，不开启 inherit global site-packages，不更改全局 PowerShell 执行策略，不为下载关闭证书校验。

**B. 前置软件与安装**

- 对软件版本、官方安装方式存在不确定性时查询官方说明；不猜 winget 包 ID，不从第三方下载站取安装器。
- 优先已有标准 Python 3.14；若缺失，使用官方安装器/已核实官方安装渠道，按工具权限处理安装。需要用户确认 UAC 或完成安装器点击时给出具体动作。
- 不需要管理员权限就按当前用户安装。不要为了静默安装扩大到系统级修改。
- 终端 PATH 尚未刷新时，可用实际发现的 Python 完整路径创建 .venv；不要依赖未经确认的默认路径。
- 安装包下载失败时保留错误；检查网络/代理/证书后重试，未经协调不换依赖版本、不追加来源不明镜像。

**C. 项目环境与依赖**

- 仅在不存在 .venv 时创建。之后始终使用它的 python.exe -m pip。
- 执行 requirements.txt 安装；每步核对实际退出码。不执行“安装失败也继续”的无条件命令链。
- 不覆盖 requirements.txt 或生成新的团队锁文件；本机 freeze 只能保存为 local-requirements.txt。
- 缺少锁文件或验收脚本时报告缺失并让用户补齐；不得自行编造一套等价文件。

**D. 验收与编辑器**

- pip check 成功后运行 check_env.py，确认退出码为 0 和 ENVIRONMENT CHECK PASSED；检查输出 JSON、CSV 和 PNG。具备图像查看能力时查看 PNG，否则请用户查看，不得声称已经目视验证。
- 不修改检查标准来适应错误版本或错误路径。验收使用人工小数据，不代表足球项目实验已经完成。
- 编辑器已有正确解释器时不需要重复配置。能操作 PyCharm UI 才设置并在 IDE 中真实运行；无 GUI 能力时明确保留人工步骤。
- VS Code 如需 .vscode/settings.json，先读取并合并已有字段；不要覆盖用户配置。defaultInterpreterPath 只是默认提示，不能单独证明编辑器已选对。PyCharm 不通过盲改 .idea 文件冒充解释器绑定。
- Notebook 只有用户要用时配置；不能因终端脚本通过就声称 Notebook 内核也已验收。

**E. 日志与最终交付**

在项目内保存 outputs/environment_setup/setup_summary.md（或等效说明），记录实际执行时间、系统、Python 完整路径与版本、安装来源/复用情况、依赖安装与 pip check 退出码、脚本验收结果、编辑器是否真实运行、未完成事项。验收脚本自己的 JSON 保留原样。

不要保存代理密码、令牌、完整无关环境变量或浏览器账号信息。日志中本机路径正常保留，发给组长前可遮住个人用户名，但不要改原始验收文件。

若发生权限限制，正常请求该具体操作所需权限；未获批准不能绕过，也不能将未执行安装记为完成。每个阻塞点给用户一个可以执行的下一步，不循环尝试破坏性修复。

## 五、怎样认定“真的完成了”

### 第一层：终端环境通过

- pip check 显示 No broken requirements found，退出码 0。
- check_env.py 显示 Python 3.14.x、64 位，以及当前项目 `.venv` 的真实路径。
- 最后显示 ENVIRONMENT CHECK PASSED，退出码 0。
- outputs/environment_check 内存在 synthetic_matches.csv、environment_check.png、environment_report.json，PNG 能正常打开。

### 第二层：编辑器通过

在 PyCharm 或 VS Code 中实际运行同一个脚本，再次通过，解释器路径一致。**这层完成后，才可称为该组员开发环境配置完成。** PyCharm 自动选中正确环境也算完成，不必强行重新设置菜单。

### 第三层：Notebook 通过（可选）

如果使用 Notebook，运行：

```python
import sys
print(sys.executable)
import pandas as pd
print(pd.__version__)
```

路径应指向同一个项目 .venv。IDE 内置 Notebook 功能不可用时，可以在项目终端用 `.\.venv\Scripts\python.exe -m jupyterlab` 启动浏览器入口；不必为了 Notebook 购买功能。

### 给组长的完成回执

复制下面模板，填真实结果即可：

```text
姓名：
系统/架构：
Python 具体版本与位数：
编辑器与版本：
是否按团队 requirements.txt 安装：
pip check：通过 / 未通过
check_env.py 终端运行：通过 / 未通过
check_env.py 编辑器运行：通过 / 未通过
PNG 打开检查：正常 / 异常
Notebook：未使用 / 已验收 / 待处理
与基线差异或未解决问题：
```

附上最终成功输出截图，以及生成的 environment_report.json；必要时附 local-requirements.txt。组长检查版本差异即可，无需队友打包整个 .venv。

## 六、常见问题：请 AI 按这些原则处理

- **No suitable Python runtime found：**没有找到指定 3.14 运行时；先安装/定位真实解释器，不是换个 venv 命令反复试。
- **执行策略报错：**无需 Activate.ps1，直接使用 .venv 的 python.exe 即可。
- **库安装成功，IDE 仍缺库：**比较 IDE 的 sys.executable，修正解释器，不在各个全局环境重复安装。
- **锁文件安装失败：**保留具体包名和错误，核对系统架构、Python 版本与网络；联系组长协调，不自行换版本后说“已按锁文件配置”。
- **检查脚本提示版本或路径错误：**纠正解释器或目录；禁止删掉报错判断。
- **中文方框：**英文字体基础测试通过与中文图字体是两回事；先看报告中的 available_chinese_fonts，后续选择本机已有字体，不因此否定整个 Python 环境。
- **AI 只给了说明：**对话式 AI 正常如此；本地 Agent 有权限和工具时应真实执行并提供证据。
- **配置遇到旧文件：**先比较并说明冲突；保持原文件，未经同意不删除旧环境或覆盖改动。

## 七、供 AI 查证的官方入口

- [Python Windows 下载](https://www.python.org/downloads/windows/)
- [Python venv](https://docs.python.org/3/library/venv.html)
- [PyCharm 虚拟环境配置](https://www.jetbrains.com/help/pycharm/creating-virtual-environment.html)
- [VS Code Python 环境](https://code.visualstudio.com/docs/python/environments)
- [VS Code Notebook](https://code.visualstudio.com/docs/datascience/jupyter-notebooks)

这些链接是安装/菜单查证入口；本团队的实际已测版本、依赖锁与验收规则以交接包为准。全部验收完成后进入比赛数据采集与审计，不需要再追加安装无关工具。
