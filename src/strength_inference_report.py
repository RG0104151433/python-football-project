"""Finalize the precision-supported reporting scope without rewriting original54.

The two fixed-generator reference envelopes are not a proof of unconditional
football confidence coverage. Ineligible original targets remain in outputs.
"""
import json
import numpy as np
from scipy.stats import beta as beta_distribution,t as student_t
from src.data_contract import csv_bytes,atomic_bytes,write_json,file_hash
from src.strength.io import ROOT
from src.strength_inference.comparison import protocol,fit_records,common_scales


def masks(c):
    level=np.array([r['effect_size_axis']=='level' for r in c['registry']])
    paired=np.array([r['effect_size_axis']=='paired_change' and r['target_id'].startswith(('Q1:','Q2:')) for r in c['registry']])
    if level.sum()!=27 or paired.sum()!=3:raise ValueError('REPORT_SCOPE_ID_MISMATCH')
    return level,paired,level|paired


def calibrate_scope(cfg,c,folder):
    scope=json.loads((ROOT/'config/strength_inference_scope.json').read_text());_,_,mask=masks(c)
    scale=common_scales(c);result={}
    for sc in cfg['scenarios']:
        rr,failed,n=fit_records(folder,sc,'calibration')
        if len(rr)!=n:raise ValueError('CALIBRATION_INCOMPLETE: '+sc['id'])
        methods={}
        for route,key in [('A','A_error_pp'),('B','B_linearized_error_pp')]:
            e=np.array([r[key] for r in rr]);stat=np.max(abs(e[:,mask]/scale[mask]),axis=1)
            methods[route]=dict(critical=float(max(stat)*cfg['calibration_safety_factor']),
                empirical_max=float(max(stat)),calibration_worlds=n,calibration_safety_factor=cfg['calibration_safety_factor'])
        difference=np.array([r['A_error_pp'] for r in rr])-np.array([r['B_linearized_error_pp'] for r in rr])
        result[sc['id']]=dict(methods=methods,targets=30,registry_ids=[r['registry_id'] for r,m in zip(c['registry'],mask) if m],
            B_normalized_approximation_RMSE=float(np.sqrt(np.mean((difference[:,mask]/scale[mask])**2))),
            B_approximation_RMSE_pp=float(np.sqrt(np.mean(difference[:,mask]**2))),
            max_rank_floor_A=n/(n+1),rank_floor_not_proved_for_B=True)
    scale_pointer=json.loads((ROOT/'outputs/logs/strength_inference/diagnostic_pointer.json').read_text())
    write_json(folder/'scope_calibration.json',dict(scope=scope,scenarios=result,
        fixed_original_scales_pp=scale.tolist(),source_config_sha256=file_hash(ROOT/'config/strength_inference_scope.json'),
        scale_source=scale_pointer,scale_table_sha256=file_hash(ROOT/scale_pointer['directory']/'diagnostic_ranges.csv')))
    return result


