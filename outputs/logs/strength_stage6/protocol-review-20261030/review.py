"""Read-only documentary/data-integrity review; no model or coverage experiment."""
from pathlib import Path
import ast,csv,hashlib,io,json,math,re
ROOT=Path(__file__).resolve().parents[4];log=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=0;failed=[]
def check(name,ok):
    global checks
    checks+=1
    if not ok:failed.append(name)
adoption_path=ROOT/'outputs/logs/strength_stage6/delivery-618a9dd942fad38863e6/adoption.json';adopt=read(adoption_path)
for key in ['preparation','sensitivity','paired']:
    folder=ROOT/adopt[key];manifest=read(folder/'manifest.json')
    check('unchanged_manifest:'+key,h(folder/'manifest.json')==adopt['identity'][{'preparation':'preparation_manifest_sha256','sensitivity':'sensitivity_manifest_sha256','paired':'paired_manifest_sha256'}[key]])
    for name,digest in manifest['outputs'].items():check('unchanged_result:'+key+':'+name,h(folder/name)==digest)
for name,digest in adopt['original_data_hashes'].items():check('original_data:'+name,h(ROOT/name)==digest)
prep=ROOT/adopt['preparation']
registry=list(csv.DictReader(io.StringIO((prep/'target_registry.csv').read_text(encoding='utf-8-sig'))))
curves=list(csv.DictReader(io.StringIO((prep/'curve_support.csv').read_text(encoding='utf-8-sig'))))
grid={float(r['strength_mean']) for r in curves};anchors={-2.,0.,2.}
check('143objects',len(registry)==143)
check('54primary',sum(r['family']=='F_PRIMARY_CONDITIONAL' for r in registry)==54)
check('25pointgrid',len(grid)==25 and anchors<=grid)
relation_scalars=len(grid)+1+2;all_scalars=54+64+10+relation_scalars
check('28unique_relation_scalars',relation_scalars==28)
check('156_if_all_families_formal',all_scalars==156)
old_time=read(ROOT/'outputs/logs/strength_joint/global_feedback.json')
check('old_timing_two_worlds',len(old_time['reports'])==2 and all(r['learning_matches']==38919 and r['study_matches']==24917 for r in old_time['reports']))
for path in ['src/strength_inference','scripts/analyze_strength_inference.py','scripts/audit_strength_inference.py']:
    check('planned_not_created:'+path,not (ROOT/path).exists())
state=read(ROOT/'研究/pipeline_state.json')['question_5'];review=state['stage6']['protocol_review']
check('current_status',state['latest_decision_log_id']=='R20261030-15' and review['decision_log_id']=='R20261030-15')
check('no_false_execution',not any(review[k] for k in ['thresholds_frozen','inference_package_created','new_model_fits','new_statistical_experiments','actual_human_review']))
check('old_inference_status_unchanged',not state['stage6']['intervals_computed'] and not state['stage6']['step4_method_selected'])
doc=ROOT/review['document'];text=doc.read_text(encoding='utf-8')
check('all_review_sections',all('## '+str(i)+'.' in text for i in range(11,18)))
for path in ['README.md','研究/README.md','研究/05_赛前实力/README.md','文档/01_项目方案/研究日志与决策记录.md']:
    t=(ROOT/path).read_text(encoding='utf-8');check('current_navigation:'+path,'R20261030-15' in t[:1800])
index=ROOT/'文档/05_团队协作/论文与汇报支撑材料索引.md';new=index.read_text(encoding='utf-8').split('## 第五问第六环节｜当前论文支撑',1)[0]
for link in re.findall(r'\]\(([^)]+)\)',new):check('index_link:'+link,(index.parent/link.split('#')[0]).is_file())
for link in re.findall(r'\]\(([^)]+)\)',text):
    if '://' not in link:check('document_link:'+link,(doc.parent/link.split('#')[0]).exists())
sources=read(log/'sources.json')
for r in sources['attempts']:
    if r['status']=='downloaded':check('PDF:'+r['local_path'],h(ROOT/'参考资料/方法文献'/r['local_path'])==r['sha256'])
catalog=read(ROOT/'参考资料/方法文献/sources.json');q4=next(r for r in catalog['records'] if r['id']=='Q4-P08')
check('old_failure_not_erased',q4['status']=='failed_no_local_original' and any(r['decision_log_id']=='R20261030-15' for r in q4['followup_retrievals']))
for p in log.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'));check('editorial_syntax:'+p.name,True)
result=dict(passed=not failed,checks=checks,failed=failed,decision_log_id='R20261030-15',
    unchanged_adoption=adoption_path.relative_to(ROOT).as_posix(),unchanged_adoption_sha256=h(adoption_path),
    reference_registry_objects=143,unique_relation_scalar_targets=relation_scalars,all_family_scalar_targets_if_formal=all_scalars,
    planning_arithmetic_not_new_experiments=dict(old_two_world_seconds=old_time['seconds'],old_average_world_seconds=old_time['seconds']/2,
        approximate2000world_serial_hours=old_time['seconds']/2*2000/3600,MCSE_at95coverage_2000worlds=math.sqrt(.95*.05/2000),
        proposed54target_Bonferroni_each_tail=.05/(2*54)),
    proposed_package_implemented=False,new_model_or_coverage_runs=False,old_tests_rerun=False,actual_human_review=False)
(log/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
if failed:raise SystemExit(1)
