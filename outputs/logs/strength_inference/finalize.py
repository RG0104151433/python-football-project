"""Synchronize current navigation AFTER completed, audited development runs."""
from pathlib import Path
import json
from src.data_contract import write_json
from src.strength.io import ROOT

base = ROOT/'outputs/logs/strength_inference'
summary = json.loads((base/'summary.json').read_text())
assert len(summary['worlds']) == 2
audits = {stage:json.loads((base/(stage+'_audit.json')).read_text()) for stage in ('interface','diagnostic','pilot')}
assert all(a['passed'] for a in audits.values())
ip = json.loads((base/'interface_pointer.json').read_text())['directory']
dp = summary['diagnostic']['directory']; pp = summary['pilot']['directory']
doc = '研究/05_赛前实力/第六环节_清单评分敏感性与数学方法.md'

def prepend(path, text):
    p = ROOT/path; body = p.read_text(encoding='utf-8-sig'); first, rest = body.split('\n',1)
    marker = '**双路线开发试算已运行（R20261030-16）：**'
    if marker in body: raise ValueError('Already synchronized: '+path)
    p.write_text(first+'\n\n'+text+'\n'+rest, encoding='utf-8', newline='\n')

for path, link in [('README.md',doc), ('研究/README.md','05_赛前实力/'+Path(doc).name),
                   ('研究/05_赛前实力/README.md',Path(doc).name)]:
    prepend(path, f'**双路线开发试算已运行（R20261030-16）：** [当前运行、数学依据与复现]({link})第18节。六模块和统一入口已实现；54对象×四日历带宽各999扰动，另做两次完整38919学习/24917分析历史，各重新拟合M0/M3并计算54配对目标。90相关测试通过；接口/诊断/试算独立核验{audits["interface"]["checks"]}/{audits["diagnostic"]["checks"]}/{audits["pilot"]["checks"]}项通过；诊断三个核心产物两跑字节一致。两路线尚未选出赢家，M0独立真值与中心化、共同覆盖/正式应用未准入；此前真实点估计和18敏感性拟合保持不变。下方R15为当时规划记录。')

state_path = ROOT/'研究/pipeline_state.json'; state=json.loads(state_path.read_text(encoding='utf-8-sig'))
q=state['question_5']; q['latest_decision_log_id']='R20261030-16'
q['status']='stages1_to5_complete_stage6_steps1_to3_complete_step4_two_route_development_runs_completed_not_admitted'
q['stage_progress']['6']['status']='steps1_to3_complete_step4_implemented_development_pilots_completed_formal_inference_pending'
s=q['stage6']; s['decision_log_id']='R20261030-16'
s['development_implementation']=dict(decision_log_id='R20261030-16', document=doc, section=18,
    implemented=True, module='src/strength_inference', entry='scripts/analyze_strength_inference.py',
    audit_entry='scripts/audit_strength_inference.py', interface=ip, diagnostic=dp, pilot=pp,
    summary='outputs/logs/strength_inference/summary.json',
    diagnostic_targets=54, diagnostic_bandwidths=[1,90,365,1095], diagnostic_repetitions_per_bandwidth=999,
    full_history_worlds=2, learning_matches_per_world=38919, study_matches_per_world=24917,
    real_models_replaced=False, real_scores_replayed=False, simulated_scores_replayed=True,
    M0_oracle_precision_admitted=False, raw_score_centering_validated=False, coverage_validated=False,
    final_method_selected=False, formal_intervals_admitted=False, tests=90,
    independent_audits={k:dict(checks=v['checks'],path=f'outputs/logs/strength_inference/{k}_audit.json') for k,v in audits.items()},
    reproducibility='outputs/logs/strength_inference/diagnostic_reproducibility.json',
    html_finalized=False, actual_human_review=False)
write_json(state_path,state)

paper_paths=[doc,'config/strength_inference.json','scripts/analyze_strength_inference.py','scripts/audit_strength_inference.py',
    *[f'src/strength_inference/{n}.py' for n in ['__init__','contract','worlds','targets','methods','experiment','reporting']],
    'tests/test_strength_inference.py',ip+'/review.json',dp+'/report.json',dp+'/diagnostic_ranges.csv',
    dp+'/calendar_influence.csv.gz',dp+'/multiplier_draws.csv.gz',pp+'/report.json',pp+'/models.json',
    pp+'/world_probabilities.csv.gz',pp+'/world_score_marginals.csv.gz',pp+'/world_estimates.csv',pp+'/method_comparison.csv',
    'outputs/logs/strength_inference/tests.xml','outputs/logs/strength_inference/interface_audit.json',
    'outputs/logs/strength_inference/diagnostic_audit.json','outputs/logs/strength_inference/pilot_audit.json',
    'outputs/logs/strength_inference/summary.json','outputs/logs/strength_inference/diagnostic_reproducibility.json']
