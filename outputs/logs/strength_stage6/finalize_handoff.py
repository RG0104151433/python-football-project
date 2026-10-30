"""Bind completed numerical evidence and synchronize current research entrances."""
from pathlib import Path
import csv,io,json,hashlib,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
log=ROOT/'outputs/logs/strength_stage6';summary=read(log/'sensitivity_summary.json');sd=ROOT/summary['directory'];sp=read(sd/'manifest.json');pd=ROOT/sp['identity']['protocol']['preparation'];pm=read(pd/'manifest.json')
paired=ROOT/read(log/'paired_pointer.json')['directory'];paired_manifest=read(paired/'manifest.json')
pa=log/(pd.name+'-audit.json');sa=log/(sd.name+'-audit.json')
proofs={'preparation_audit.json':pa,'preparation_reproducibility.json':log/'reproducibility.json',
        'sensitivity_audit.json':sa,'selected_refit_reproducibility.json':log/'selected_refit_reproducibility.json',
        'sensitivity_summary.json':log/'sensitivity_summary.json','source_retrieval.json':log/'source_retrieval.json',
        'tests.xml':log/'combined_tests.xml','paired_audit.json':log/'paired_audit.json','paired_reproducibility.json':log/'paired_reproducibility.json','paired_summary.json':log/'paired_summary.json'}
for name,path in proofs.items():
    if not path.exists():raise ValueError('Missing evidence:'+name)
for p in [pa,sa,proofs['preparation_reproducibility.json'],proofs['selected_refit_reproducibility.json'],proofs['paired_audit.json'],proofs['paired_reproducibility.json']]:
    if not read(p)['passed']:raise ValueError('Failed evidence:'+str(p))
tests=ET.fromstring(proofs['tests.xml'].read_bytes());suite=tests.find('testsuite')
if int(suite.attrib['tests'])!=83 or any(int(suite.attrib[k]) for k in ['failures','errors','skipped']):raise ValueError('Tests incomplete')
for folder,manifest in [(pd,pm),(sd,sp),(paired,paired_manifest)]:
    for name,digest in manifest['outputs'].items():
        if h(folder/name)!=digest:raise ValueError('Artifact changed:'+name)
expected={'data/raw/international_results/results.csv':'5dcefd1aa0483979ea8378cef5be448d2005609d39945ea162378561a30a6767',
          'data/processed/prep-3fab808178cf8ad71d88/matches_clean.csv':'69ba00073970fe011a62f5871c08ace6285d7fe75d5a0d79afdac0ef972de9dc'}
for name,digest in expected.items():
    if h(ROOT/name)!=digest:raise ValueError('Original data changed:'+name)
identity=dict(preparation_manifest_sha256=h(pd/'manifest.json'),sensitivity_manifest_sha256=h(sd/'manifest.json'),paired_manifest_sha256=h(paired/'manifest.json'),proofs={n:h(p) for n,p in proofs.items()})
ident='delivery-'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20];delivery=log/ident
doc='研究/05_赛前实力/第六环节_清单评分敏感性与数学方法.md'
display=dict(decision_log_id='R20261030-14',preparation=pd.relative_to(ROOT).as_posix(),sensitivity=summary['directory'],paired=paired.relative_to(ROOT).as_posix(),
             original_point_analysis='outputs/tables/strength_joint/joint-analysis-55371e4d4aa3d2060190',
             original_interpretation='outputs/tables/strength_joint/strength-interpretation-35a760de1ec558401703',
             stage6_steps=dict(step1='completed',step2='completed',step3='declared_sensitivity_complete',step4='mathematical_discussion_only'),
             targets=dict(registry=143,primary_conditional=54,auxiliary=64,original_missing_extrapolation=10,exploratory_objects=7,descriptive_only=8),
             conclusion_notes=[
                 'M3 four score variants:26 of27 original primary full-reference contrasts retain baseline sign; north-minus-south Europe flips close to zero under initialization variance0.5.',
                 'Geographical magnitudes can change materially; all ranges are sensitivity ranges, not confidence intervals.',
                 'Unknown-geography and combined exclusion each require39 new reference estimands; original unidentified values stay empty.',
                 'Friendly strength relation remains an exploratory model scenario; no causal, significance or future-prediction claim.'
             ],
             model_summaries=summary['model_summaries'],relation_points=summary['relation_points'],strength_slopes=summary['strength_slopes'],
             paired_summary=read(log/'paired_summary.json'),
             plot_policy='Use existing point-analysis figures with stage6 sensitivity caveats; no confidence bars or significance stars',
             formula_and_scope_document=doc,formal_inference_admitted=False,stage6_complete=False,actual_human_review=False)
