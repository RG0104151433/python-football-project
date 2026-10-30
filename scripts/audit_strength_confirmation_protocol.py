"""Exact finite Bernoulli path recursion for the frozen confirmation rule."""
from pathlib import Path
import json,math,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import write_json,file_hash


def run():
    path=ROOT/'config/strength_inference_confirmation.json';c=json.loads(path.read_text());p=c['gate_probability'];q=c['alternative_probability']
    initial=p**c['first_stage_worlds'];remaining=c['original_gate_error_budget']-initial
    mass={0:1.};previous=0;hits=[]
    for n in c['look_sizes']:
        block=n-previous;updated={}
        probs=[math.comb(block,k)*p**k*(1-p)**(block-k) for k in range(block+1)]
        for old_k,weight in mass.items():
            for k,prob in enumerate(probs):updated[old_k+k]=updated.get(old_k+k,0.)+weight*prob
        hit=0.;mass={};accepted_failures=[]
        for k,weight in updated.items():
            log_e=k*math.log(q/p)+(n-k)*math.log((1-q)/(1-p))
            if log_e>=-math.log(remaining):hit+=weight;accepted_failures.append(n-k)
            else:mass[k]=weight
        hits.append(dict(n=n,additional_null_crossing_probability=hit,max_accepted_failures=max(accepted_failures,default=None)))
        previous=n
    fresh=sum(r['additional_null_crossing_probability'] for r in hits)
    total=initial+(1-initial)*fresh
    checks=dict(probability_conserved=abs(sum(mass.values())+fresh-1)<2e-12,
        fresh_rule_within_remaining=fresh<=remaining+1e-14,
        combined_single_gate_within_original=total<=c['original_gate_error_budget']+1e-14,
        all_four_within_original=4*total<=.05+1e-14,
        alternative_above_null=q>p,all_looks_in_frozen_cap=max(c['look_sizes'])==c['seeds'][1]-c['seeds'][0])
    result=dict(passed=all(checks.values()),checks=checks,first_screen_false_pass_at_null=initial,
        remaining_error_budget=remaining,fresh_exact_null_crossing_probability=fresh,
        combined_single_gate_exact_null_false_pass=total,four_gate_union_bound=4*total,look_details=hits,
        observed_fresh_world_outcomes_used=False,scope='conditional fixed generator; mathematical probability calculation only',
        config_sha256=file_hash(path),source_sha256=file_hash(Path(__file__)))
    write_json(ROOT/'outputs/logs/strength_inference/confirmation_protocol_audit.json',result);print(json.dumps(result))
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':run()