for p in paper_paths: assert (ROOT/p).exists(), p
entries='\n'.join(f'- [{p}](../../{p})' for p in paper_paths)
prepend('文档/05_团队协作/论文与汇报支撑材料索引.md',
    '**双路线开发试算已运行（R20261030-16）：** 当前论文方法/开发证据如下；仅登记既有文件，不迁移。无最终置信区间、显著性或路线优胜结论。下方R15及R14分属规划和既有敏感性历史。\n\n'+entries+
    '\n\n汇报取数：`outputs/logs/strength_inference/display_notes.json`为流程与边界，实际研究发现仍用R14采用包，不把开发范围绘成正式误差棒。')

display=dict(decision_log_id='R20261030-16', status='development_methods_only_not_final_inference',
    findings_source='outputs/logs/strength_stage6/delivery-618a9dd942fad38863e6/display_data.json',
    workflow=['先核对54目标和只读评分接口','A重新生成完整历史并同场重拟合两模型','B按实际日历联合扰动两模型','独立真值和共同覆盖未通过前不选择路线'],
    two_route_summary='A保留历史反馈但真值/中心和成本仍待审定；B快速保留配对信息但M0中心化和长期依赖仍待检验',
    results_summary='outputs/logs/strength_inference/summary.json',
    allowed=['实现流程','诊断成本','诊断对依赖长度敏感这一方法发现','此前第三步主要实质发现'],
    forbidden=['把诊断范围当置信区间','把两个世界当覆盖验收','把同世界27目标当27个独立重复','宣称最终路线优胜'],
    formal_method_selected=False, confidence_intervals_admitted=False, final_html_created=False, human_review=False)
write_json(base/'display_notes.json',display)
prepend('文档/05_团队协作/汇报要求与HTML方案.md',
    '**双路线开发试算已运行（R20261030-16）：** [方法与运行](../../'+doc+')第18节、[流程与展示边界](../../outputs/logs/strength_inference/display_notes.json)和[实际摘要](../../outputs/logs/strength_inference/summary.json)已保存。可展示完整反馈与日期乘子的不同处理思路；不可把开发范围当正式置信区间或宣称最终方法已选出。未制作最终HTML。')

mean=summary['mean_full_world_seconds']; world_text='\n'.join(
    f'- 种子{w["seed"]}：38919学习/24917研究，生成{w["generation_seconds"]:.2f}秒，完整生成、双拟合、两次目标评价及B诊断合计{w["seconds"]:.2f}秒；赛前查询最大差{w["max_query_error"]:.3g}；27个已知M3目标的RMSE为{w["known_M3_RMSE_pp"]:.4f}个百分点。' for w in summary['worlds'])
with (ROOT/doc).open('a',encoding='utf-8',newline='\n') as f:
    f.write(f'''\n### 18.6 完整反馈试算的实际结果与交接\n\n结果包`{pp}/`已完成。两世界各保存38,919条完整三类概率、24,917条分析评分边际及54目标；合计77,838概率记录、49,834分析评分和108目标记录，两模型共4次三起点拟合。每个世界均重新从1950初始状态学习，没有接用现实1980评分。\n\n{world_text}\n\n平均完整试算耗时{mean:.2f}秒；这包括本轮额外目标与B诊断，不是纯生成器耗时，也不是独占机器性能基准。完整赛程与54目标的代码接口已跑通，不能据两个历史推断95%共同覆盖。27已知M3目标彼此相关，不能当作每世界27次独立实验。另27配对目标仍标`M0_PROJECTION_NOT_READY`。\n\n两世界平均软概率的M0投影求解已完成，但它使用同一开发流、只有两个世界；单路径投影和跨世界平均投影分开保存。该投影尚无独立精度验收，不能作为正式bootstrap中心。两条路线现在都能进入同一比较框架；当前报告的`winner`仍为`NOT_SELECTED`。\n\n独立核验：接口{audits['interface']['checks']}项、日期诊断{audits['diagnostic']['checks']}项、完整试算{audits['pilot']['checks']}项均通过。完整试算未重新生成同种子第二遍，不宣称A世界已全量重复；检查点缓存不算独立世界。原始和清洗数据指纹不变。\n\n**下一轮必须完成的实际工作：** 先用独立随机流建立M0损失投影参照并报告精度，验证A的每个拟合生成世界中心；同时用模拟已知的日期均值诊断B的均值漂移与相关长度，不能直接删除漂移来获得较窄范围。再按小规模成本确定有限情景、世界数和内层次数，冻结门槛，运行同外层世界的两方法覆盖比较及新随机流验证。满足门槛前不出正式现实区间，不根据现实结论的方向选方法。当前独立真值、正式验证与应用代码尚未完成，属于后续实现任务。\n''')