adoption=dict(decision_log_id='R20261030-14',purpose='Adopt preparation and declared sensitivity diagnostics, not replace baseline or admit intervals',
              identity=identity,preparation=pd.relative_to(ROOT).as_posix(),sensitivity=summary['directory'],
              study_population=24917,registry_rows=143,sensitivity_refits=13,contrast_rows=832,paired=paired.relative_to(ROOT).as_posix(),additional_M0_fits=5,total_new_fits=18,paired_rows=576,
              tests=83,preparation_audit_checks=read(pa)['checks'],sensitivity_audit_checks=read(sa)['checks'],
              preparation_repeated_outputs=14,sensitivity_repeated_selected_fits=2,all13_refits_repeated=False,paired_outputs_repeated=len(paired_manifest['outputs']),paired_audit_checks=read(proofs['paired_audit.json'])['checks'],
              no_new_rating_runs=True,no_formal_intervals=True,no_prospective_validation=True,no_human_review=True,
              stage6_complete=False,mathematical_method_selected=False,original_data_hashes=expected,
              display_data=(delivery/'display_data.json').relative_to(ROOT).as_posix(),document=doc)
payload={name:p.read_bytes() for name,p in proofs.items()}
for name,obj in {'adoption.json':adoption,'display_data.json':display}.items():payload[name]=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
for name,data in payload.items():
    path=delivery/name
    if path.exists() and path.read_bytes()!=data:raise ValueError('Immutable delivery collision')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
write(delivery/'manifest.json',dict(identity=identity,outputs={name:h(delivery/name) for name in payload}))
write(log/'delivery_pointer.json',dict(directory=delivery.relative_to(ROOT).as_posix(),manifest_sha256=h(delivery/'manifest.json')))

# Insert actual run record; do not change the original result packages.
labels={'repaired-initialization-d1f3771999bd8731b716':'1960起点','repaired-initialization-1dc37caeddc61830a0af':'初始方差0.5','repaired-initialization-146d3bc167c27a4a3466':'初始方差2','weak_jump':'弱跳变',
        'exclude_cold_start':'排除冷启动','exclude_previously_disconnected':'排除此前图不连通','exclude_unknown_geography':'排除地理未知','exclude_history_or_geography_flags':'排除历史/地理标记并集','exclude_initialization_mean_sensitive':'排除原均值初始化敏感'}
lines=['### 第三步实际运行补记（R20261030-14）','',f'结果包：`{summary["directory"]}/`。13次拟合和832条对比均已产出，具体数值门槛通过；另以`{paired.relative_to(ROOT).as_posix()}/`补五个同估计行M0模型和576条配对变化，共18次新拟合。原目标不再可估的行仍留空，新共同可估参考明确另编号。本轮不改1950/方差1的主版本，不按结果挑评分器。','']
for r in summary['model_summaries']:
    tops=r['top_primary_changes'];impact=f'{abs(tops[0]["change_pp"]):.4f}个百分点' if tops else '原主要目标无可直接比较值'
    lines.append(f'- {labels[r["variant_id"]]}，{r["model_id"]}：估计{r["estimation_rows"]}场；64个参考目标中原目标可估{r["original_estimable"]}个、另立新参考{r["new_reference_targets"]}个。原主要全参考可比较{r["primary_original_estimable"]}项，方向改变{len(r["primary_sign_flips"])}项，最大绝对变化{impact}。M4的主要目标数量仅沿用同一比较名单，不升格为主检验模型。')
