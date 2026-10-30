"""Editorial synchronization only; does not implement inference or run models."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[4]
log=ROOT/'outputs/logs/strength_stage6/protocol-review-20261030'
doc='研究/05_赛前实力/第六环节_清单评分敏感性与数学方法.md'
brief='**第四步审定建议与脚本规划已细化（R20261030-15）：** [逐项论证与拟议结构]({link})第11—17节依次处理完整赛果生成、模拟真值、参考随机性、历史选型、两方法条件与覆盖/预算。新增指出：M3均值正确不等于遗漏实力的M0也满足鞅差条件；主参考固定成员但逐世界重评分。拟议一个主入口、六模块和独立核验，尚未创建推断程序或运行新模型；先做接口/真值/成本试算，再冻结正式仿真协议。原18拟合与前三步验收保持不变。'
items=[('README.md','# 国际足球分析课程项目',doc),('研究/README.md','# 研究路线、编号与当前进度','05_赛前实力/'+Path(doc).name),
       ('研究/05_赛前实力/README.md','# 第五问：赛前实力评价与调整',Path(doc).name),('文档/01_项目方案/研究日志与决策记录.md','## 当前摘要','../../'+doc)]
for name,anchor,link in items:
    p=ROOT/name;t=p.read_text(encoding='utf-8')
    if brief.format(link=link) not in t:t=t.replace(anchor,anchor+'\n\n'+brief.format(link=link),1)
    if name=='README.md':t=t.replace('第6环节完整评分敏感性、相依/反馈与区间验收待进行','第6环节完整评分/范围/配对敏感性已完成，相依/反馈与区间协议正细化，统计覆盖仍待验收')
    p.write_text(t,encoding='utf-8')
p=ROOT/'研究/pipeline_state.json';state=json.loads(p.read_text(encoding='utf-8'));q=state['question_5'];q['latest_decision_log_id']='R20261030-15'
q['status']='stages1_to5_complete_stage6_steps1_to3_complete_step4_protocol_review_and_script_design'
q['stage_progress']['6']['status']='steps1_to3_complete_step4_specification_reviewed_numerical_protocol_not_frozen'
q['stage6']['protocol_review']=dict(decision_log_id='R20261030-15',document=doc,sections='11–17',status='proposals_and_mathematical_specifications_numeric_gates_pending',
    completed_topics=['full_WDL_generation_and_pre_day_adapter_design','world_expectation_projection_truth','fixed_membership_replayed_score_reference','fixed_selected_rating_rule_scope','M0_nonmartingale_and_centering_limitation','Bartlett_calendar_multiplier_construction','joint_coverage_and_cost_requirements','one_entry_six_modules_independent_audit_plan'],
    numerical_requirements_pending=['readonly_probability_consistency','M0_and_misspecified_model_truth_precision','centering_and_bandwidth_performance','bootstrap_world_M0_center','full_scale_time_memory_and_inner_replication_budget','coverage_failure_and_MC_tolerances_freeze'],
    nominal_joint_coverage_proposed=0.95,simulation_coverage_floor_proposed=0.93,failure_upper_limit_proposed=0.01,thresholds_frozen=False,
    inference_package_created=False,new_model_fits=False,new_statistical_experiments=False,actual_human_review=False)
p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
notes=dict(decision_log_id='R20261030-15',role='workflow and limitations for later presentation; not new statistical results',
    current_result_adoption='outputs/logs/strength_stage6/delivery-618a9dd942fad38863e6/adoption.json',document=doc,
    workflow=['generate full WDL history','define and verify truth','couple reference scores with each world','state fixed-rule selection limitation','compare feedback and score-based methods','freeze coverage and cost protocol','implement pilot then locked validation'],
    required_cautions=['M0 intentionally omits strength; M3 martingale argument does not automatically cover paired changes','fixed reference members are not fixed generated scores','143 registry objects are not143 scalar tests','old timing is a planning estimate, not new runtime measurement','no new coverage or significance results'],
    planned_code_status='not_created',formal_protocol_frozen=False,actual_human_review=False)
(log/'display_notes.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
index=ROOT/'文档/05_团队协作/论文与汇报支撑材料索引.md';text=index.read_text(encoding='utf-8')
existing=[doc,'outputs/logs/strength_stage6/protocol-review-20261030/sources.json','outputs/logs/strength_stage6/protocol-review-20261030/display_notes.json','参考资料/方法文献/sources.json','参考资料/方法文献/README.md']
sources=json.loads((log/'sources.json').read_text())
existing += ['参考资料/方法文献/'+r['local_path'] for r in sources['attempts'] if r['status']=='downloaded']
for name in existing:
    if not (ROOT/name).is_file():raise ValueError('Missing current material:'+name)
entry='## 第五问第六环节第四步｜当前方法准备与汇报说明（R20261030-15）\n\n方法规格与脚本规划，不是新计算结果；下方R14为实际采用的18拟合与敏感性证据。只登记已有文档、来源和展示说明，不登记尚未创建的拟议Python路径。\n\n'+'\n'.join(f'- [{name}](../../{name})' for name in existing)+'\n\n'
if entry not in text:text=text.replace('# 论文与汇报支撑材料索引','# 论文与汇报支撑材料索引\n\n'+entry,1)
index.write_text(text,encoding='utf-8')
html=ROOT/'文档/05_团队协作/汇报要求与HTML方案.md';text=html.read_text(encoding='utf-8')
note='**第五问第四步准备说明（R20261030-15）：** [逐项论证第11—17节](../../'+doc+')与[展示流程说明](../../outputs/logs/strength_stage6/protocol-review-20261030/display_notes.json)可用于解释为何要同时检查有无实力模型、为何全流程反馈不能只模拟主胜。它们是方法与工作流程素材，不是已完成的区间或新结论；实际数字继续读取R14采用包，拟议程序、真值精度及覆盖验收尚未执行。\n\n'
if note not in text:text=text.replace('# 课程汇报要求核对与 HTML 方案','# 课程汇报要求核对与 HTML 方案\n\n'+note,1)
html.write_text(text,encoding='utf-8')
print('Updated documentation, state and existing-material index; no inference code or statistical runs.')
