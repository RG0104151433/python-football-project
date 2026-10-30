"""Independent arithmetic, coefficient and curve audit for Q5 stages 4/5."""
from pathlib import Path
from collections import Counter
import argparse
import json
import math
import sys
import numpy as np
from scipy.special import ndtr
from scipy.stats import poisson
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import file_hash,write_json
from src.strength.io import read_rows


def run(directory=None):
    log=ROOT/'outputs/logs/strength_interpretation'
    if directory is None:directory=json.loads((log/'current.json').read_text())['directory']
    folder=ROOT/directory;m=json.loads((folder/'manifest.json').read_text());cfg=m['identity']['protocol']
    errors=[];nchecks=0
    def check(label,ok):
        nonlocal nchecks
        nchecks+=1
        if not ok:errors.append(label)
    for name,h in m['outputs'].items():check('hash:'+name,file_hash(folder/name)==h)
    for name,h in m['identity']['inputs'].items():check('input:'+name,file_hash(ROOT/name)==h)
    for name,h in m['identity']['code'].items():check('code:'+name,file_hash(ROOT/name)==h)
    base=ROOT/cfg['analysis'];original=json.loads((base/'manifest.json').read_text());jc=original['identity']['protocol']
    rows=read_rows(ROOT/jc['input']/'analysis_matches.csv');pred=read_rows(base/'joint_predictions.csv')
    check('same24917',len(rows)==24917 and [r['match_id'] for r in rows]==[r['match_id'] for r in pred])
    y=np.array([int(r['home_win']) for r in rows]);full=read_rows(folder/'layer_comparisons.csv');groups=read_rows(folder/'layer_group_diagnostics.csv')
    for r in full:
        a=np.array([float(p[r['before_model']]) for p in pred]);b=np.array([float(p[r['after_model']]) for p in pred])
        gain=np.where(y,np.log(b)-np.log(a),np.log1p(-b)-np.log1p(-a))
        check('paired_loss:'+r['comparison_id'],abs(gain.mean()-float(r['loss_reduction']))<1e-9)
        check('paired_accuracy:'+r['comparison_id'],abs(100*np.mean(((b>=.5)==y).astype(float)-((a>=.5)==y).astype(float))-float(r['accuracy_change_pp']))<1e-8)
        for field in ('year','era','tournament_group','home_region','away_region'):
            rr=[q for q in groups if q['comparison_id']==r['comparison_id'] and q['grouping']==field]
            check('group_partition:'+r['comparison_id']+field,sum(int(q['matches']) for q in rr)==24917)
            check('group_weighted_identity:'+r['comparison_id']+field,abs(sum(int(q['matches'])*float(q['loss_reduction']) for q in rr)/24917-gain.mean())<1e-9)
            for q in rr:
                mask=np.array([(x[field] or 'unknown')==q['group'] for x in rows])
                check('group_value:'+r['comparison_id']+field+q['group'],mask.sum()==int(q['matches']) and abs(gain[mask].mean()-float(q['loss_reduction']))<1e-9)
    models=json.loads((base/'models.json').read_text())
    counters={side:Counter((r[side+'_region'],r[side+'_unit']) for r in rows) for side in ('home','away')}
    mu=np.array([float(r['strength_difference']) for r in rows]);v=np.array([float(r['strength_difference_base_variance']) for r in rows])
    nu=np.array([float(r['home_jump_intensity'])+float(r['away_jump_intensity']) for r in rows]);sd=np.array([float(r['jump_scale_sd']) for r in rows])
    def independent_eta(model,kind):
        f=models[model];theta=dict(zip(f['names']+f['slope_names'],f['theta']))
        if model=='M1_strength':return np.full(len(rows),theta['intercept']),math.exp(theta['log_b'])
        eta=np.array([theta['intercept']+theta.get('era:'+r['era'],0)+theta['friendly']*(kind=='friendly') for r in rows])
        for side in ('home','away'):
            c=counters[side];values={}
            for region,unit in c:
                units=[u for g,u in c if g==region];anchor=max(units,key=lambda u:(c[region,u],u))
                within=theta.get(side+':within:'+unit,0.) if unit!=anchor else -sum(theta.get(side+':within:'+u,0.)*c[region,u]/c[region,anchor] for u in units if u!=anchor)
                values[unit]=theta.get(side+':region:'+(region or 'unknown'),0.)+within
            eta+=np.array([values[r[side+'_unit']] for r in rows])
        b=math.exp(theta['log_b_friendly' if kind=='friendly' else 'log_b_nonfriendly']) if model=='M4_type_slope' else math.exp(theta['log_b'])
        return eta,b
    cache={(model,kind):independent_eta(model,kind) for model in cfg['curve_models'] for kind in ('friendly','non_friendly')}
    cap=int(poisson.isf(1e-14,float(nu.max())));weights=[poisson.pmf(k,nu) for k in range(cap+1)]
    curve=read_rows(folder/'strength_curves.csv')
    for r in curve:
        eta,b=cache[r['model_id'],r['tournament_group']];d=float(r['strength_mean'])
        p=sum(w*ndtr((eta+b*d)/np.sqrt(1+b*b*(v+k*sd*sd))) for k,w in enumerate(weights))
        check('curve:'+r['model_id']+r['tournament_group']+r['strength_mean'],abs(p.mean()-float(r['standardized_home_probability']))<2e-8)
        check('curve_no_interval',not r['lower'] and not r['upper'] and r['inference_status']=='INFERENCE_NOT_ADMITTED')
    for model in cfg['curve_models']:
        for kind in ('friendly','non_friendly'):
            cc=[r for r in curve if r['model_id']==model and r['tournament_group']==kind]
            check('monotonic_assumption:'+model+kind,all(float(b['standardized_home_probability'])>float(a['standardized_home_probability']) for a,b in zip(cc,cc[1:])))
    cd=read_rows(folder/'tournament_curve_differences.csv');index={(r['model_id'],r['tournament_group'],r['strength_mean']):r for r in curve}
    for r in cd:
        a=index[r['model_id'],'friendly',r['strength_mean']];b=index[r['model_id'],'non_friendly',r['strength_mean']]
        check('type_curve_difference',abs(100*(float(a['standardized_home_probability'])-float(b['standardized_home_probability']))-float(r['friendly_minus_other_pp']))<2e-8)
        if r['model_id']=='M1_strength':check('strength_only_no_type_difference',abs(float(r['friendly_minus_other_pp']))<1e-9)
    ledger=read_rows(folder/'target_evidence_ledger.csv');check('32x2ledger',len(ledger)==64)
    source=read_rows(base/'contrasts.csv');idx={(r['target_id'],r['reference_kind'],r['model_id']):r for r in source}
    for r in ledger:
        targets=[idx[r['target_id'],r['reference_kind'],model] for model in cfg['target_model_comparison']]
        values=[float(x['difference_pp']) for x in targets]
        check('same_reference',len({x['reference_id'] for x in targets})==1 and r['reference_id']==targets[0]['reference_id'])
        check('model_range_not_ci',r['model_range_is_confidence_interval']=='false' and r['significance']=='NOT_TESTED' and abs(min(values)-float(r['specified_model_min_pp']))<1e-8 and abs(max(values)-float(r['specified_model_max_pp']))<1e-8)
        check('missing_support_preserved',r['original_target_status']==targets[0]['old_target_status'])
    legacy=read_rows((ROOT/jc['facts']).parent/'group_summary.csv');legacy_counts={r['group_id']:int(r['n_matches']) for r in legacy}
    for r in read_rows(folder/'observed_score_composition.csv'):
        check('arm_count:'+r['group_id'],int(r['matches'])==legacy_counts[r['group_id']])
        check('arm_rate:'+r['group_id'],abs(int(r['home_wins'])/int(r['matches'])-float(r['observed_home_rate']))<1e-9)
    for r in read_rows(folder/'original_new_estimand_bridge.csv'):
        check('no_unlike_estimand_subtraction',not r['difference_from_original'] and r['same_estimand_as_original']=='false')
    for name in m['outputs']:
        if name.endswith('.csv'):
            content=(folder/name).read_bytes();check('csv_BOM_LF:'+name,content.startswith(b'\xef\xbb\xbf') and b'\r\n' not in content)
    scope=json.loads((folder/'scope.json').read_text());check('stage6_not_claimed',not scope['stage6_complete'] and not scope['statistical_inference'] and not scope['new_model_fits'])
    report=dict(passed=not errors,checks=nchecks,failed=errors,directory=directory,actual_human_review=False,interval_coverage_tested=False)
    write_json(log/(folder.name+'-audit.json'),report);print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',nargs='?');run(p.parse_args().directory)
