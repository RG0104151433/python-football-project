# 足球分析项目环境配置：VS Code 版

更新：2026-10-20。本文可以独立执行；与 PyCharm 版二选一。命令均为 PowerShell 语法，不要连同提示符或 Markdown 围栏复制。

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

## 4. 安装并配置真正的 VS Code

1. 从 [VS Code 官方网站](https://code.visualstudio.com/) 下载 Windows 稳定版，普通个人电脑可使用 User Installer。
2. 安装后从 Windows 开始菜单打开 **Visual Studio Code**。本机 code 命令目前属于 Qoder，因此本教程不使用 code 命令启动。
3. 在 File → Open Folder 打开项目根目录：
   C:\Users\EasonG\Desktop\文件\python项目
4. 按 Ctrl+Shift+X 打开扩展面板，安装 Microsoft 发布的 Python（扩展 ID：ms-python.python）。
5. 检查 Pylance（ms-python.vscode-pylance）与 Python Debugger（ms-python.debugpy）是否已随 Python 扩展安装；若没有，再安装。
6. 使用 Notebook 时安装 Microsoft 的 Jupyter（ms-toolsai.jupyter）。中文界面语言包可选，不影响运行。不要把 Code Runner 当作本教程的 Python 运行入口。

选择解释器：
1. 按 Ctrl+Shift+P。
2. 执行 Python: Select Interpreter。
3. 选择项目内 .venv；若未列出，选 Enter interpreter path / Find，手动选择：
   C:\Users\EasonG\Desktop\文件\python项目\.venv\Scripts\python.exe
4. 打开 .py 文件，检查状态栏解释器。解释器名称可能因扩展版本不同而不同，以完整路径为准。

可选：如果尚无 .vscode/settings.json，可通过 Preferences: Open Workspace Settings (JSON) 添加下列设置；已有配置时合并字段，不要整份覆盖：

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
  "files.encoding": "utf8"
}
```

defaultInterpreterPath 是默认发现提示，不能替代 Select Interpreter，也不一定覆盖已经保存的解释器选择。[官方解释器文档](https://code.visualstudio.com/docs/python/environments)

## 5. 配置运行、调试和 Notebook 入口

运行：
1. 打开根目录 check_env.py。
2. 点编辑器右上角 Run Python File in Terminal，或右键选择同名命令。
3. 检查输出路径为当前项目 .venv，不要点 Code Runner 的 Run Code。
4. 使用 Terminal → New Terminal 时选 PowerShell；若终端自动激活失败，直接使用第 3 节的完整解释器命令。

调试：
1. 在 check_env.py 的 main() 内任一有效代码行左侧单击，设置断点。
2. 按 F5，按提示选择 Python Debugger → Python File（具体提示随版本略有差异）。
3. 能停在断点、查看变量，再继续运行，即说明调试入口正常。

Notebook：
1. 创建 notebooks 文件夹，再创建 .ipynb 文件。
2. 右上角 Select Kernel → Python Environments，选择项目 .venv。
3. 执行第 7 节的 sys.executable 验证。
4. VS Code 的脚本解释器和 Notebook 内核需要分别核对，不能假设选择一个就自动配置全部。

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

- [VS Code Windows 安装](https://code.visualstudio.com/docs/setup/windows)
- [Python 扩展与入门](https://code.visualstudio.com/docs/python/python-tutorial)
- [解释器与环境](https://code.visualstudio.com/docs/python/environments)
- [Notebook 内核与使用](https://code.visualstudio.com/docs/datascience/jupyter-notebooks)
- [Python Windows 下载](https://www.python.org/downloads/windows/)
- [venv 文档](https://docs.python.org/3/library/venv.html)

本机 Python 3.14.8 已通过脚本验收，requirements.txt 已生成。编辑器运行与 Notebook 内核尚需用户核对。