def evaluate_scope(cfg,c,folder):
    level,paired,mask=masks(c)
    saved_calibration=json.loads((folder/'scope_calibration.json').read_text())
    scale=np.array(saved_calibration['fixed_original_scales_pp'])
    if len(scale)!=54 or np.any(scale<=0):raise ValueError('FROZEN_SCALE_INVALID')
    calibration=saved_calibration['scenarios']
    scope=json.loads((ROOT/'config/strength_inference_scope.json').read_text());rows=[]
    truth_audit=json.loads((ROOT/'outputs/logs/strength_inference/truth_audit.json').read_text())
    if not truth_audit['passed']:raise ValueError('INDEPENDENT_TRUTH_AUDIT_REQUIRED')
    audit_by_scenario={r['scenario']:r for r in truth_audit['details']}
    candidate_radii={route:[] for route in ('A','B')}
    for sc in cfg['scenarios']:
        truth=json.loads((folder/sc['id']/'truth.json').read_text());records,failed,n=fit_records(folder,sc,'validation')
        if len(records)+len(failed)!=n:raise ValueError('VALIDATION_DENOMINATOR_MISMATCH')
        errs=np.array([r['A_error_pp'] for r in records]);mc=np.array(truth['target_MC_standard_errors_at_real_reference_pp'])
        independent=audit_by_scenario[sc['id']]
        mc[paired]=np.maximum(mc[paired],independent['era_type_MC_jackknife_se_pp'])
        truth_ok=bool(max(mc[mask])<=scope['target_precision_gate_pp'])
        tvalue=float(student_t.ppf(1-scope['MC_truth_alpha']/(2*int(paired.sum())),truth['independent_worlds']-1))
        allowance=tvalue*mc
        allowance[paired]+=np.abs(independent['era_type_MC_jackknife_bias_pp'])+independent['independent_solver_max_target_difference_pp']
        for route in ('A','B'):
            half=calibration[sc['id']]['methods'][route]['critical']*scale
            contained=np.all(abs(errs[:,mask])<=half[mask],axis=1)
            k=int(contained.sum());alpha=cfg['mc_family_alpha']/cfg['mc_gates']
            lo=float(beta_distribution.ppf(alpha,k,n-k+1)) if k else 0.
            failures=len(failed)/n;upper=float(beta_distribution.ppf(1-alpha,len(failed)+1,n-len(failed))) if len(failed)<n else 1.
            passed=truth_ok and lo>=cfg['coverage_gate_lower'] and failures<=cfg['numerical_failure_point_gate']
            candidate_radii[route].append(half+allowance)
            rows.append(dict(scenario=sc['id'],route=route,family='precision_supported30',targets=30,
                planned=n,delivered=len(records),numerical_failures=len(failed),joint_contained=k,
                joint_containment_rate=k/n,one_sided_MC_lower=lo,MC_error_probability=alpha,
                numerical_failure_rate=failures,numerical_failure_MC_upper=upper,
                max_admitted_truth_MC_se_pp=float(max(mc[mask])),truth_precision_passed=truth_ok,
                max_truth_allowance_pp=float(max(allowance[mask])),median_half_width_with_MC_pp=float(np.median((half+allowance)[mask])),
                B_normalized_approximation_RMSE=calibration[sc['id']]['B_normalized_approximation_RMSE'],
                conditional_reference_gate_passed=bool(passed)))
    confirmation_path=folder/'confirmation_result.json'
    if confirmation_path.exists():
        confirmation=json.loads(confirmation_path.read_text())
        frozen=json.loads((folder/'confirmation_schedule.json').read_text())
        if file_hash(ROOT/'config/strength_inference_confirmation.json')!=frozen['config_sha256'] or file_hash(ROOT/'scripts/confirm_strength_inference.py')!=frozen['source_sha256'] or file_hash(folder/'scope_calibration.json')!=frozen['calibration_sha256']:
            raise ValueError('CONFIRMATION_FROZEN_INPUT_CHANGED')
        for result in confirmation['assessments']:
            row=next(r for r in rows if r['scenario']==result['scenario'] and r['route']==result['route'])
            row.update(first_stage_planned=row['planned'],first_stage_contained=row['joint_contained'],
                first_stage_MC_lower=row['one_sided_MC_lower'],first_stage_gate_passed=row['conditional_reference_gate_passed'],
                initial_failure_MC_upper=row['numerical_failure_MC_upper'],new_stream_worlds=result['new_worlds'],
                new_stream_contained=result['successes'],new_stream_e_value=result['e_value'],new_stream_e_threshold=result['threshold'],
                new_stream_error_budget=result['fresh_error_budget'],combined_false_gate_bound=result['combined_error_bound'],
                old_worlds_used_in_e_process=False,validation_evidence_kind='first screen plus independent fresh-stream e-process')
            row['planned']+=result['new_worlds'];row['delivered']+=result['new_worlds']-result['numerical_failures']
            row['joint_contained']+=result['successes'];row['numerical_failures']+=result['numerical_failures']
            row['joint_containment_rate']=row['joint_contained']/row['planned']
            row['numerical_failure_rate']=row['numerical_failures']/row['planned']
            row['numerical_failure_MC_upper']=None
            row['failure_upper_scope']='initial64 exact upper retained separately; no optional-N failure upper certified'
            row['one_sided_MC_lower']=result['fresh_stream_CS_lower']
            row['MC_error_probability']=result['fresh_error_budget']
            row['conditional_reference_gate_passed']=bool(row['truth_precision_passed'] and result['gate_passed'] and row['numerical_failure_rate']<=cfg['numerical_failure_point_gate'])
    for row in rows:
        row.setdefault('validation_evidence_kind','initial fixed64 exact binomial gate')
    a_ok=all(r['conditional_reference_gate_passed'] for r in rows if r['route']=='A')
    b_ok=all(r['conditional_reference_gate_passed'] and r['B_normalized_approximation_RMSE']<=scope['B_normalized_linearization_RMSE_gate'] for r in rows if r['route']=='B')
    selected='A' if a_ok else None
    # A is predeclared priority. B cannot be selected without independent cost evidence.
    timing=ROOT/'outputs/logs/strength_inference/route_timing.json'
    b_cost=False
    if timing.exists():b_cost=json.loads(timing.read_text())['B_whole_run_relative_saving']>=scope['B_whole_run_cost_advantage_required']
    if selected is None and b_ok and b_cost:selected='B'
    radii=np.max(candidate_radii[selected],axis=0) if selected else np.full(54,np.nan)
    intervals=[]
    for j,r in enumerate(c['registry']):
        admitted=bool(mask[j] and selected is not None)
        value=float(r['estimate']);bound=100 if r['effect_size_axis']=='level' else 200
        intervals.append(dict(registry_id=r['registry_id'],target_id=r['target_id'],axis=r['effect_size_axis'],
            estimate_pp=value,lower_pp=max(-bound,value-radii[j]) if admitted else None,
            upper_pp=min(bound,value+radii[j]) if admitted else None,
            half_width_before_logical_clip_pp=float(radii[j]) if admitted else None,
            reference_id=r['reference_id'],family='precision_supported30' if mask[j] else 'original_regional_change24',
            adopted_route=selected if admitted else '',status='MODEL_CONDITIONAL_REFERENCE' if admitted else
                'TRUTH_PRECISION_NOT_ADMITTED' if not mask[j] else 'METHOD_VALIDATION_NOT_ADMITTED',
            unconditional_real_coverage_certified=False,causal_effect=False))
    decision=dict(decision_log_id='R20261031-06',scope_decision_log_id='R20261031-02',confirmation_protocol_log_id='R20261031-05',selected_route=selected,candidate_family_size=30,
        model_conditional_reference_admitted=selected is not None,original54_joint_admission=False,
        admitted_targets=sum(r['status']=='MODEL_CONDITIONAL_REFERENCE' for r in intervals),
        withheld_targets=sum(r['status']!='MODEL_CONDITIONAL_REFERENCE' for r in intervals),
        assessments=rows,B_coverage_and_approximation_passed=b_ok,B_material_cost_advantage=b_cost,
        rank_guarantee_applies_to_new_fixed_generator_worlds=True,
        unconditional_football_coverage_certified=False,plugin_recalibration_per_outer_world_validated=False,
        finite_sample_MC_truth_certified=False,historical_selection_adjusted=False,
        truth_margin_guard_sha256=file_hash(ROOT/'config/strength_inference_truth_margin.json'),
        recommendation='full nonlinear A where admitted; retain B as comparison; no unsupported regional contribution claim',
        original54_estimands_preserved=True,human_review=False)
    write_json(folder/'scope_decision.json',decision)
    fields=list(dict.fromkeys(key for row in rows for key in row))
    atomic_bytes(folder/'scope_method_comparison.csv',csv_bytes(fields,rows))
    atomic_bytes(folder/'scope_reference_ranges.csv',csv_bytes(list(intervals[0]),intervals))
    return decision


def run(phase):
    cfg,c,folder=protocol()
    if phase=='calibrate':value=calibrate_scope(cfg,c,folder)
    elif phase=='apply':
        value=evaluate_scope(cfg,c,folder)
        from src.strength_inference.comparison import publish_manifest
        publish_manifest(cfg,c,folder)
    else:raise ValueError('UNKNOWN_REPORT_PHASE')
    print(json.dumps(value,ensure_ascii=False),flush=True)