lines+=['','范围变体的最大变化如果来自另立的新参考，应只和该新参考上的基准比较，不能与原全参考直接连成敏感性范围。所有模型系数、回顾性拟合概率、新参考成员和未可估状态均已保存。']
for r in summary['mean_only_comparison']:lines.append(f'- {labels[r["fit_id"].split(":")[0]]}：完整边际与此前仅改均值的结果最大相差{r["maximum_abs_difference_from_old_mean_only_pp"]:.4f}个百分点。两种计算保留为不同诊断，不能互相冒充。')
lines+=['',f'验证：全套83测试、准备{read(pa)["checks"]:,}项、13模型敏感性{read(sa)["checks"]:,}项、配对补算{read(proofs["paired_audit.json"])["checks"]:,}项独立核对通过。准备14产物及清单重复字节一致；13模型包只独立重跑两种代表拟合（三起点各自重复），未声称13种拟合全部重复；配对补算的五拟合及全部产物/清单重复一致。相关证据固化于`{delivery.relative_to(ROOT).as_posix()}/`。',
        '',f'统一展示取数：`{adoption["display_data"]}`。它保留全部敏感性，不带统计区间或显著性；原第四五环节图继续作为点估计展示材料，制作最终HTML时须加本轮范围说明。']
text=(ROOT/doc).read_text(encoding='utf-8');placeholder='第三步的实际结果和交付数字见本节后续的运行补记；未写入前不以设计代替运行成果。'
if placeholder in text:text=text.replace(placeholder,'\n'.join(lines))
else:raise ValueError('Actual-results insertion already occurred or source changed')
(ROOT/doc).write_text(text,encoding='utf-8')
brief=f'**第五问第六环节已完成第一至第三步，第四步进入数学讨论（R20261030-14）：** [清单、评分敏感性与数学方法]({doc})登记143对象，补齐五套逐场边际；13次敏感性拟合/832条对比，加五个M0拟合/576条配对变化，共18拟合。83测试，准备{read(pa)["checks"]:,}项、敏感性{read(sa)["checks"]:,}项、配对{read(proofs["paired_audit.json"])["checks"]:,}项独立核对通过；准备14产物重跑一致，13模型包两代表拟合重复，五M0配对包全部重复。未新增评分、正式区间、未来验证或真人复核；相依/反馈/覆盖协议及验收仍未完成，不能宣布第五问全部结束。'
for path,anchor,relative in [('README.md','# 国际足球分析课程项目',''),('研究/README.md','# 研究路线、编号与当前进度','研究/'),('研究/05_赛前实力/README.md','# 第五问：赛前实力评价与调整','研究/05_赛前实力/'),('文档/01_项目方案/研究日志与决策记录.md','## 当前摘要','文档/01_项目方案/')]:
    p=ROOT/path;t=p.read_text(encoding='utf-8');link=Path(doc).relative_to('研究/05_赛前实力').as_posix() if relative=='研究/05_赛前实力/' else ('05_赛前实力/'+Path(doc).name if relative=='研究/' else ('../../'+doc if relative.startswith('文档') else doc))
    local=brief.replace(']('+doc+')',']('+link+')');t=t.replace(anchor,anchor+'\n\n'+local,1);p.write_text(t,encoding='utf-8')
for name,replacements in {
    'README.md':[('第1—5环节已完成其计算与描述，可进入第6环节（R20261030-07）','第1—5环节已完成，第6环节前三步已完成、第四步数学方法待审读（R20261030-14）')],
    '研究/README.md':[('第五问最新状态（R20261030-07）','第五问R20261030-07阶段记录')],
    '研究/05_赛前实力/README.md':[('当前状态（R20261030-07）','R20261030-07阶段记录'),('当前六环节：①目标完成','截至R20261030-07的六环节：①目标完成')]
}.items():
    p=ROOT/name;t=p.read_text(encoding='utf-8')
    for old,new in replacements:t=t.replace(old,new,1)
    p.write_text(t,encoding='utf-8')
state=read(ROOT/'研究/pipeline_state.json');q=state['question_5'];q['latest_decision_log_id']='R20261030-14';q['status']='stages1_to5_complete_stage6_steps1_to3_complete_step4_discussion'
q['goal_discussion'].update(status='joint_point_analysis_and_declared_stage6_sensitivity_completed_inference_pending',analysis_run=True,interaction_terms='Limited M4/M5 fitted; relationships exploratory; formal inference pending')
q['stage_progress']['6']=dict(status='steps1_to3_completed_step4_math_discussion',existing='registry, scope, five complete per-match marginals and declared sensitivity audited',
    outstanding=['formal method and conditional target/mean/feedback/dependence assumptions','reference randomness and historical selection scope','simulation truth, joint error control, budget and coverage protocol','formal inference implementation and acceptance'])
