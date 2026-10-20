# 足球分析项目环境配置：PyCharm 版

更新：2026-10-20。本文可以独立执行；与 VS Code 版二选一。命令均为 PowerShell 语法。菜单以英文名称为主，中文版可通过设置搜索“Python Interpreter / Python 解释器”定位。

## 1. 配置目标与开始前须知

适用：Windows 10/11，PowerShell，项目目录为：

```text
C:\Users\EasonG\Desktop\文件\python项目
```

其他组员将本文中的项目路径替换成自己的路径即可。项目代码放在此目录中，不必再创建第二层项目根目录。

配置分为四层：Python 解释器 → 项目虚拟环境 .venv → 分析依赖 → 编辑器绑定解释器。两种编辑器可以共用同一个 .venv；不需要为每个编辑器各建一套环境。

配置进度更新：用户已安装依赖，本机 Python 3.14.8（64 位）已通过 check_env.py 验收。编辑器运行与 Notebook 内核仍需按本文核对。

首次配置前的历史检查结果（当前已安装 Python，请勿据此重复安装）：
- 找到 py.exe，但 `py -0p` 返回 No installed Pythons found。这表示该启动器未发现已注册解释器，不等于电脑所有位置绝对没有 Python。
- python 命令指向 WindowsApps 入口，不能据此确认已经安装可用解释器。
- code 命令指向 Qoder IDE，不能直接用 `code .` 作为启动 VS Code 的步骤。
- 找到 PyCharm 2025.3.2 和 Git。

## 2. 安装并确认 Python

本次配置统一采用 **Python 3.14 的标准 64 位版本**。前一份路线文档中的 3.12 是初步建议；本次给出可执行配置时改为 3.14，使用仍提供 Windows 安装器的成熟版本，并在首次配置成功后记录具体补丁号。全组保持相同版本。不要混用 3.12 与 3.14 创建各自环境。

