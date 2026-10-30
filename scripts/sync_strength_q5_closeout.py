"""Synchronize adopted Q5 results and existing material paths after real checks."""
from pathlib import Path
import csv,json,re,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import atomic_bytes,write_json


def text(path):return (ROOT/path).read_text(encoding='utf-8-sig')
def put(path,value):atomic_bytes(ROOT/path,value.encode('utf-8'))
def prepend(path,body):
    old=text(path);title,rest=old.split('\n',1)
    marker='<!-- Q5-CURRENT-START -->';end='<!-- Q5-CURRENT-END -->'
    rest=re.sub(re.escape(marker)+r'.*?'+re.escape(end)+r'\n*','',rest,flags=re.S)
    put(path,title+'\n\n'+marker+'\n'+body+'\n'+end+'\n\n'+rest.lstrip('\n'))


def run():
    log=ROOT/'outputs/logs/strength_inference'
    cp=json.loads((log/'comparison_pointer.json').read_text());folder=ROOT/cp['directory']
    d=json.loads((folder/'scope_decision.json').read_text())
    audit=json.loads((log/'q5_calculation_audit.json').read_text())
    pred=json.loads((log/'prediction_pointer.json').read_text());pa=json.loads((log/'prediction_audit.json').read_text())
    material=json.loads((ROOT/'outputs/logs/strength_q5_closeout/current.json').read_text())
    tests=ET.parse(log/'q5_all_tests.xml').getroot()
    suites=list(tests.iter('testsuite'));n=sum(int(s.attrib.get('tests',0)) for s in suites)
    if not audit['passed'] or not pa['passed'] or any(int(s.attrib.get(k,0)) for s in suites for k in ('failures','errors')):
        raise ValueError('FINAL_CHECKS_REQUIRED')
    if d['selected_route']!='A' or d['admitted_targets']!=30 or d['withheld_targets']!=24:
        raise ValueError('FINAL_ADOPTION_DIFFERS_FROM_EXPECTATION; REVIEW_NARRATIVE_BEFORE_SYNC')
    confirmation=json.loads((folder/'confirmation_result.json').read_text())
    fresh=confirmation['new_worlds']
    ident='R20261031-06';base=cp['directory'];pf=pred['directory']
    common=f'''**第五问在声明范围内收尾（{ident}）：** 已完成统一标准、两路线补齐、独立模拟比较和回顾性年度预测。采用完整非线性重算A；原54对象保留，**30项获准模型条件参照，24项地域前后变化因模拟标准精度不足不准入**，不是原54族全部通过。80个真值、56个校准和128个首轮验证历史完成；保留首轮同日63/64未过的结果，再以{fresh}个新流历史作有剩余错误预算的顺序确认，模型和宽度不改。{n}项相关测试、{audit['checks']:,}项最终数值核对及{pa['checks']:,}项预测核对通过。

1990—2024同一21,413场，三个方案只用过去资料拟合和编码。实力＋背景相对仅背景的对数损失下降{100*pa['background_to_joint_relative_loss_reduction']:.2f}%，在仅实力上再改善{100*pa['strength_to_joint_relative_loss_reduction']:.2f}%；二元主胜/非主胜准确率{100*pa['metrics']['M3_nested']['binary_accuracy']:.2f}%。这是历史滚动验证，不能当新增盲测、完整胜平负准确率或未知真实分布的95%保证。B仅节省约8.93%全流程成本，未达事前20%替代门槛。

HTML及论文支撑已准备，图像、离线资源和控制脚本已检查；验收浏览器安全规则拒绝本地文件预览，**实际浏览器与投影验收未完成**，不能由静态检查代替。
'''
    # Current status is prominent; earlier dated text is explicitly historical.
    for path,prefix in [('README.md',''),('研究/README.md','../'),('研究/05_赛前实力/README.md','../../')]:
        location='研究/05_赛前实力/'
        links=f"\n[收尾、主要发现与本地复核]({prefix+location}第五问_收尾与下一问交接.md) · [离线HTML]({prefix+location}展示/index.html) · [数学推导]({prefix+location}第六环节_清单评分敏感性与数学方法.md) · [第六问准备]({prefix}研究/06_历史参考周期/README.md)\n\n以下带日期内容保留当时进度；当前结论与采用范围以本段、收尾说明及pipeline登记为准。"
        prepend(path,common+links)
    root=text('README.md')
    root=re.sub(r'7\. \*\*第五问：.*?(?=\n\n\*\*后续编号)',
        '7. **第五问：六环节在已声明范围内完成（R20261031-06）。** [当前收尾与复核](研究/05_赛前实力/第五问_收尾与下一问交接.md)、[HTML展示](研究/05_赛前实力/展示/index.html)。完整非线性A作为主方法，30项模型条件参照与24项不准入明确分开；原点估计和18敏感性拟合保留。历史滚动显示实力承载主要预测信息，背景有较小增量。第六问交接已准备；最终整组报告正文、老师载体许可和真人复核未冒写完成。',root,flags=re.S)
    put('README.md',root)
    study=text('研究/README.md')
    study=re.sub(r'(## 第五问：赛前实力评价与调整\n\n).*?(?=\n\n## 第六至)',
        r'\1已完成评分、共同模型、解释、敏感性、双路线比较及限定范围验收。当前入口：[第五问收尾](05_赛前实力/第五问_收尾与下一问交接.md)和[HTML](05_赛前实力/展示/index.html)。A用于30项模型条件参照，原24地域变化不准入；不把条件结果当真实无条件保证。',study,flags=re.S)
    study=study.replace('第五问已有小范围评分原型与试算、尚未通过数值验收和全量应用，第六至第十问未运行。','第五问已在R20261031-06声明范围内收尾，第六问准备完成、尚未运行，第七至第十问未运行。')
    put('研究/README.md',study)
    for path in ['研究/05_赛前实力/第三环节_运行结果与交接.md','研究/05_赛前实力/第四五环节_比较结果与研究解释.md','研究/05_赛前实力/实力评估_逻辑与运行说明.md','研究/05_赛前实力/第六环节_清单评分敏感性与数学方法.md']:
        prepend(path,'**当前收尾（R20261031-06）：** [结果、采用边界与复核](第五问_收尾与下一问交接.md)。完整A为主方法；原54项保留、30项获准模型条件参照、24项地域前后变化不准入。新版预测仅用过去编码；以下各节按日期保留研究过程，旧“未完成”描述不代表当前状态。')
    path='研究/06_历史参考周期/README.md'
    put(path,text(path).replace('rolling-prediction-41c77e3a1f9eeba865ec',pf.split('/')[-1]))
    state=json.loads(text('研究/pipeline_state.json'));q=state['question_5']
    q.update(status='closed_with_declared_conditional_scope_and_explicit_nonadmission',decision_log_id=ident,
        current_closeout='研究/05_赛前实力/第五问_收尾与下一问交接.md',current_HTML=material['HTML'],
        final_inference=dict(directory=base,selected_route='A',original54_retained=True,original54_joint_admitted=False,
            admitted_targets=30,withheld_regional_changes=24,complete_worlds=264+fresh,truth_worlds=80,calibration_worlds=56,first_validation_worlds=128,fresh_confirmation_worlds=fresh,
            confirmation=base+'/confirmation_result.json',first_stage_failure_preserved=True,model_and_width_unchanged=True,
            paired_world_model_refits=2*(184+fresh),
            decision=base+'/scope_decision.json',ranges=base+'/scope_reference_ranges.csv',comparison=base+'/scope_method_comparison.csv',
            audit='outputs/logs/strength_inference/q5_calculation_audit.json',tests=n,
            unconditional_real_coverage_certified=False,historical_selection_adjusted=False),
        past_only_prediction=dict(directory=pf,matches=21413,annual_fits=105,audit='outputs/logs/strength_inference/prediction_audit.json',
            all_encoding_uses_past=True,new_blind_future_test=False,full_WDL=False),
        material_pointer='outputs/logs/strength_q5_closeout/current.json',actual_human_review=False,actual_browser_validation=False,
        HTML_status='offline_materials_and_static_checks_ready_browser_file_preview_policy_blocked',
        remaining_global_delivery=['actual local browser and projector validation','teacher HTML permission','whole-course final report','actual group review and rehearsal'])
    q['stage6'].update(stage6_complete_with_declared_limits=True,stage6_complete=True,step4_method_selected=True,current_adoption=base+'/scope_decision.json',
        original54_joint_admitted=False,admitted_targets=30,withheld_targets=24)
    q['stage6']['fresh_confirmation'].update(status=confirmation['current_stop'],result=base+'/confirmation_result.json',new_worlds=fresh,final_admission_declared=True)
    q['stage6']['count_scope']='original sensitivity counts retained below; current complete-world inference counts and adoption are in question_5.final_inference'
    q['goal_discussion'].update(status='research_scope_closed_with_declared_conditional_limits',
        planning_snapshot_note='earlier proposed/implemented flags record the planning history; current stage_progress and final_inference govern handoff')
    q['joint_analysis'].update(original_point_run_snapshot=True,current_inference_adoption=base+'/scope_decision.json',
        current_scope='30 model-conditional references;24 regional paired changes not admitted',next_tasks=[])
    q['stage_progress']['5']['scope']='interpretation and reusable Q5 HTML/paper materials prepared; whole-course integration remains'
    q['stage_progress']['6'].update(status='completed_with_conditional_scope_and24_explicit_nonadmissions',outstanding=[],
        limits=['24 regional paired changes not admitted for formal ranges','no real unconditional or prospective certificate'])
    state['question_6'].update(decision_log_id=ident,status='handoff_prepared_not_started',results_generated=False,
        preparation='研究/06_历史参考周期/README.md',comparison_start_candidate=2000,common_test_matches=16599)
    write_json(ROOT/'研究/pipeline_state.json',state)
    # Index lists files that exist, without copying their content.
    papers=['研究/05_赛前实力/第五问_收尾与下一问交接.md','研究/05_赛前实力/第六环节_清单评分敏感性与数学方法.md',
        'config/strength_inference_validation.json','config/strength_inference_scope.json','config/strength_inference_truth_margin.json','config/strength_inference_confirmation.json',
        base+'/identity.json',base+'/source_snapshot.zip',base+'/numerical_extension.json',base+'/method_decision.json',
        base+'/scope_decision.json',base+'/scope_calibration.json',base+'/scope_method_comparison.csv',base+'/scope_reference_ranges.csv',
        base+'/scope_decision_first_stage.json',base+'/scope_method_comparison_first_stage.csv',base+'/confirmation_schedule.json',base+'/confirmation_result.json',
        base+'/conditional_independent_dates/truth.json',base+'/same_day_shared_noise/truth.json',
        'outputs/logs/strength_inference/truth_audit.json','outputs/logs/strength_inference/route_timing.json',
        'outputs/logs/strength_inference/full_fast_equivalence.json','outputs/logs/strength_inference/q5_all_tests.xml',
        'outputs/logs/strength_inference/q5_calculation_audit.json','outputs/logs/strength_inference/prediction_audit.json',
        *[pf+'/'+name for name in ('predictions.csv','yearly_metrics.csv','group_metrics.csv','calibration_bins.csv','models.json','protocol.json','manifest.json','source_snapshot.zip')],
        'scripts/run_strength_inference_final.py','src/strength_inference_numerics.py','src/strength_inference/comparison.py','src/strength_inference_report.py',
        'scripts/audit_strength_inference_truth.py','scripts/report_strength_inference.py','scripts/audit_strength_q5_final.py','scripts/confirm_strength_inference.py',
        'scripts/audit_strength_q5_html.py','scripts/audit_strength_q5_html.cjs','outputs/logs/strength_inference/confirmation_protocol_audit.json',
        '参考资料/方法文献/sources.json','参考资料/方法文献/原文/Howard_etal_2020v5_confidence_sequences.pdf',
        'src/strength_predictive_validation.py','scripts/analyze_strength_predictive_validation.py','scripts/audit_strength_predictive_validation.py',
        '研究/06_历史参考周期/README.md']
    display=[material['HTML'],material['document'],material['directory']+'/presentation_data.json',material['directory']+'/object_disposition.csv',material['directory']+'/manifest.json',
        *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/material['figures']).glob('*'))]]
    for path in papers+display:
        if not (ROOT/path).exists():raise ValueError('INDEX_PATH_MISSING: '+path)
    def lines(paths):return '\n'.join('- ['+p.rsplit('/',1)[-1]+'](../../'+p+') — `'+p+'`' for p in paths)
    prepend('文档/05_团队协作/论文与汇报支撑材料索引.md',f'''## 第五问当前采用材料（{ident}）

30项条件参照、24项明确不准入；新版年度预测与完整模拟分别说明。以下只列现有文件名与路径。

### 论文支撑

{lines(papers)}

### 汇报支撑

{lines(display)}

### 历史对照

- `outputs/tables/strength_joint/rolling-prediction-41c77e3a1f9eeba865ec/`：含全期编码首版，已被修正版替代。
- R20261030-16日期乘子/两世界开发试算与下方索引保留，用于说明迭代，不能当当前正式参照。
''')
    prepend('文档/05_团队协作/分工与交付/03_后续分析与展示.md','''**第五问交接（R20261031-06）：** 当前说明见[收尾文档](../../../研究/05_赛前实力/第五问_收尾与下一问交接.md)，[HTML](../../../研究/05_赛前实力/展示/index.html)可离线打开。

- A：先读“本地复核”，在仓库根目录用自己的环境跑两项审计，提交终端结果和环境版本；核对30项获准/24项不准入、预测21,413场/105拟合，以及模型条件限制。若缺本地世界缓存，报告缺少的具体文件，按冻结种子重建，不能填已复现。
- B：读90秒稿，用自己的话说明“实力是主要信息，背景增量小且非每年改善”；逐屏核对数字、单位、来源，特别是70.01%只指主胜/非主胜，64/64是模拟历史验收而非比赛预测。记录不理解或可能误导的说法，交回组长。
- 两人实际复核、计时排练、老师是否接受HTML均尚无记录。现有AI检查不能替代本人完成。
''')
    prepend('文档/05_团队协作/汇报要求与HTML方案.md','''**第五问HTML素材已制作（R20261031-06）：** [离线三屏展示](../../研究/05_赛前实力/展示/index.html)、[90秒讲稿及论文说明](../../研究/05_赛前实力/第五问_收尾与下一问交接.md)和[统一材料索引](论文与汇报支撑材料索引.md)。页面使用本地内嵌图和数据，无外部字体或网络依赖；附录给年度增量、全部27个实力后差异及来源。30项条件参照与24项未准入分开显示。

本文件下方早期“未制作HTML”是当时状态；`outputs/logs/strength_q5_closeout/browser_review.json`保存静态/19项控制逻辑检查，也明确记录内置浏览器安全规则拒绝file预览，**实际浏览器和投影验收未通过执行**。没有改走其他浏览器或间接导航来绕过该限制。组长应在汇报机器正常打开HTML，检查三页、附录、箭头键、全屏、断网和打印。课程总时长仍为10分钟、全员上台；老师载体许可、整组最终成品和现场计时排练尚未确认。
''')
    prepend('参考资料/方法文献/README.md','''**第五问最终方法用途（R20261031-06）：** 当前推导和适配边界见[第六环节第19节](../../研究/05_赛前实力/第六环节_清单评分敏感性与数学方法.md)与[收尾说明](../../研究/05_赛前实力/第五问_收尾与下一问交接.md)。复用Q4-P08模拟研究规范、Q5-P17/P18依赖与动态重采样条件，以及既有秩校准背景。新增Q5-P20 Howard等2020v5/2021，已读顺序推断相关部分并保存PDF；新流Bernoulli似然比与扣除旧检验错误预算的推导由项目另行给出，不冒称全文全部定理已复审。固定完整生成历史的秩论证在项目内自行列出条件，不把文献的独立同分布比赛假设套到国家队历史。最终A为固定插件模型条件参照，不是上述论文已证明本项目真实覆盖。

来源副本、在线阅读与失败下载状态仍以`sources.json`逐项登记为准；原始引用和文献版本不改写。论文写作需同时引用原文和本项目适配说明，不能仅引用当前结果图。
''')
    print('Q5_DOCUMENTS_SYNCHRONIZED',ident,flush=True)


if __name__=='__main__':run()