q['stage6']=dict(decision_log_id='R20261030-14',document=doc,delivery=delivery.relative_to(ROOT).as_posix(),preparation=pd.relative_to(ROOT).as_posix(),sensitivity=summary['directory'],
    display_data=adoption['display_data'],steps1_2_complete=True,step3_declared_sensitivity_complete=True,step4_mathematical_discussion_complete=True,step4_method_selected=False,
    registry_rows=143,score_marginal_sets=5,sensitivity_models=13,sensitivity_contrast_rows=832,additional_M0_models=5,total_new_models=18,paired_rows=576,paired=paired.relative_to(ROOT).as_posix(),paired_audit_checks=read(proofs['paired_audit.json'])['checks'],tests=83,preparation_audit_checks=read(pa)['checks'],sensitivity_audit_checks=read(sa)['checks'],
    intervals_computed=False,stage6_complete=False,score_replay=False,full_joint_posterior_recovered=False,all13_refits_repeated=False,selected_refits_repeated=2,actual_human_review=False)
write(ROOT/'研究/pipeline_state.json',state)
index=ROOT/'文档/05_团队协作/论文与汇报支撑材料索引.md';t=index.read_text(encoding='utf-8')
paper=[doc,'config/strength_stage6_preparation.json','config/strength_stage6_sensitivity.json','src/strength_stage6_prepare.py','src/strength_stage6_sensitivity.py',
       'scripts/prepare_strength_stage6.py','scripts/audit_strength_stage6_preparation.py','scripts/analyze_strength_stage6_sensitivity.py','scripts/audit_strength_stage6_sensitivity.py','scripts/reproduce_strength_stage6_selected.py',
       'tests/test_strength_stage6_prepare.py','tests/test_strength_stage6_sensitivity.py',*[str((pd/n).relative_to(ROOT)).replace('\\','/') for n in pm['outputs']],pd.relative_to(ROOT).as_posix()+'/manifest.json',
       *[str((sd/n).relative_to(ROOT)).replace('\\','/') for n in sp['outputs']],sd.relative_to(ROOT).as_posix()+'/manifest.json',
       'config/strength_stage6_paired.json','src/strength_stage6_paired.py','scripts/analyze_strength_stage6_paired.py',
       *[str((paired/n).relative_to(ROOT)).replace('\\','/') for n in paired_manifest['outputs']],paired.relative_to(ROOT).as_posix()+'/manifest.json',
       *[str((delivery/n).relative_to(ROOT)).replace('\\','/') for n in payload],delivery.relative_to(ROOT).as_posix()+'/manifest.json','参考资料/方法文献/sources.json']
for r in read(log/'source_retrieval.json'):
    if r['status']=='downloaded':paper.append('参考资料/方法文献/'+r['local_path'])
for name in paper:
    if not (ROOT/name).exists():raise ValueError('Missing index file:'+name)
entry='## 第五问第六环节｜当前论文支撑（R20261030-14）\n\n第一至第三步已运行；第四步为数学讨论。只是补充诊断，不替换原主版本，不把敏感性当置信区间；下方原第三至五环节仍是基准点估计来源。\n\n'+'\n'.join(f'- [{n}](../../{n})' for n in dict.fromkeys(paper))
entry+='\n\n## 第五问第六环节｜当前汇报素材（R20261030-14）\n\n'+'\n'.join(f'- [{n}](../../{n})' for n in [doc,adoption['display_data'],summary['directory']+'/contrasts.csv',summary['directory']+'/relation_points.csv'])+'\n\n'
t=t.replace('# 论文与汇报支撑材料索引','# 论文与汇报支撑材料索引\n\n'+entry,1);index.write_text(t,encoding='utf-8')
for name in ['研究/05_赛前实力/第四五环节_比较结果与研究解释.md','研究/05_赛前实力/第三环节_运行结果与交接.md']:
    p=ROOT/name;t=p.read_text(encoding='utf-8');first,rest=t.split('\n',1);p.write_text(first+'\n\n**后续R20261030-14：** 第六环节第一至第三步已完成，评分/估计样本敏感性和第四步数学讨论见[当前补充](第六环节_清单评分敏感性与数学方法.md)。本页保留基准点估计和当时交接，未替换为正式区间。\n'+rest,encoding='utf-8')
print(json.dumps(dict(delivery=delivery.relative_to(ROOT).as_posix(),adoption=adoption),ensure_ascii=False))