body=(ROOT/doc).read_text(encoding='utf-8')
body=body.replace('当前诊断包为`outputs/tables/strength_joint/inference-diagnostic-77f7d4884e60e121983d/`',f'当前诊断包为`{dp}/`')
body=body.replace('第二次实测约112.12秒',f'当前源码版本实测约{summary["B_seconds"]:.2f}秒；此前第二次约112.12秒')
body+='\n本地`outputs/logs/strength_inference/checkpoints/`只作可重建的完整世界续跑缓存，已加入Git忽略；正式概率、评分边际、模型、目标、版本清单和源码快照另存结果包，不依赖缓存交付。\n'
(ROOT/doc).write_text(body,encoding='utf-8',newline='\n')

log=ROOT/'文档/01_项目方案/研究日志与决策记录.md'
body=log.read_text(encoding='utf-8-sig')
start=body.index('**R20261030-16正在执行：**'); end=body.index('\n',start)
body=body[:start]+f'**双路线开发试算已运行（R20261030-16）：** 六模块及统一/核验入口已创建；54对象四带宽各999扰动和两个完整38919/24917反馈世界已完成；90测试、79/715/{audits["pilot"]["checks"]}独立核对通过，诊断三核心两跑一致。原始/清洗及原真实结果不变；最终路线未选、独立M0真值/中心与覆盖验收待完成。详见阶段文档第18节和`outputs/logs/strength_inference/summary.json`。'+body[end:]
body+=f'''\n- R30-16实际结果补记：接口22项已知答案/数值检查通过，独立包核对79项；B现实54目标×四带宽各999扰动，216诊断范围，715独立核对通过，三数值核心两次实际计算字节一致。第二次整体112.12秒，诊断标准差中位数1/90/365/1095日分别1.006/1.300/1.298/1.346pp；说明依赖长度会改变精度近似，不据某一范围跨零与否选带宽。全套实力相关90测试通过（旧83加新7），`outputs/logs/strength_inference/tests.xml`保存真实报告。\n- A实际完成两个独立种子完整反馈：结果`{pp}`，各38919学习/24917研究；保存全部77838个生成概率、49834评分边际、108目标，两世界M0/M3共4次三起点拟合并沿用原数值门槛。每个世界配套B365；平均完整试算{mean:.2f}秒。具体查询误差、已知M3目标误差、耗时见summary；各世界27目标相依，不把它们计为独立覆盖次数。独立试算核验{audits['pilot']['checks']}项通过。未全量重跑同种子生成，未声称A重复验收。\n- 两世界均值软标签M0投影和两个单路径投影分别保存；同开发流/两世界不足以作为独立精确oracle，配对真值留空。A仍待其bootstrap中心精度、B仍待M0均值中心化和依赖适配、两者均待锁定覆盖验收。最终路线未选，不以速度/较窄/显著选择；数学比较依据及条件保留主文18.2。当前程序对truth/validate/apply明确拒绝，尚未实现的步骤不记成通过。\n- 本轮新增代码、配置、源码快照、输入/结果指纹、执行时间和独立核验均保留；同步根/研究/阶段README、pipeline、论文索引和展示流程。读取摘要的一次命令换行转义失败，改用已保存汇总脚本成功，无研究运行受影响。执行Codex（AI），无真人复核或提交；实际原始/清洗指纹与旧值一致。下一步独立真值/中心与均值趋势诊断，再冻结双路线正式验证预算和协议。\n'''
log.write_text(body,encoding='utf-8',newline='\n')
print('Documentation and current state synchronized; no new statistical claims')
