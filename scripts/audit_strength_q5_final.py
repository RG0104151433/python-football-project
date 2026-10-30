"""Independent complete-history, family-calibration and final-delivery audit."""
from pathlib import Path
import argparse,csv,gzip,io,json,math,os,sys,zipfile
import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr
from scipy.stats import binom,poisson,t as student_t
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import file_hash,fingerprint,write_json
from src.strength_joint.design import Design
from src.strength_joint.contract import load


def run(materials=False,initial=False):
    log=ROOT/'outputs/logs/strength_inference';cp=json.loads((log/'comparison_pointer.json').read_text());folder=ROOT/cp['directory']
    identity=json.loads((folder/'identity.json').read_text());cfg=identity['protocol'];checks=[]
    def check(name,ok):checks.append(dict(name=name,passed=bool(ok)))
    def read(path):return list(csv.DictReader(path.open(encoding='utf-8-sig')))
    for n,h in identity['inputs'].items():check('input:'+n,file_hash(ROOT/n)==h)
    for n,h in identity['code'].items():check('original_code:'+n,file_hash(ROOT/n)==h)
    with zipfile.ZipFile(folder/'source_snapshot.zip') as source:
        import hashlib
        for n,h in identity['code'].items():check('source_snapshot:'+n,hashlib.sha256(source.read(n)).hexdigest()==h)
    extension=json.loads((folder/'numerical_extension.json').read_text())
    for n,h in extension['code'].items():check('numerical_extension:'+n,file_hash(ROOT/n)==h)
    _,facts,_,_,_=load();ids=[r['match_id'] for r in facts];x,names=Design(facts).matrix(facts,'M3_nested')
    registry=read(ROOT/'outputs/tables/strength_joint/stage6-preparation-662dd5a756b8c1bf7688/target_registry.csv')
    registry=[r for r in registry if r['family']=='F_PRIMARY_CONDITIONAL'];check('54_retained',len(registry)==54)
    chosen=[i for i,r in enumerate(registry) if r['effect_size_axis']=='level' or r['target_id'].startswith(('Q1:','Q2:'))]
    check('30_scope',len(chosen)==30)
    all_seeds=[];worlds=0;fit_worlds=0;retries=0;value_count=0;max_independent_p=0.
    confirmation={} if initial else json.loads((folder/'confirmation_result.json').read_text())
    confirmation_cfg=json.loads((ROOT/'config/strength_inference_confirmation.json').read_text())
    new_n=confirmation.get('new_worlds',0)
    for sc in cfg['scenarios']:
        truth=json.loads((folder/sc['id']/'truth.json').read_text());theta=np.array(truth['generator_M3']['theta']);eta=x@theta[:-1];b=math.exp(theta[-1])
        check('truth_rows:'+sc['id'],truth['independent_worlds']==sc['truth_seeds'][1]-sc['truth_seeds'][0])
        check('truth_convexity:'+sc['id'],truth['Hessian_min_eigenvalue']>0 and truth['pooled_gradient_max']<1e-7)
        streams={phase:sc[phase+'_seeds'] for phase in ('truth','calibration','validation')}
        if new_n and sc['id']==confirmation_cfg['scenario']:streams['confirmation']=[confirmation_cfg['seeds'][0],confirmation_cfg['seeds'][0]+new_n]
        for phase,bounds in streams.items():
            for seed in range(*bounds):
                all_seeds.append(seed);path=folder/'worlds'/sc['id']/phase/f'{seed}.npz';meta=json.loads(path.with_suffix('.json').read_text())
                check('world_hash',file_hash(path)==meta['npz_sha256'])
                check('complete_history',meta['learning_matches']==38919 and meta['study_matches']==24917 and meta['dates']==12174)
                check('same_ids',meta['exact_schedule_ids_sha256']==fingerprint(ids))
                check('same_day_order',meta['all_same_day_generated_before_update'] and meta['max_query_error']<2e-8)
                check('all_outcomes_counted',meta['home_wins']+meta['draws']+meta['away_wins']==38919)
                retries+=len(meta.get('strict_same_date_retries',[]))
                with np.load(path) as ar:
                    check('array_shapes',all(ar[k].shape==(24917,) for k in ar.files))
                    check('valid_probability',np.all((ar['true_p']>0)&(ar['true_p']<1)))
                    check('valid_variance',np.all(ar['strength_difference_base_variance']>0) and np.allclose(ar['strength_difference_variance'],ar['strength_difference_base_variance']+(ar['home_jump_intensity']+ar['away_jump_intensity'])*ar['jump_scale_sd']**2,rtol=0,atol=2e-9))
                    check('outcome_encoding',np.all((ar['outcome']>=0)&(ar['outcome']<=2)) and np.array_equal(ar['y'],ar['outcome']==0))
                    # Explicit independent Poisson sum for12 fixed positions/world.
                    for i in np.linspace(0,24916,12,dtype=int):
                        nu=ar['home_jump_intensity'][i]+ar['away_jump_intensity'][i];cap=int(poisson.isf(1e-14,nu)) if nu else 0
                        p=math.fsum(poisson.pmf(k,nu)*ndtr((eta[i]+b*ar['strength_difference'][i])/math.sqrt(1+b*b*(ar['strength_difference_base_variance'][i]+k*ar['jump_scale_sd'][i]**2))) for k in range(cap+1))
                        max_independent_p=max(max_independent_p,abs(p-ar['true_p'][i]));check('independent_generator_p',abs(p-ar['true_p'][i])<2e-9)
                    value_count+=len(ar.files)*24917
                worlds+=1
                if phase!='truth':
                    fitted=json.loads((folder/'fits'/sc['id']/phase/f'{seed}.json').read_text())
                    check('54_world_targets',len(fitted['A_error_pp'])==54 and len(fitted['B_linearized_error_pp'])==54)
                    check('actual_error_arithmetic',np.max(abs(np.array(fitted['A_estimates_pp'])-fitted['numerical_reference_pp']-np.array(fitted['A_error_pp'])))<2e-9)
                    for model,m in fitted['models'].items():
                        check('model_numerics',m['rows']==24917 and m['numerical_fit_passed'] and m['gradient']<3e-6 and m['curvature_min']>0 and not m['boundary_parameters'] and len(m['trials'])==3)
                    fit_worlds+=1
    check('all_independent_worlds',worlds==264+new_n and len(set(all_seeds))==264+new_n)
    check('all_paired_fitted_worlds',fit_worlds==184+new_n)
    check('initial_failure_retained',(folder/'failures/conditional_independent_dates/truth/710035.json').exists())
    check('strict_recovery_evidence',retries>=1)
    cal=json.loads((folder/'scope_calibration.json').read_text());scales=np.array(cal['fixed_original_scales_pp'])
    check('scale_version',file_hash(ROOT/cal['scale_source']['directory']/'diagnostic_ranges.csv')==cal['scale_table_sha256'])
    scope=json.loads((ROOT/'config/strength_inference_scope.json').read_text())
    suffix='_first_stage' if initial else ''
    decision=json.loads((folder/('scope_decision'+suffix+'.json')).read_text());summary=read(folder/('scope_method_comparison'+suffix+'.csv'))
    check('original54_not_misreported',not decision['original54_joint_admission'])
    for sc in cfg['scenarios']:
        calibration=[json.loads((folder/'fits'/sc['id']/'calibration'/f'{seed}.json').read_text()) for seed in range(*sc['calibration_seeds'])]
        validation=[json.loads((folder/'fits'/sc['id']/'validation'/f'{seed}.json').read_text()) for seed in range(*sc['validation_seeds'])]
        for route,key in [('A','A_error_pp'),('B','B_linearized_error_pp')]:
            # Python max/loops rather than main vectorized summary.
            maximum=max(max(abs(r[key][j])/scales[j] for j in chosen) for r in calibration)
            critical=maximum*1.35;check('independent_critical',abs(critical-cal['scenarios'][sc['id']]['methods'][route]['critical'])<2e-10)
            success=sum(all(abs(r['A_error_pp'][j])<=critical*scales[j] for j in chosen) for r in validation)
            saved=next(r for r in summary if r['scenario']==sc['id'] and r['route']==route)
            initial_count=saved.get('first_stage_contained') or saved['joint_contained']
            check('independent_containment',success==int(initial_count))
            n=sc['validation_seeds'][1]-sc['validation_seeds'][0];alpha=.05/4
            lo=math.exp(math.log(alpha)/n) if success==n else brentq(lambda p:binom.sf(success-1,n,p)-alpha,1e-12,1-1e-12) if success else 0.
            initial_lower=saved.get('first_stage_MC_lower') or saved['one_sided_MC_lower']
            check('independent_MC_lower',abs(lo-float(initial_lower))<2e-9)
    frozen=json.loads((folder/'confirmation_schedule.json').read_text())
    check('fresh_stream_config_frozen',file_hash(ROOT/'config/strength_inference_confirmation.json')==frozen['config_sha256'])
    check('fresh_stream_code_frozen',file_hash(ROOT/'scripts/confirm_strength_inference.py')==frozen['source_sha256'])
    check('calibration_not_revised',file_hash(folder/'scope_calibration.json')==frozen['calibration_sha256'])
    p0=confirmation_cfg['gate_probability'];q=confirmation_cfg['alternative_probability']
    remaining=confirmation_cfg['original_gate_error_budget']-p0**64
    check('four_gates_error_budget',abs(4*(p0**64+remaining)-.05)<1e-14)
    for result in confirmation.get('assessments',[]):
        critical=cal['scenarios'][result['scenario']]['methods'][result['route']]['critical']
        flags=[]
        for seed in range(confirmation_cfg['seeds'][0],confirmation_cfg['seeds'][0]+new_n):
            fit=json.loads((folder/'fits'/result['scenario']/'confirmation'/f'{seed}.json').read_text())
            flags.append(all(abs(fit['A_error_pp'][j])<=critical*scales[j] for j in chosen))
        log_e=math.fsum(math.log(q/p0) if flag else math.log((1-q)/(1-p0)) for flag in flags)
        check('fresh_worlds_only_e',sum(flags)==result['successes'] and abs(log_e-result['log_e_value'])<1e-10 and not result['old_worlds_in_e_process'])
        check('remaining_budget_threshold',abs(result['threshold']-1/remaining)<1e-8 and result['gate_passed']==(log_e>=-math.log(remaining)))
        low=brentq(lambda p:math.fsum(math.log(q/p) if flag else math.log((1-q)/(1-p)) for flag in flags)+math.log(remaining),1e-10,min(q,sum(flags)/new_n))
        check('independent_CS_inversion',abs(low-result['fresh_stream_CS_lower'])<2e-9)
    ranges=read(folder/('scope_reference_ranges'+suffix+'.csv'));check('54_output_statuses',len(ranges)==54 and {r['registry_id'] for r in ranges}=={r['registry_id'] for r in registry})
    byid={r['registry_id']:r for r in registry}
    numerical_audit=json.loads((log/'truth_audit.json').read_text());audit_by_scenario={r['scenario']:r for r in numerical_audit['details']}
    paired_indices=[i for i,r in enumerate(registry) if r['effect_size_axis']=='paired_change' and r['target_id'].startswith(('Q1:','Q2:'))]
    candidate_radii=[]
    if decision['selected_route']:
        for sc in cfg['scenarios']:
            truth=json.loads((folder/sc['id']/'truth.json').read_text());a=audit_by_scenario[sc['id']]
            mc=np.array(truth['target_MC_standard_errors_at_real_reference_pp'])
            mc[paired_indices]=np.maximum(mc[paired_indices],a['era_type_MC_jackknife_se_pp'])
            critical=cal['scenarios'][sc['id']]['methods'][decision['selected_route']]['critical']
            radius=critical*scales+student_t.isf(.01/(2*len(paired_indices)),truth['independent_worlds']-1)*mc
            radius[paired_indices]+=np.abs(a['era_type_MC_jackknife_bias_pp'])+a['independent_solver_max_target_difference_pp']
            candidate_radii.append(radius)
        expected_radius=np.array([max(values) for values in zip(*candidate_radii)])
    for j,r in enumerate(ranges):
        check('point_unchanged',abs(float(r['estimate_pp'])-float(byid[r['registry_id']]['estimate']))<2e-9)
        if r['status']=='MODEL_CONDITIONAL_REFERENCE':
            bound=100 if r['axis']=='level' else 200
            check('range_order_and_bounds',float(r['lower_pp'])<=float(r['estimate_pp'])<=float(r['upper_pp']) and abs(float(r['lower_pp']))<=bound and abs(float(r['upper_pp']))<=bound)
            check('independent_final_radius',abs(expected_radius[j]-float(r['half_width_before_logical_clip_pp']))<2e-8)
            check('independent_range_endpoints',abs(max(-bound,float(r['estimate_pp'])-expected_radius[j])-float(r['lower_pp']))<2e-8 and abs(min(bound,float(r['estimate_pp'])+expected_radius[j])-float(r['upper_pp']))<2e-8)
        else:check('unadmitted_left_empty',r['lower_pp']=='' and r['upper_pp']=='')
    for name in ('prediction_audit.json','truth_audit.json','full_fast_equivalence.json','confirmation_protocol_audit.json'):
        a=json.loads((log/name).read_text());check(name,a['passed'])
    timing=json.loads((log/'route_timing.json').read_text());check('representative_replays',timing['all_replayed_values_passed'])
    check('raw_unchanged',file_hash(ROOT/'data/raw/international_results/results.csv')=='5dcefd1aa0483979ea8378cef5be448d2005609d39945ea162378561a30a6767')
    check('clean_unchanged',file_hash(ROOT/'data/processed/prep-3fab808178cf8ad71d88/matches_clean.csv')=='69ba00073970fe011a62f5871c08ace6285d7fe75d5a0d79afdac0ef972de9dc')
    if materials:
        pointer=json.loads((ROOT/'outputs/logs/strength_q5_closeout/current.json').read_text());mf=json.loads((ROOT/pointer['directory']/'manifest.json').read_text())
        for name,h in mf['outputs'].items():check('material:'+name,file_hash(ROOT/name)==h)
        check('public_HTML',file_hash(ROOT/pointer['HTML'])==pointer['HTML_sha256'])
        check('public_paper_notes',file_hash(ROOT/pointer['document'])==pointer['document_sha256'])
        from collections import Counter
        from html.parser import HTMLParser
        import re
        dispositions=read(ROOT/pointer['directory']/'object_disposition.csv')
        all_registry=read(ROOT/'outputs/tables/strength_joint/stage6-preparation-662dd5a756b8c1bf7688/target_registry.csv')
        old_byid={r['registry_id']:r for r in all_registry}
        check('all143_disposed',len(dispositions)==143 and {r['registry_id'] for r in dispositions}==set(old_byid))
        expected_counts={'MODEL_CONDITIONAL_REFERENCE':30,'TRUTH_PRECISION_NOT_ADMITTED':24,'AUXILIARY_SENSITIVITY_ONLY':64,
            'UNSUPPORTED_EXTRAPOLATION_ONLY':10,'EXPLORATORY_NOT_CONFIRMATORY':7,'TRAINING_FIT_DESCRIPTION_ONLY':8}
        check('all143_status_counts',dict(Counter(r['status'] for r in dispositions))==expected_counts)
        for r in dispositions:
            old=old_byid[r['registry_id']]
            check('disposition_point_preserved',r['estimate']==old['estimate'] and r['unit']==old['unit'] and r['family']==old['family'])
        payload=json.loads((ROOT/pointer['directory']/'presentation_data.json').read_text())
        class Links(HTMLParser):
            def handle_starttag(self,tag,attrs):
                a=dict(attrs)
                if tag=='a' and a.get('href') and not a['href'].startswith(('https:','http:','#')):self.links.append(a['href'])
                if tag in ('script','img','link') and a.get('src',a.get('href','')).startswith(('https:','http:')):self.external.append(a)
        for page in (ROOT/pointer['HTML'],ROOT/pointer['directory']/'index.html'):
            content=page.read_text(encoding='utf-8');parser=Links();parser.links=[];parser.external=[];parser.feed(content)
            check('offline_no_external_resource',not parser.external)
            for href in parser.links:check('HTML_relative_source_link',(page.parent/href).resolve().exists())
            embedded=json.loads(re.search(r'<script id="q5-data" type="application/json">(.*?)</script>',content,re.S).group(1))
            check('HTML_same_version',embedded==payload and embedded['decision']['selected_route']==decision['selected_route'])
        browser=json.loads((ROOT/'outputs/logs/strength_q5_closeout/browser_review.json').read_text())
        check('HTML_static_and_control_review',browser['passed'] and browser['HTML_sha256']==pointer['HTML_sha256'])
        check('browser_blocker_not_hidden',not browser['actual_browser_validation'] and browser['browser_attempt_status']=='blocked_by_browser_security_policy')
        for name in ('README.md','研究/README.md','研究/05_赛前实力/README.md','文档/01_项目方案/研究日志与决策记录.md','文档/05_团队协作/论文与汇报支撑材料索引.md'):
            check('current_doc:'+name,'R20261031-06' in (ROOT/name).read_text(encoding='utf-8-sig'))
        check('Q6_prepared',(ROOT/'研究/06_历史参考周期/README.md').exists())
        forecast=json.loads((log/'prediction_pointer.json').read_text())
        forecasts=read(ROOT/forecast['directory']/'predictions.csv')
        next_ids={model:{r['match_id'] for r in forecasts if r['model_id']==model and int(r['year'])>=2000} for model in ('M0_nested','M1_strength','M3_nested')}
        check('Q6_same_16599_future_cohort',all(len(ids)==16599 for ids in next_ids.values()) and next_ids['M0_nested']==next_ids['M1_strength']==next_ids['M3_nested'])
    report=dict(passed=all(r['passed'] for r in checks),checks=len(checks),failed=[r['name'] for r in checks if not r['passed']],
        full_worlds=worlds,paired_fit_worlds=fit_worlds,independently_checked_array_values=value_count,
        independent_scalar_generator_checks=12*worlds,max_independent_generator_probability_error=float(max_independent_p),
        strict_recovery_dates=retries,materials_checked=materials,original54_joint_admitted=False,
        real_unconditional_coverage_certified=False,human_review=False,actual_browser_validation=False,source_sha256=file_hash(Path(__file__)))
    write_json(log/('q5_first_screen_audit.json' if initial else 'q5_final_audit.json' if materials else 'q5_calculation_audit.json'),report);print(json.dumps(report))
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group();g.add_argument('--materials',action='store_true');g.add_argument('--initial',action='store_true');a=p.parse_args();run(a.materials,a.initial)
