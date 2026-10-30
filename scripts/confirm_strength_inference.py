"""Fresh-stream e-process; exact first-screen error is charged to the budget."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,json,math,os,sys,time
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.optimize import brentq
from src.data_contract import write_json,file_hash,atomic_bytes
from src.strength_inference import comparison
from scripts.run_strength_inference_final import initialize,task


def summarize(folder,config,n):
    cal=json.loads((folder/'scope_calibration.json').read_text());scenario=config['scenario']
    scales=np.array(cal['fixed_original_scales_pp']);ids=cal['scenarios'][scenario]['registry_ids']
    registry=__import__('csv').DictReader((ROOT/'outputs/tables/strength_joint/stage6-preparation-662dd5a756b8c1bf7688/target_registry.csv').open(encoding='utf-8-sig'))
    primary=[r for r in registry if r['family']=='F_PRIMARY_CONDITIONAL'];mask=np.array([r['registry_id'] in ids for r in primary])
    p0=config['gate_probability'];q=config['alternative_probability'];budget=config['original_gate_error_budget']-p0**config['first_stage_worlds']
    output=[];start=config['seeds'][0];numerical_failures=0
    for route in ('A','B'):
        half=cal['scenarios'][scenario]['methods'][route]['critical']*scales;successes=[];failures=0
        for seed in range(start,start+n):
            path=folder/'fits'/scenario/'confirmation'/f'{seed}.json'
            if path.exists():
                r=json.loads(path.read_text());contained=bool(np.all(abs(np.array(r['A_error_pp'])[mask])<=half[mask]))
            elif (folder/'failures'/scenario/'confirmation'/f'{seed}.json').exists():contained=False;failures+=1
            else:raise ValueError('NEW_STREAM_INCOMPLETE: '+str(seed))
            successes.append(contained)
        k=sum(successes);log_e=k*math.log(q/p0)+(n-k)*math.log((1-q)/(1-p0));passed=log_e>=-math.log(budget)
        # The inversion uses a FIXED new-stream budget, no reuse of first-stage trials.
        def log_e_at(p):return k*math.log(q/p)+(n-k)*math.log((1-q)/(1-p))
        limit=min(q,k/n) if k else 1e-12
        lower=brentq(lambda p:log_e_at(p)+math.log(budget),1e-12,limit) if k and log_e_at(limit)<-math.log(budget) else 0.
        output.append(dict(route=route,scenario=scenario,new_worlds=n,successes=k,numerical_failures=failures,
            log_e_value=log_e,e_value=math.exp(log_e),threshold=1/budget,fresh_error_budget=budget,
            first_screen_actual_error=p0**64,combined_error_bound=p0**64+budget,
            fresh_stream_CS_lower=lower,gate_passed=bool(passed and failures/n<=.01),
            old_worlds_in_e_process=False,original_critical_and_scales_unchanged=True))
        numerical_failures=max(numerical_failures,failures)
    return dict(decision_log_id=config['decision_log_id'],schema_version=config['schema_version'],
        first_stage_failed_result_preserved=True,new_worlds=n,assessments=output,
        all_routes_passed=all(r['gate_passed'] for r in output),max_worlds=config['seeds'][1]-start,
        current_stop='both_passed' if all(r['gate_passed'] for r in output) else 'maximum_reached' if n==config['seeds'][1]-start else 'continue_to_next_fixed_look',
        conditional_generator_only=True,numerical_failures=numerical_failures)


def run(workers):
    cfg,c,folder=comparison.protocol();config=json.loads((ROOT/'config/strength_inference_confirmation.json').read_text())
    for name in ('scope_decision.json','scope_method_comparison.csv','scope_reference_ranges.csv'):
        dest=folder/(name.rsplit('.',1)[0]+'_first_stage.'+name.rsplit('.',1)[1])
        if not dest.exists():atomic_bytes(dest,(folder/name).read_bytes())
    source=ROOT/'scripts/confirm_strength_inference.py'
    frozen=dict(config=config,config_sha256=file_hash(ROOT/'config/strength_inference_confirmation.json'),source_sha256=file_hash(source),
        calibration_sha256=file_hash(folder/'scope_calibration.json'),comparison_identity_sha256=file_hash(folder/'identity.json'))
    schedule=folder/'confirmation_schedule.json'
    if schedule.exists() and json.loads(schedule.read_text())!=frozen:raise ValueError('CONFIRMATION_PROTOCOL_CHANGED')
    write_json(schedule,frozen)
    scenario=next(sc for sc in cfg['scenarios'] if sc['id']==config['scenario']);start=config['seeds'][0];began=time.perf_counter();executions=[]
    for n in config['look_sizes']:
        items=[(scenario,'confirmation',seed) for seed in range(start,start+n) if not (folder/'fits'/scenario['id']/'confirmation'/f'{seed}.json').exists() and not (folder/'failures'/scenario['id']/'confirmation'/f'{seed}.json').exists()]
        if items:
            with ProcessPoolExecutor(max_workers=workers,initializer=initialize,initargs=(cfg,str(folder))) as pool:
                for future in as_completed([pool.submit(task,item) for item in items]):
                    r=future.result();executions.append(r);print('FRESH_CONFIRMATION_WORLD',r['seed'],r['success'],round(r['seconds'],2),len(executions),flush=True)
        report=summarize(folder,config,n);write_json(folder/'confirmation_result.json',report)
        write_json(folder/f'confirmation_look_{n}.json',report)
        write_json(folder/'confirmation_execution.json',dict(records=executions,wall_seconds=time.perf_counter()-began,workers=workers))
        print('FRESH_CONFIRMATION_LOOK',json.dumps(report),flush=True)
        if report['all_routes_passed']:break
    comparison.publish_manifest(cfg,c,folder)
    print('FRESH_CONFIRMATION_COMPLETE',report['current_stop'],report['new_worlds'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=16);run(p.parse_args().workers)
