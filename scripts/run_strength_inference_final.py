"""Resume frozen comparison with deterministic strict same-date EP fallback."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import argparse,json,os,sys,time
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_inference import comparison,worlds
from src.strength_inference_numerics import ReliableJumpFilter,RETRY_EVENTS
from src.data_contract import write_json,file_hash


def initialize(cfg,folder):
    comparison.initialize(cfg,folder)
    worlds.CollapsedJumpFilter=ReliableJumpFilter


def task(item):
    RETRY_EVENTS.clear();result=comparison.task(item)
    sc,phase,seed=item;folder=comparison._CTX['folder']
    if result['success']:
        path=folder/'worlds'/sc['id']/phase/f'{seed}.json'
        meta=json.loads(path.read_text())
        if RETRY_EVENTS:
            meta['strict_same_date_retries']=list(RETRY_EVENTS);write_json(path,meta)
        result['strict_same_date_retries']=len(RETRY_EVENTS)
    return result


def pool(cfg,folder,phase,workers,only_missing=False,seeds=None):
    items=[]
    for sc in cfg['scenarios']:
        begin,end=sc[phase+'_seeds']
        for seed in range(begin,end):
            if seeds and seed not in seeds:continue
            exists=(folder/'worlds'/sc['id']/phase/f'{seed}.npz').exists() if phase=='truth' else (folder/'fits'/sc['id']/phase/f'{seed}.json').exists()
            if only_missing and exists:continue
            items.append((sc,phase,seed))
    records=[];started=time.perf_counter()
    if items:
        with ProcessPoolExecutor(max_workers=workers,initializer=initialize,initargs=(cfg,str(folder))) as executor:
            pending=[executor.submit(task,item) for item in items]
            for future in as_completed(pending):
                r=future.result();records.append(r)
                print('RELIABLE_WORLD',phase,r['scenario'],r['seed'],r['success'],round(r['seconds'],2),len(records),'/',len(items),flush=True)
    write_json(folder/(phase+'_strict_execution.json'),dict(requested=len(items),attempted=len(records),
        successes=sum(r['success'] for r in records),failures=sum(not r['success'] for r in records),records=records,
        wall_seconds=time.perf_counter()-started,previous_failures_preserved=True))
    return records


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['repair','truth','calibration','validation','all'],required=True)
    p.add_argument('--workers',type=int,default=16);p.add_argument('--seed',type=int)
    args=p.parse_args();cfg,c,folder=comparison.protocol()
    extension=dict(decision_log_id='R20261031-01',reason='default EP failed at seed710035; do not discard/reseed',
        successful_default_histories_unchanged=True,prior_state_restore=True,strict_tolerances=[1e-7,1e-8],
        attempts=[dict(damping=.25,max_iterations=1500),dict(damping=.1,max_iterations=6000)],
        code={name:file_hash(ROOT/name) for name in ['src/strength_inference_numerics.py','scripts/run_strength_inference_final.py']})
    write_json(folder/'numerical_extension.json',extension)
    if args.phase=='repair':pool(cfg,folder,'truth',args.workers,True,{args.seed} if args.seed else None)
    else:
        phases=['truth','calibration','validation'] if args.phase=='all' else [args.phase]
        for phase in phases:
            pool(cfg,folder,phase,args.workers,True)
            if phase=='truth':comparison.make_truth(cfg,c,folder)
            elif phase=='calibration':comparison.calibrate(cfg,c,folder)
            else:comparison.evaluate(cfg,c,folder)
    comparison.publish_manifest(cfg,c,folder)
    print('RELIABLE_PHASE_COMPLETE',args.phase,folder.relative_to(ROOT).as_posix(),flush=True)
