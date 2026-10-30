"""Read-only same-version handoff plus independent Poisson-sum target checks."""
from pathlib import Path
import csv
import gzip
import io
import json
import xml.etree.ElementTree as ET
import numpy as np
from scipy.special import ndtr
from scipy.stats import poisson
from src.strength.io import ROOT, read_rows
from src.strength_joint.design import Design
from src.data_contract import file_hash, write_json

base=ROOT/'outputs/logs/strength_inference'; checks=[]
def check(name,ok): checks.append(dict(name=name,passed=bool(ok)))
def records(path):
    data=path.read_bytes()
    if path.suffix=='.gz': data=gzip.decompress(data)
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))

summary=json.loads((base/'summary.json').read_text())
state=json.loads((ROOT/'研究/pipeline_state.json').read_text())['question_5']
check('current_decision',state['latest_decision_log_id']=='R20261030-16')
check('method_not_selected',not state['stage6']['development_implementation']['final_method_selected'])
check('raw_hash',summary['raw_hash']=='5dcefd1aa0483979ea8378cef5be448d2005609d39945ea162378561a30a6767')
check('clean_hash',summary['clean_hash']=='69ba00073970fe011a62f5871c08ace6285d7fe75d5a0d79afdac0ef972de9dc')
for stage in ('interface','diagnostic','pilot'):
    a=json.loads((base/(stage+'_audit.json')).read_text());check(stage+'_independent_audit',a['passed'])
    p=json.loads((base/(stage+'_pointer.json')).read_text());folder=ROOT/p['directory']
    check(stage+'_pointer',file_hash(folder/'manifest.json')==p['manifest_sha256'])
    m=json.loads((folder/'manifest.json').read_text())
    for n,h in m['outputs'].items():check(stage+':'+n,file_hash(folder/n)==h)
    for kind in ('inputs','code'):
        for n,h in m['identity'][kind].items():check(stage+':'+kind+':'+n,file_hash(ROOT/n)==h)
repeat=json.loads((base/'diagnostic_reproducibility.json').read_text())
check('three_repeat_core',len(repeat['same_core_outputs'])==3 and all(repeat['same_core_outputs'].values()))
xml=ET.parse(base/'tests.xml').getroot(); suites=list(xml.iter('testsuite'))
check('90_actual_tests',sum(int(s.get('tests','0')) for s in suites)==90)
check('tests_zero_failures',sum(int(s.get('failures','0'))+int(s.get('errors','0')) for s in suites)==0)
for p in ('README.md','研究/README.md','研究/05_赛前实力/README.md','文档/05_团队协作/论文与汇报支撑材料索引.md',
          '文档/01_项目方案/研究日志与决策记录.md','文档/05_团队协作/汇报要求与HTML方案.md'):
    check('current_doc:'+p,'R20261030-16' in (ROOT/p).read_text(encoding='utf-8-sig'))

# Independent kernel implementation: explicit Poisson sum, not production Kernel.
cfg=json.loads((ROOT/'config/strength_joint.json').read_text())
original=read_rows(ROOT/cfg['input']/'analysis_matches.csv');design=Design(original)
generator=json.loads((ROOT/'outputs/tables/strength_joint/joint-analysis-55371e4d4aa3d2060190/models.json').read_text())['M3_nested']
folder=ROOT/summary['pilot']['directory'];models=json.loads((folder/'models.json').read_text())
marg=records(folder/'world_score_marginals.csv.gz'); estimates=records(folder/'world_estimates.csv')
for r in estimates:
    if r['axis']=='level':
        expected=abs(float(r['known_M3_error_pp'])) <= float(r['B365_diagnostic_half_width_pp'])
        check('containment_boolean_and_arithmetic',r['diagnostic_contains_known_truth'].casefold()==str(expected).casefold())
original_index={r['match_id']:r for r in original}
def probabilities(result,rr):
    x,names=design.matrix(rr,result['model_id']); check('independent_column_order',names==result['names'])
    theta=np.array(result['theta']);eta=x@theta[:x.shape[1]]
    if result['model_id']=='M0_nested':return ndtr(eta)
    b=np.exp(theta[-1]);mu=np.array([float(r['strength_difference']) for r in rr])
    nu=np.array([float(r['home_jump_intensity'])+float(r['away_jump_intensity']) for r in rr])
    v0=np.array([float(r['strength_difference_base_variance']) for r in rr]);sd=np.array([float(r['jump_scale_sd']) for r in rr])
    cap=int(poisson.isf(1e-14,float(max(nu)))) if max(nu)>0 else 0
    total=np.zeros(len(rr))
    for n in range(cap+1):total+=poisson.pmf(n,nu)*ndtr((eta+b*mu)/np.sqrt(1+b*b*(v0+n*sd*sd)))
    return total

targets=[('Q1:2010s_minus_1980s:adjusted','era','2010s','1980s'),
         ('Q1:2020_2024_minus_1980s:adjusted','era','2020_2024','1980s'),
         ('Q2:difference:overall:all:era_standardized','tournament_group','friendly','non_friendly')]
independent_errors=[]
for seed,mm in models.items():
    rows=[dict(original_index[r['match_id']],**{k:v for k,v in r.items() if k!='seed'}) for r in marg if r['seed']==seed]
    for model,result in mm.items():
        p=probabilities(result,rows);y=np.array([float(r['home_win']) for r in rows])
        loss=-float(np.mean(np.where(y>0,np.log(p),np.log1p(-p))))
        check('independent_loss:'+seed+':'+model,abs(loss-result['loss'])<2e-8)
    for tid,field,first,second in targets:
        deltas={}
        for name,result in [('generator',generator),*mm.items()]:
            deltas[name]=100*(probabilities(result,[dict(r,**{field:first}) for r in rows]).mean()-probabilities(result,[dict(r,**{field:second}) for r in rows]).mean())
        for r in (r for r in estimates if r['seed']==seed and r['target_id']==tid):
            if r['axis']=='level':
                err=abs(deltas['generator']-float(r['known_M3_truth_pp']));check('independent_known_target',err<2e-8)
                errfit=abs(deltas['M3_nested']-float(r['estimate_pp']))
            else:errfit=abs(deltas['M3_nested']-deltas['M0_nested']-float(r['estimate_pp']))
            check('independent_target:'+seed+':'+r['registry_id'],errfit<2e-8)
            independent_errors.append(errfit)
report=dict(passed=all(c['passed'] for c in checks),checks=len(checks),failed=[c['name'] for c in checks if not c['passed']],
    independent_selected_target_errors_pp=independent_errors,
    independent_target_scope='three predeclared era/type targets x two axes x two worlds; explicit Poisson sum, b0 ordinary probit',
    formal_coverage_admitted=False, final_method_selected=False, human_review=False,
    review_source_sha256=file_hash(Path(__file__)))
write_json(base/'handoff_review.json',report);print(json.dumps(report))
if not report['passed']:raise SystemExit(1)