1. 打开 [Python 官方 Windows 下载页](https://www.python.org/downloads/windows/)。
2. 找到 Python 3.14 系列，选择 Windows installer (64-bit)。不要直接点页面顶部的最新大版本，也不要下载 embeddable package、32-bit 或 free-threaded 实验构建。
3. 如果 Windows“系统 → 系统信息”显示 ARM 处理器，改选对应 ARM64 安装器；普通 Intel/AMD 电脑选 64-bit。
4. 运行安装器，勾选 Add python.exe to PATH，保留 pip 和 launcher 安装选项，使用 Install Now。按当前用户安装即可。
5. 安装结束后关闭并重新打开 PowerShell 和编辑器。

验证：

```powershell
py -0p
py -3.14 --version
py -3.14 -c "import sys, struct; print(sys.executable); print(struct.calcsize('P') * 8)"
```

预期：版本为 Python 3.14.x；显示真实 python.exe 路径；最后显示 64。记录实际补丁号供全组统一。

如果 py 仍不可用，但已知安装目录，直接用解释器完整路径执行命令，例如：

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" --version
```

这只是传统安装器默认位置的示例，以实际安装位置为准。创建环境时也可以将下一节命令中的 `py -3.14` 替换为 `& "真实完整路径\python.exe"`。

不要卸载现有 Python，也不要先删 WindowsApps 文件。若 python 弹出商店，继续用已验证的 py 或解释器完整路径即可。

## 3. 创建项目虚拟环境与安装依赖

打开 PowerShell，以下命令一条条执行，某一步报错就先处理，不要继续。

```powershell
Set-Location -LiteralPath 'C:\Users\EasonG\Desktop\文件\python项目'
Get-Location
Test-Path -LiteralPath '.venv\Scripts\python.exe'
```

如果最后是 False，创建环境：

```powershell
py -3.14 -m venv .venv
```

如果是 True，先检查，不要重复创建或覆盖：

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable); print(sys.prefix != sys.base_prefix)"
```

应为 Python 3.14.x、路径位于本项目 .venv、最后 True。若不符合，先确认旧环境是否仍被其他项目使用，再通过编辑器选择正确环境或另建环境，不要盲目删除。

安装本项目附带的依赖清单：

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.in
.\.venv\Scripts\python.exe -m pip check
```

看到 No broken requirements found 才进入下一步。安装需要网络，首次耗时取决于下载速度。

依赖用途：
- numpy、pandas：数组运算、比赛数据读取、清洗与特征。
- matplotlib、seaborn：统计图、评级曲线和结果图。
- scipy：统计计算。
- scikit-learn：三分类模型和评价；安装名是 scikit-learn，导入名是 sklearn。
- requests：后续下载数据。
- pytest：后续关键公式和防泄漏检查。
- ipykernel、jupyterlab：Notebook 内核与可选的浏览器 Notebook 入口。

requirements.in 是首次安装的依赖名称清单，**并非已经验证的版本锁文件**。首次成功安装、完成下文检查后，再生成精确版本 requirements.txt。全组第二个人开始优先使用该锁文件，不再独立解析最新版本。

无需 GPU/CUDA、Anaconda、TensorFlow、PyTorch、数据库、Java 或 Node.js。Git 已存在，本阶段可以先不配置远程仓库。

本文命令直接使用 .venv 中的解释器，不要求执行 Activate.ps1，也不需要修改 PowerShell 执行策略。

## 4. 打开项目并绑定现有虚拟环境

本机已找到 PyCharm 2025.3.2，可先使用，无需为了本项目重装。其他组员尚未安装时，从 [JetBrains PyCharm 官网](https://www.jetbrains.com/pycharm/download/) 下载 Windows 版；本项目脚本开发不要求购买额外功能。Notebook 的内置支持取决于版本与可用功能，始终可使用第 7 节浏览器入口。

1. 从开始菜单打开 PyCharm。
2. 欢迎页选择 Open；已有窗口则 File → Open。
3. 选择项目根目录 C:\Users\EasonG\Desktop\文件\python项目，作为项目打开。
4. 如果出现自动创建环境提示，而第 3 节已创建 .venv，选择现有解释器，不再建第二个环境。
5. 按 Ctrl+Alt+S 打开 Settings，搜索 Python Interpreter。入口可能是 Python → Interpreter，或 Project: 项目名 → Python Interpreter。
6. 选择 Add Interpreter → Add Local Interpreter（有些版本显示 Add Local）。
7. 选择 Existing environment / Select existing，环境类型选择 Python / Virtualenv，浏览至：
   C:\Users\EasonG\Desktop\文件\python项目\.venv\Scripts\python.exe
8. 点 OK / Apply，等待索引结束。解释器应是 Python 3.14.x，路径必须在本项目内。
9. 不勾选 Inherit global site-packages；不要选择 WindowsApps 入口或其他项目的环境。

这里采用“先命令创建 .venv，再绑定已有解释器”的统一流程。官方还支持在界面创建环境，但本教程不需要再执行那条路径。[官方虚拟环境说明](https://www.jetbrains.com/help/pycharm/creating-virtual-environment.html)

## 5. 运行、工作目录与调试配置

1. 打开根目录 check_env.py，右键 → Run 'check_env'。
2. 第一次运行后，进入 Run → Edit Configurations。
3. 检查 Script path 指向根目录 check_env.py。
4. Python interpreter 选 Project Default，即刚绑定的 .venv；如果单独指定过其他解释器，改回项目环境。
5. Working directory 设为 C:\Users\EasonG\Desktop\文件\python项目。
6. 参数留空，环境变量通常使用默认值即可；若控制台中文乱码，可设置 PYTHONIOENCODING=utf-8。
7. Apply 后重新运行，核对 sys.executable。

终端：
1. 打开 View → Tool Windows → Terminal。
2. 若终端不是 PowerShell，在 Settings → Tools → Terminal 中选择可用的 powershell.exe 或 pwsh.exe。
3. 即使终端没有显示 (.venv)，也可以直接用第 3 节的 .venv 解释器命令。
4. PyCharm 的 Project Interpreter、Run Configuration、Terminal、Python Console 可能保存不同状态，必须通过实际解释器路径确认；改完解释器后关闭旧 Python Console 再新开。

调试：
1. 在 check_env.py 的 main() 内任一有效代码行左侧单击，设置断点。
2. 右键 Debug 'check_env'，或使用 Shift+F9。
3. 能停住并查看变量，再继续执行，说明调试环境正常。

编码：
在 Settings → Editor → File Encodings 中，将项目与默认文本文件编码设为 UTF-8；不要将既有文件从 UTF-8 错转为 GBK。

Notebook：
若内置 .ipynb 编辑器可用，打开 Notebook 并选择本项目 .venv 对应的内核，运行 sys.executable 验证。若没有该入口或提示功能不可用，直接按第 7 节启动 JupyterLab，不必为此更换编辑器或购买功能。

## 6. 运行环境验收

本目录已附带 check_env.py。命令行运行：

```powershell
.\.venv\Scripts\python.exe check_env.py
```

该脚本使用人工构造的小数据验证 CSV 读写、数值计算、逻辑回归、指标计算与图片保存，**不是足球实验，也不生成研究结论**。正常结果：
- 显示项目 .venv 内的 Python 路径、3.14.x 和 64 位。
- 逐项显示包版本，无导入错误。
- 生成 outputs/environment_check/synthetic_matches.csv。
- 生成 outputs/environment_check/environment_check.png。
- 生成 outputs/environment_check/environment_report.json。
- 最后输出 ENVIRONMENT CHECK PASSED。

打开 PNG 确认柱状图正常。脚本使用英文标签保证基础出图不依赖中文字体；JSON 会记录常见中文字体是否可用。若未找到中文字体，不影响基本验收，后续可在 Matplotlib 中选择本机已安装的 Microsoft YaHei 或 SimHei，再验证中文图。

再用编辑器运行一次同一个脚本，核对解释器路径与命令行一致。脚本路径核验通过后，才能认定编辑器也配置正确；只在终端运行成功还不够。

完成验收后锁定环境：

```powershell
.\.venv\Scripts\python.exe -m pip freeze | Set-Content -LiteralPath requirements.txt -Encoding utf8
.\.venv\Scripts\python.exe -m pip check
```

把 requirements.txt 与 environment_report.json 分享给组员。其他组员安装统一 Python、创建自己的 .venv 后执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe check_env.py
```

不要复制 .venv 文件夹给别人，也不要把它提交进代码仓库。当前清单是同版本 Windows/Python 环境下的复现依据，不能保证跨操作系统安装完全一致。

## 7. 可选：Notebook 配置

建议先完成 .py 文件验收，再配置 Notebook。浏览器入口不依赖具体 IDE 版本：

```powershell
.\.venv\Scripts\python.exe -m jupyterlab
```

浏览器打开终端给出的本地地址；在 Notebook 中运行：

```python
import sys
print(sys.executable)
import pandas as pd
print(pd.__version__)
```

解释器必须指向本项目 .venv。Ctrl+C 停止本地服务。若需要在内核列表中明确命名，可以执行：

```powershell
.\.venv\Scripts\python.exe -m ipykernel install --user --name football-elo --display-name "Python (football-elo)"
```

此可选命令会在当前用户目录注册一个内核；项目移动或重建后，需要重新注册以免旧路径失效。

## 8. 常见错误与处理顺序

### 找不到 py 或 No installed Pythons found

确认安装的是完整 Python，关闭终端重新打开；用安装位置的 python.exe --version 检查。只有 launcher 不等于安装了 Python。不要尝试用无法运行的 Python 创建环境。

### 找不到 .venv 或 requirements.in

先运行 Get-Location，确认正在项目根目录；用 Test-Path 检查文件。必须打开完整项目文件夹，不能只打开某个 .py 文件。路径中的中文不是必须迁移项目的理由。

### Activate.ps1 被禁止执行

本文无需激活即可工作。保持使用 .\\.venv\\Scripts\\python.exe -m pip，不必修改系统执行策略。

### 安装后仍报 ModuleNotFoundError

用编辑器运行下面代码，查看实际解释器：

```python
import sys
print(sys.executable)
```

把解释器改为本项目 .venv。不要用裸 pip 反复安装；始终用目标 python.exe -m pip，尤其不要混淆 sklearn 与 scikit-learn。

### pip 下载超时、代理或证书错误

先检查浏览器能否访问 https://pypi.org，确认校园网/代理正常，再重试：

```powershell
.\.venv\Scripts\python.exe -m pip install --timeout 120 --retries 5 -r requirements.in
```

若已有团队锁文件，将上面 requirements.in 改为 requirements.txt。若需镜像或学校证书，按可信官方/学校配置处理；不要为了下载关闭 TLS 验证，也不要使用来源不明的 wheel。

### No matching distribution / 尝试本地编译失败

核对 Python 版本、64 位与标准构建；确认不是误装了刚发布的新大版本。先更新 pip、核对包名和锁文件，再调查兼容性；本项目不应把安装 C++ 编译工具链作为默认前置步骤。

### pip check 不通过

保留完整报错，检查冲突包来自哪次安装。新环境只装本项目依赖，避免继承全局 site-packages；不要靠 --no-deps 掩盖冲突。

### PNG 正常但中文方框

这是字体问题，不是模型或 pandas 问题。选择本机存在的中文字体，例如：
```python
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
```

### 工作目录和数据路径不一致

正式脚本以 pathlib.Path(__file__).resolve().parent 定位项目根目录，避免依赖终端当前位置。编辑器运行配置的工作目录也设为项目根目录。

## 9. 完成标准与交付

- [ ] Python 3.14.x、64 位可用，具体补丁号已记录并与组员统一。
- [ ] 项目 .venv 可用，pip check 无冲突。
- [ ] 编辑器运行脚本显示的解释器就是该 .venv。
- [ ] check_env.py 通过，CSV、PNG、JSON 均生成并检查。
- [ ] requirements.txt 已在验收后生成；另一位组员按它安装并复现。
- [ ] 若使用 Notebook，其解释器也与脚本一致。
- [ ] 全组保留文档、requirements.in、requirements.txt、check_env.py；不分享 .venv。

完成以上项目后，环境阶段结束，下一步是采集并冻结比赛数据，而不是继续安装更多工具。

## 10. 官方参考

- [PyCharm 下载](https://www.jetbrains.com/pycharm/download/)
- [配置解释器](https://www.jetbrains.com/help/pycharm/configuring-python-interpreter.html)
- [配置虚拟环境](https://www.jetbrains.com/help/pycharm/creating-virtual-environment.html)
- [Python Windows 下载](https://www.python.org/downloads/windows/)
- [venv 文档](https://docs.python.org/3/library/venv.html)

PyCharm 菜单随版本会有变化；以解释器文件路径为最终判断标准。本机依赖已通过脚本验收并锁定，编辑器运行与 Notebook 内核尚需用户核对。

