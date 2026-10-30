"""Independent truth, two complete-feedback routes and locked comparison.

An unsuccessful admission is a valid research result. Truth precision is never
silently waived, and plug-in simulation is not a real-world coverage theorem.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import gzip,io,json,time,traceback,zipfile
import numpy as np
from scipy.linalg import block_diag
from scipy.special import ndtr
from scipy.stats import beta as beta_distribution, t as student_t
from src.data_contract import atomic_bytes,csv_bytes,file_hash,fingerprint,write_json
from src.strength.io import ROOT,environment,read_rows
from src.strength_joint.model import Kernel
from .contract import load
from . import worlds
from .fast import install_count_cache,query,FrozenTargets
from .targets import soft_probit_projection
from .methods import refit_pair,score_geometry

_CTX=None


def protocol():
    path=ROOT/'config/strength_inference_validation.json'
    cfg=json.loads(path.read_text(encoding='utf-8-sig'));c=load()
    code_paths=[*ROOT.glob('src/strength_inference/*.py'),*ROOT.glob('src/strength/*.py'),*ROOT.glob('src/strength_joint/*.py'),
        ROOT/'scripts/validate_strength_inference.py',ROOT/'src/data_contract.py',ROOT/'src/strength_stage6_sensitivity.py']
    identity=dict(protocol=cfg,inputs=c['inputs'],code={p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(code_paths) if p.exists()},
        validation_config_sha256=file_hash(path))
    directory=ROOT/'outputs/tables/strength_joint'/('inference-comparison-'+fingerprint(identity)[:20])
    directory.mkdir(parents=True,exist_ok=True)
    if not (directory/'source_snapshot.zip').exists():
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
            for name in identity['code']:z.writestr(zipfile.ZipInfo(name,(1980,1,1,0,0,0)),(ROOT/name).read_bytes())
        atomic_bytes(directory/'source_snapshot.zip',buf.getvalue())
        write_json(directory/'protocol.json',cfg);write_json(directory/'identity.json',identity)
    write_json(ROOT/'outputs/logs/strength_inference/comparison_pointer.json',dict(directory=directory.relative_to(ROOT).as_posix(),identity_sha256=file_hash(directory/'identity.json')))
    return cfg,c,directory


def initialize(cfg,folder):
    global _CTX
    c=load();install_count_cache();worlds.before_day=query
    models=json.loads((ROOT/c['cfg']['analysis']/'models.json').read_text())
    from src.strength_joint.design import Design
    _CTX=dict(c=c,cfg=cfg,folder=Path(folder),models=models,design=Design(c['rows']),
        templates={r['match_id']:r for r in c['rows']},index={r['match_id']:i for i,r in enumerate(c['rows'])},operator=None)


def cached_world(scenario,phase,seed):
    ctx=_CTX;c=ctx['c'];dest=ctx['folder']/'worlds'/scenario['id']/phase/f'{seed}.npz'
    meta_path=dest.with_suffix('.json')
    if dest.exists() and meta_path.exists():
        meta=json.loads(meta_path.read_text())
        if file_hash(dest)!=meta['npz_sha256']:raise ValueError('WORLD_CACHE_CORRUPT')
        with np.load(dest) as data:arrays={k:data[k] for k in data.files}
        return arrays,meta
    started=time.perf_counter()
    with redirect_stdout(io.StringIO()):
        rr,pp,meta=worlds.generate(c['games'],ctx['templates'],ctx['design'],ctx['models']['M3_nested'],
            c['score_parameters'],c['score_numerics'],seed,scenario['day_correlation'],scenario['draw_odds_multiplier'])
    rr.sort(key=lambda r:ctx['index'][r['match_id']]);pp=[p for p in pp if not p['auxiliary_learning']]
    pp.sort(key=lambda r:ctx['index'][r['match_id']])
    fields=['strength_difference','strength_difference_base_variance','strength_difference_variance','home_jump_intensity','away_jump_intensity','jump_scale_sd']
    arrays={k:np.array([float(r[k]) for r in rr]) for k in fields}
    arrays['y']=np.array([int(r['home_win']) for r in rr],dtype=np.int8)
    arrays['outcome']=np.array([('home','draw','away').index(r['outcome']) for r in rr],dtype=np.int8)
    arrays['true_p']=np.array([p['true_home_probability'] for p in pp])
    buf=io.BytesIO();np.savez_compressed(buf,**arrays);atomic_bytes(dest,buf.getvalue())
    meta.update(scenario=scenario['id'],phase=phase,total_generation_seconds=time.perf_counter()-started,
        npz_sha256=file_hash(dest),seed_is_independent_replication=True,exact_schedule_ids_sha256=fingerprint([r['match_id'] for r in rr]))
    write_json(meta_path,meta)
    return arrays,meta


def rows_from(arrays):
    result=[]
    for i,r in enumerate(_CTX['c']['rows']):
        row=dict(r)
        for name,values in arrays.items():
            if name not in ('true_p','y','outcome'):row[name]=float(values[i])
        row.update(home_win=int(arrays['y'][i]),outcome=('home','draw','away')[int(arrays['outcome'][i])])
        for name in ('home_variance','away_variance','home_away_covariance'):row.pop(name,None)
        result.append(row)
    return result


def task(item):
    scenario,phase,seed=item;started=time.perf_counter()
    dest=_CTX['folder']/'fits'/scenario['id']/phase/f'{seed}.json'
    try:
        arrays,meta=cached_world(scenario,phase,seed)
        if phase=='truth':return dict(seed=seed,scenario=scenario['id'],phase=phase,success=True,seconds=time.perf_counter()-started)
        if dest.exists():return dict(seed=seed,scenario=scenario['id'],phase=phase,success=True,cached=True,seconds=time.perf_counter()-started)
        rr=rows_from(arrays);c=_CTX['c']
        if _CTX['operator'] is None:_CTX['operator']=FrozenTargets(c)
        operator=_CTX['operator'];truth=json.loads((_CTX['folder']/scenario['id']/'truth.json').read_text())
        beta0=np.array(truth['theta_M0']);theta3=np.array(_CTX['models']['M3_nested']['theta'])
        fitted=refit_pair(rr,_CTX['design'],c['joint_cfg']['numerics'])
        values,_=operator.evaluate(fitted['M0_nested']['theta'],fitted['M3_nested']['theta'],rr)
        known,jac=operator.evaluate(beta0,theta3,rr,True)
        fixed=dict(M0_nested=dict(fitted['M0_nested'],theta=beta0.tolist()),M3_nested=_CTX['models']['M3_nested'])
        scores=[];hs=[];geometry={}
        for model in ('M0_nested','M3_nested'):
            score,h,diagnostic=score_geometry(fixed[model],rr,_CTX['design'])
            scores.append(score.sum(axis=0));hs.append(h);geometry[model]=diagnostic
        correction=np.linalg.solve(block_diag(*hs),np.concatenate(scores))
        error_B=jac@correction
        cov=np.array(truth['MC_covariance_M0']);p0=len(beta0)
        mc_se=np.sqrt(np.maximum(np.einsum('ij,jk,ik->i',jac[:,:p0],cov,jac[:,:p0]),0))
        # M0 drift is retained in the full-history score, not subtracted per date.
        x,_=_CTX['design'].matrix(rr,'M0_nested');eta=x@beta0;q=ndtr(eta)
        density=np.exp(-eta*eta/2)/np.sqrt(2*np.pi)
        drift=x.T@((arrays['true_p']-q)*density/(q*(1-q)))
        value=dict(seed=seed,scenario=scenario['id'],phase=phase,success=True,A_estimates_pp=values.tolist(),
            numerical_reference_pp=known.tolist(),A_error_pp=(values-known).tolist(),B_linearized_error_pp=error_B.tolist(),
            truth_MC_standard_errors_pp=mc_se.tolist(),M0_predictable_total_score_drift_norm=float(np.linalg.norm(drift)),
            geometry=geometry,models=fitted,seconds=time.perf_counter()-started,
            role='plugin_model_conditional_comparison; truth MC approximation reported separately')
        write_json(dest,value)
        return dict(seed=seed,scenario=scenario['id'],phase=phase,success=True,seconds=value['seconds'])
    except Exception as error:
        failure=dict(seed=seed,scenario=scenario['id'],phase=phase,success=False,error_type=type(error).__name__,
            error=str(error),traceback=traceback.format_exc(),seconds=time.perf_counter()-started)
        write_json(_CTX['folder']/'failures'/scenario['id']/phase/f'{seed}.json',failure)
        return failure


def run_pool(cfg,folder,phase,workers,scenario_id=None):
    tasks=[]
    for sc in cfg['scenarios']:
        if scenario_id and sc['id']!=scenario_id:continue
        begin,end=sc[phase+'_seeds']
        tasks.extend((sc,phase,seed) for seed in range(begin,end))
    records=[];started=time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize,initargs=(cfg,str(folder))) as executor:
        pending={executor.submit(task,item):item for item in tasks}
        for future in as_completed(pending):
            result=future.result();records.append(result)
            print('COMPARISON_WORLD',phase,result['scenario'],result['seed'],result['success'],round(result['seconds'],2),len(records),'/',len(tasks),flush=True)
    records.sort(key=lambda r:(r['scenario'],r['seed']))
    write_json(folder/(phase+'_execution.json'),dict(planned=len(tasks),attempts=len(records),successes=sum(r['success'] for r in records),
        failures=sum(not r['success'] for r in records),records=records,wall_seconds=time.perf_counter()-started,workers=workers))
    return records


def make_truth(cfg,c,folder,scenario_id=None):
    operator=FrozenTargets(c);x=operator.x;output=[]
    for sc in cfg['scenarios']:
        if scenario_id and sc['id']!=scenario_id:continue
        begin,end=sc['truth_seeds'];probabilities=[]
        for seed in range(begin,end):
            path=folder/'worlds'/sc['id']/'truth'/f'{seed}.npz'
            if not path.exists():raise ValueError('TRUTH_WORLD_MISSING: '+str(path))
            with np.load(path) as ar:probabilities.append(ar['true_p'])
        ps=np.array(probabilities);pooled=soft_probit_projection(x,ps.mean(axis=0));theta=np.array(pooled['theta'])
        eta=x@theta;q=ndtr(eta);phi=np.exp(-eta*eta/2)/np.sqrt(2*np.pi)
        lp=phi/q;lq=phi/(1-q);h=ps.mean(axis=0)*lp*(eta+lp)+(1-ps.mean(axis=0))*lq*(lq-eta)
        bread=(x.T*h)@x/len(x)
        soft_scores=(ps-q)@(x*(phi/(q*(1-q)))[:,None])/len(x)
        parameter_influences=np.linalg.solve(bread,soft_scores.T).T
        covariance=np.cov(parameter_influences,rowvar=False,ddof=1)/len(ps)
        models=json.loads((ROOT/c['cfg']['analysis']/'models.json').read_text());_,jac=operator.evaluate(theta,models['M3_nested']['theta'],c['rows'],True)
        grad0=jac[:,:len(theta)];se=np.sqrt(np.maximum(np.einsum('ij,jk,ik->i',grad0,covariance,grad0),0))
        halves=[soft_probit_projection(x,p.mean(axis=0))['theta'] for p in np.array_split(ps,2)]
        projected=[]
        for beta0 in halves:projected.append(operator.evaluate(beta0,models['M3_nested']['theta'],c['rows'])[0])
        half_difference=max(abs(projected[0]-projected[1]))
        truth=dict(scenario=sc['id'],independent_worlds=len(ps),theta_M0=theta.tolist(),
            generator_M3=models['M3_nested'],MC_covariance_M0=covariance.tolist(),
            pooled_gradient_max=pooled['gradient_max'],Hessian_min_eigenvalue=float(np.linalg.eigvalsh(bread).min()),
            target_MC_standard_errors_at_real_reference_pp=se.tolist(),max_target_MC_se_pp=float(max(se)),
            half_batch_max_target_difference_pp=float(half_difference),
            nominal_MC_level=cfg['truth_mc_nominal'],MC_error_law='independent-world CLT/t approximation, not finite-sample certificate',
            precision_gate_passed=bool(max(se)<=cfg['truth_mc_target_max_se_pp']),
            truth_status='INDEPENDENT_NUMERICAL_REFERENCE_WITH_PROPAGATED_MC_ERROR',
            original_estimand_preserved=True,exact_M0_truth_claimed=False)
        write_json(folder/sc['id']/'truth.json',truth);output.append(truth)
        print('TRUTH_COMPLETE',sc['id'],len(ps),'maxMCSEpp',max(se),'batchdiffpp',half_difference,flush=True)
    return output


def common_scales(c):
    pointer=json.loads((ROOT/'outputs/logs/strength_inference/diagnostic_pointer.json').read_text())
    records=read_rows(ROOT/pointer['directory']/'diagnostic_ranges.csv')
    lookup={r['registry_id']:float(r['diagnostic_se_pp']) for r in records if r['bandwidth_days']=='365'}
    scale=np.array([lookup[r['registry_id']] for r in c['registry']])
    if np.any(scale<=0):raise ValueError('NONPOSITIVE_FIXED_SCALE')
    return scale


def fit_records(folder,sc,phase):
    begin,end=sc[phase+'_seeds'];out=[];failed=[]
    for seed in range(begin,end):
        path=folder/'fits'/sc['id']/phase/f'{seed}.json'
        if path.exists():out.append(json.loads(path.read_text()))
        else:failed.append(seed)
    return out,failed,end-begin


def calibrate(cfg,c,folder):
    scale=common_scales(c);result=[]
    for sc in cfg['scenarios']:
        rr,fail,n=fit_records(folder,sc,'calibration')
        if not rr:raise ValueError('NO_CALIBRATION_WORLDS')
        methods={}
        for route,key in [('A','A_error_pp'),('B','B_linearized_error_pp')]:
            e=np.array([r[key] for r in rr]);stat=np.max(abs(e/scale),axis=1)
            methods[route]=dict(critical=float(max(stat)*cfg['calibration_safety_factor']),unexpanded_max=float(max(stat)),
                calibration_worlds=len(rr),rank_model_conditional_coverage_floor=len(rr)/(len(rr)+1),
                mean_error_pp=e.mean(axis=0).tolist(),RMSE_pp=float(np.sqrt(np.mean(e*e))))
        discrepancy=np.array([r['A_error_pp'] for r in rr])-np.array([r['B_linearized_error_pp'] for r in rr])
        value=dict(scenario=sc['id'],methods=methods,scales_pp=scale.tolist(),
            A_B_paired_RMSE_pp=float(np.sqrt(np.mean(discrepancy**2))),
            normalized_A_B_paired_RMSE=float(np.sqrt(np.mean((discrepancy/scale)**2))),
            failures=fail,planned_worlds=n,rank_guarantee_scope='fixed generator, exact truth, exchangeable next world and pre-fixed scales only; not plug-in real-world confidence theorem')
        write_json(folder/sc['id']/'calibration.json',value);result.append(value)
    return result


def evaluate(cfg,c,folder):
    output=[];delta=cfg['mc_family_alpha']/cfg['mc_gates'];alpha_truth=1-cfg['truth_mc_nominal']
    for sc in cfg['scenarios']:
        rr,fail,n=fit_records(folder,sc,'validation');cal=json.loads((folder/sc['id']/'calibration.json').read_text());truth=json.loads((folder/sc['id']/'truth.json').read_text())
        scale=np.array(cal['scales_pp']);mc_critical=float(student_t.ppf(1-alpha_truth/(2*27),truth['independent_worlds']-1))
        errors=np.array([r['A_error_pp'] for r in rr]);mc=np.array([r['truth_MC_standard_errors_pp'] for r in rr])*mc_critical
        for route in ('A','B'):
            half=cal['methods'][route]['critical']*scale
            strict=np.all(abs(errors)+mc<=half,axis=1);point=np.all(abs(errors)<=half,axis=1)
            success=int(strict.sum());lower=float(beta_distribution.ppf(delta,success,n-success+1)) if success else 0.
            failed_fraction=len(fail)/n;failure_upper=float(beta_distribution.ppf(1-delta,len(fail)+1,n-len(fail))) if len(fail)<n else 1.
            admitted=bool(truth['precision_gate_passed'] and lower>=cfg['coverage_gate_lower'] and failed_fraction<=cfg['numerical_failure_point_gate'])
            row=dict(scenario=sc['id'],route=route,planned=n,delivered=len(rr),failures=len(fail),
                point_truth_joint_containment=int(point.sum()),conservative_MC_truth_joint_containment=success,
                strict_joint_containment_rate=success/n,one_sided_MC_lower=lower,
                numerical_failure_fraction=failed_fraction,numerical_failure_MC_upper=failure_upper,
                truth_precision_passed=truth['precision_gate_passed'],truth_max_MC_se_pp=truth['max_target_MC_se_pp'],
                median_half_width_pp=float(np.median(half)),max_half_width_pp=float(max(half)),admitted=admitted,
                original54_targets=True,MC_truth_error_certified_finite_sample=False)
            output.append(row)
    selected='A' if all(r['admitted'] for r in output if r['route']=='A') else None
    # B is not automatically substituted just because it happens to look narrower.
    decision=dict(selected_route=selected,formal_original54_admitted=selected is not None,
        status='MODEL_CONDITIONAL_APPROXIMATE_ADMISSION' if selected else 'NO_FORMAL_ORIGINAL54_ADMISSION',
        evidence=output,unknown_football_law_certified=False,selection_adjustment=False,
        real_future_accuracy_claim=False,reason='nonlinear complete replay preferred; every original-family truth/coverage gate must pass',
        scientific_work_can_conclude_with_nonadmission=True)
    write_json(folder/'method_decision.json',decision)
    atomic_bytes(folder/'method_comparison.csv',csv_bytes(list(output[0]),output))
    return decision


def publish_manifest(cfg,c,folder):
    outputs={p.relative_to(folder).as_posix():file_hash(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    write_json(folder/'manifest.json',dict(schema_version='strength-comparison-delivery-v2',protocol=cfg,
        inputs=c['inputs'],outputs=outputs,environment=environment(),actual_human_review=False,
        executed_utc=datetime.now(timezone.utc).isoformat()))


def run(phase,workers=None,scenario_id=None):
    cfg,c,folder=protocol();workers=workers or cfg['workers']
    if phase in ('truth','all'):
        run_pool(cfg,folder,'truth',workers,scenario_id);make_truth(cfg,c,folder,scenario_id)
    if phase in ('calibration','all'):
        run_pool(cfg,folder,'calibration',workers,scenario_id)
        if scenario_id is None:calibrate(cfg,c,folder)
    if phase in ('validation','all'):
        run_pool(cfg,folder,'validation',workers,scenario_id)
        if scenario_id is None:evaluate(cfg,c,folder)
    if phase=='summarize':calibrate(cfg,c,folder);evaluate(cfg,c,folder)
    publish_manifest(cfg,c,folder)
    print('COMPARISON_PHASE_COMPLETE',phase,folder.relative_to(ROOT).as_posix(),flush=True)
