# 课程提交：中文取用说明

**中文** | [English](README_SUBMISSION.en.md)


Code.zip、Data.zip解压到同一父目录，合并FootballProject；需要论文源码再合入Report.zip。正式论文为paper/final_paper.pdf。python123仅收报告和代码，邮件用三个ZIP。

## 检查与环境

在FootballProject运行python quick_check.py，预期7/7；只读采用结果，不重训或核验未来实际成绩。记录环境为Windows x64的CPython 3.14.8。自行创建.venv并安装requirements-core.txt、运行pip check；无需GPU。完整requirements.txt与核心依赖范围用途不同，不是相同的锁定环境。

```powershell
python -m src.snapshot --verify --config config.json
python -m src.audit --config config.json
python -m pytest -q tests/test_data_rules.py tests/test_strength_baseline.py tests/test_strength_joint.py --basetemp .submission_test_tmp
```

audit写诊断报告，原始已知冲突导致预期review_needed/退出1和40条ERROR，不是安装失败；清洗另有处置。代码入口与配置见scripts导航及pipeline_state。

## 精简范围和结论边界

数据包保留原始输入、论文证据和最终汇总，省略多数模拟世界、检查点及大诊断。严格回放须补完整仓库或重新生成，不得改指纹掩盖缺输入。部分脚本加--help仍执行；clean按python -m src.clean运行。

70.01%是历史二分类准确率，不是三分类或未来成绩；提交件无已核验未来赛果。交付核验不等于新机器安装或成员独立复核。完整项目题目及细节见英文版。

原始文件：[README_SUBMISSION.md](README_SUBMISSION.md)，原指纹保留。
