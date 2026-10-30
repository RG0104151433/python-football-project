"""Check the concrete stage6 handoff, not statistical coverage."""
from pathlib import Path
import ast,csv,gzip,hashlib,io,json,re,zipfile
ROOT=Path(__file__).resolve().parents[3];log=ROOT/'outputs/logs/strength_stage6'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=0;failed=[]
def check(name,ok):
    global checks
    checks+=1
    if not ok:failed.append(name)
dp=read(log/'delivery_pointer.json');delivery=ROOT/dp['directory'];dm=read(delivery/'manifest.json');adopt=read(delivery/'adoption.json')
for name,digest in dm['outputs'].items():check('delivery:'+name,h(delivery/name)==digest)
for folder in [ROOT/adopt['preparation'],ROOT/adopt['sensitivity'],ROOT/adopt['paired']]:
    m=read(folder/'manifest.json')
    for name,digest in m['outputs'].items():
        check('output:'+name,h(folder/name)==digest)
        if '.csv' in name:
            data=(folder/name).read_bytes();data=gzip.decompress(data) if name.endswith('.gz') else data
            check('BOM_LF:'+name,data.startswith(b'\xef\xbb\xbf') and b'\r\n' not in data)
    for name,digest in m['identity']['code'].items():check('code:'+name,h(ROOT/name)==digest)
    for name,digest in m['identity']['inputs'].items():check('input:'+name,h(ROOT/name)==digest)
    with zipfile.ZipFile(folder/'source_snapshot.zip') as archive:
        for name,digest in m['identity']['code'].items():check('source_archive:'+name,hashlib.sha256(archive.read(name)).hexdigest()==digest)
for name,digest in adopt['original_data_hashes'].items():check('original_data:'+name,h(ROOT/name)==digest)
state=read(ROOT/'研究/pipeline_state.json')['question_5'];s=state['stage6']
check('same_delivery',s['delivery']==dp['directory'] and s['display_data']==adopt['display_data'])
check('completed_scope',all(s[k] for k in ['steps1_2_complete','step3_declared_sensitivity_complete','step4_mathematical_discussion_complete']))
check('not_claimed',not any(s[k] for k in ['step4_method_selected','intervals_computed','stage6_complete','score_replay','full_joint_posterior_recovered','all13_refits_repeated','actual_human_review']))
index=ROOT/'文档/05_团队协作/论文与汇报支撑材料索引.md';new=index.read_text(encoding='utf-8').split('## 第五问第四、五环节',1)[0]
for link in re.findall(r'\]\(([^)]+)\)',new):
    if '://' not in link:check('new_index_link:'+link,(index.parent/link.split('#')[0]).exists())
for name in ['README.md','研究/README.md','研究/05_赛前实力/README.md','文档/01_项目方案/研究日志与决策记录.md']:
    text=(ROOT/name).read_text(encoding='utf-8');check('current_entry:'+name,'R20261030-14' in text[:2200] and '第六环节' in text[:2200])
for name in ['src/strength_stage6_prepare.py','src/strength_stage6_sensitivity.py','scripts/prepare_strength_stage6.py','scripts/analyze_strength_stage6_sensitivity.py','scripts/audit_strength_stage6_preparation.py','scripts/audit_strength_stage6_sensitivity.py','scripts/reproduce_strength_stage6_selected.py',
             'outputs/logs/strength_stage6/retrieve_method_sources.py','outputs/logs/strength_stage6/summarize_sensitivity.py','outputs/logs/strength_stage6/finalize_handoff.py',
             'src/strength_stage6_paired.py','scripts/analyze_strength_stage6_paired.py']:
    ast.parse((ROOT/name).read_text(encoding='utf-8'));check('syntax:'+name,True)
for r in read(delivery/'source_retrieval.json'):
    check('primary_PDF:'+r['id'],r['status']=='downloaded' and h(ROOT/'参考资料/方法文献'/r['local_path'])==r['sha256'])
check('18_models_832_and576',adopt['sensitivity_refits']==13 and adopt['contrast_rows']==832 and adopt['total_new_fits']==18 and adopt['paired_rows']==576)
check('83tests',adopt['tests']==83)
prep_manifest=read(ROOT/adopt['preparation']/'manifest.json');original=ROOT/prep_manifest['identity']['protocol']['analysis']
def csvread(p):return list(csv.DictReader(io.StringIO(p.read_text(encoding='utf-8-sig'))))
old={(r['target_id'],r['reference_kind']):float(r['difference_pp']) for r in csvread(original/'contrasts.csv') if r['model_id']=='M0_nested'}
for r in csvread(ROOT/adopt['paired']/'paired_changes.csv'):
    if r['original_reference_all_scenarios_estimable']=='true':
        check('original_M0_reference_link',abs(float(r['M0_baseline_delta_same_reference_pp'])-old[r['target_id'],r['reference_kind']])<2e-8)
result=dict(passed=not failed,checks=checks,failed=failed,delivery=dp['directory'],same_artifact_and_current_documents=not failed,
            original_data_unchanged=not any(n.startswith('original_data:') for n in failed),statistical_inference_validated=False,human_review=False)
writepath=log/'final_review.json';writepath.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
if failed:raise SystemExit(1)
