"""Full same-seed equivalence against the R16 saved 38919-match history."""
from pathlib import Path
import json,os,sys
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength_inference.contract import load
from src.strength_inference import worlds
from src.strength_inference.fast import install_count_cache,query
from src.strength_inference_numerics import ReliableJumpFilter,RETRY_EVENTS
from src.strength_joint.design import Design
from src.strength_stage6_sensitivity import read
from src.data_contract import write_json,file_hash

if __name__=='__main__':
    c=load();install_count_cache();worlds.before_day=query;worlds.CollapsedJumpFilter=ReliableJumpFilter
    generator=json.loads((ROOT/c['cfg']['analysis']/'models.json').read_text())['M3_nested']
    rr,pp,meta=worlds.generate(c['games'],{r['match_id']:r for r in c['rows']},Design(c['rows']),generator,c['score_parameters'],c['score_numerics'],61001)
    old=ROOT/'outputs/tables/strength_joint/inference-pilot-121f390b31e497032ff5'
    old_r={r['match_id']:r for r in read(old/'world_score_marginals.csv.gz') if r['seed']=='61001'}
    old_p={r['match_id']:r for r in read(old/'world_probabilities.csv.gz') if r['seed']=='61001'}
    fields=['strength_difference','strength_difference_base_variance','strength_difference_variance','home_jump_intensity','away_jump_intensity','jump_scale_sd']
    max_score=max(abs(float(r[k])-float(old_r[r['match_id']][k])) for r in rr for k in fields)
    max_p=max(abs(float(p[k])-float(old_p[p['match_id']][k])) for p in pp for k in ('true_home_probability','true_draw_probability','true_away_probability'))
    different=sum(p['generated_outcome']!=int(old_p[p['match_id']]['generated_outcome']) for p in pp)
    result=dict(passed=len(pp)==38919 and len(rr)==24917 and not RETRY_EVENTS and different==0 and max_score<2e-9 and max_p<2e-9,
        learning_matches=len(pp),study_matches=len(rr),different_outcomes=different,max_score_difference=max_score,
        max_WDL_probability_difference=max_p,strict_retries=len(RETRY_EVENTS),metadata=meta,
        source_sha256=file_hash(Path(__file__)),scope='actual same-seed full rerun; original saved CSV10-decimal tolerance')
    write_json(ROOT/'outputs/logs/strength_inference/full_fast_equivalence.json',result);print(json.dumps(result))
    if not result['passed']:raise SystemExit(1)
