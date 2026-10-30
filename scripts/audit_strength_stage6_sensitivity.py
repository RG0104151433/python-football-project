"""Independent numerical probability and common-reference audit of step3 fits."""
from pathlib import Path
from collections import defaultdict
from fractions import Fraction
import csv,gzip,io,json,sys
import numpy as np
from scipy.special import ndtr
from scipy.stats import poisson
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.data_contract import file_hash,write_json
from src.strength.io import read_rows
from src.strength_joint.design import Design


def read(path):
    p=Path(path)
    return list(csv.DictReader(io.StringIO(gzip.decompress(p.read_bytes()).decode('utf-8-sig')))) if p.suffix=='.gz' else read_rows(p)


def run():
    log=ROOT/'outputs/logs/strength_stage6';directory=json.loads((log/'sensitivity_pointer.json').read_text())['directory'];folder=ROOT/directory
    manifest=json.loads((folder/'manifest.json').read_text());cfg=manifest['identity']['protocol'];prep=ROOT/cfg['preparation'];pm=json.loads((prep/'manifest.json').read_text())
    analysis=ROOT/pm['identity']['protocol']['analysis'];source=json.loads((analysis/'manifest.json').read_text());jc=source['identity']['protocol']
    original=read(ROOT/jc['input']/'analysis_matches.csv');base_index={r['match_id']:r for r in original};base_design=Design(original)
    models=json.loads((folder/'models.json').read_text());baseline_models=json.loads((analysis/'models.json').read_text())
    readiness=json.loads((prep/'readiness.json').read_text());files={r['variant_id']:r['prepared_file'] for r in readiness['score_variants']}
    score_sets={label:{r['match_id']:r for r in read(prep/file)} for label,file in files.items()}
    flags={r['match_id']:r for r in read(prep/'baseline_flags.csv.gz')};checks=0;failed=[]
    def check(name,ok):
        nonlocal checks
        checks+=1
        if not ok:failed.append(name)
    for n,h in manifest['outputs'].items():check('hash:'+n,file_hash(folder/n)==h)
    for n,h in manifest['identity']['code'].items():check('source:'+n,file_hash(ROOT/n)==h)
    for n,h in manifest['identity']['inputs'].items():check('input:'+n,file_hash(ROOT/n)==h)
    def rowset(label):
        label=label if label in score_sets else 'baseline'
        return {mid:dict(r,**{k:score_sets[label][mid][k] for k in ('strength_difference','strength_difference_variance','strength_difference_base_variance','home_jump_intensity','away_jump_intensity','jump_scale_sd')}) for mid,r in base_index.items()}
    data={key:rowset(key) for key in ['baseline',*cfg['score_variants']]}
    def independent_p(result,rows):
        x,names=base_design.matrix(rows,result['model_id']);spec=result.get('restricted_design')
        kept=spec['kept_columns'] if spec else list(range(x.shape[1]));theta=np.array(result['theta']);eta=x[:,kept]@theta[:len(kept)]
        if len(result['slope_names'])==2:
            logb=np.where(np.array([r['tournament_group']=='friendly' for r in rows]),theta[-1],theta[-2]);b=np.exp(logb)
        else:b=np.exp(theta[-1])
        mu=np.array([float(r['strength_difference']) for r in rows]);v=np.array([float(r['strength_difference_base_variance']) for r in rows])
        nu=np.array([float(r['home_jump_intensity'])+float(r['away_jump_intensity']) for r in rows]);sd=np.array([float(r['jump_scale_sd']) for r in rows])
        cap=int(poisson.isf(1e-14,float(nu.max()))) if nu.max() else 0
        return sum(poisson.pmf(k,nu)*ndtr((eta+b*mu)/np.sqrt(1+b*b*(v+k*sd*sd))) for k in range(cap+1))
    predictions=defaultdict(list)
    for r in read(folder/'fit_predictions.csv.gz'):predictions[r['fit_id']].append(r)
    check('13fits',len(models)==len(predictions)==13)
    for key,result in models.items():
        label=result['variant_id'];index=data.get(label,data['baseline']);saved=predictions[key];rs=[index[r['match_id']] for r in saved]
        prob=independent_p(result,rs);y=np.array([int(r['home_win']) for r in rs]);loss=-np.mean(np.where(y,np.log(prob),np.log1p(-prob)))
        check('likelihood:'+key,abs(loss-result['loss'])<2e-8)
        check('solver:'+key,result['numerical_fit_passed'] and result['gradient']<jc['numerics']['gradient_gate'] and not result['boundary_parameters'])
        for r,p in zip(saved,prob):check('probability:'+key+':'+r['match_id'],abs(float(r['fitted_home_probability'])-p)<2e-8)
        x,_=base_design.matrix(rs,result['model_id']);null=np.array(result['restricted_design']['null_space'])
        if null.size:check('training_nullspace:'+key,float(np.max(abs(x@null)))<1e-7)
        if label in cfg['score_variants']:expected=set(base_index)
        else:
            def keep(mid):
                f=flags[mid]
                if label=='exclude_cold_start':return f['cold_start']!='true'
                if label=='exclude_previously_disconnected':return f['weak_connection']!='true'
                if label=='exclude_unknown_geography':return f['unknown_home']!='true' and f['unknown_away']!='true'
                if label=='exclude_initialization_mean_sensitive':return f['initialization_mean_sensitive']!='true'
                return all(f[k]!='true' for k in ('cold_start','weak_connection','unknown_home','unknown_away'))
            expected={mid for mid in base_index if keep(mid)}
        check('exact_estimation_rows:'+key,{r['match_id'] for r in saved}==expected)
        print('STEP3_AUDIT_FIT',key,len(saved),flush=True)
    memberships=defaultdict(list)
    for r in read(prep/'reference_membership.csv.gz'):memberships[r['reference_id']].append(r['match_id'])
    new_members=defaultdict(list)
    if (folder/'new_estimable_reference_members.csv.gz').exists():
        for r in read(folder/'new_estimable_reference_members.csv.gz'):new_members[r['reference_id']].append(r['match_id'])
    pieces=defaultdict(list)
    for r in read(prep/'scenario_mixtures.csv'):pieces[r['target_id'],r['reference_kind'],r['arm']].append(r)
    source_contrasts={(r['target_id'],r['reference_kind'],r['model_id']):r for r in read(analysis/'contrasts.csv')}
    def scenario(p,ids,index,tid):
        rr=[index[mid] for mid in ids if not tid.startswith('Q3:B_') or index[mid]['home_unit']==p['home_unit_constant']]
        changed=[]
        for r in rr:
            x=dict(r)
            for field in ('era','tournament_group','home_region','home_unit','away_region','away_unit'):
                if p[field+'_constant']!='__varies__':x[field]=p[field+'_constant']
            changed.append(x)
        return changed
    for n,r in enumerate(read(folder/'contrasts.csv')):
        result=models[r['fit_id']];index=data.get(result['variant_id'],data['baseline']);oldids=memberships[r['baseline_reference_id']]
        ids=oldids if r['original_reference_all_scenarios_estimable']=='true' else new_members.get(r['comparison_reference_id'],[])
        check('reference_population',len(ids)==int(r['common_estimable_reference_rows']) and len(ids)==len(set(ids)) and set(ids)<=set(oldids))
        check('no_unidentified_original_number',(r['original_reference_all_scenarios_estimable']=='true')==bool(r['original_target_new_estimate_pp']))
        check('intervals_empty',not r['lower_pp'] and not r['upper_pp'] and r['inference_status']=='NOT_ADMITTED')
        if not ids:continue
        values=[];bv=[];null=np.array(result['restricted_design']['null_space'])
        for arm in ('1','2'):
            value=0.;basevalue=0.;mass=Fraction()
            for p in pieces[r['target_id'],r['reference_kind'],arm]:
                rr=scenario(p,ids,index,r['target_id'])
                if not rr:continue
                w=Fraction(int(p['weight_numerator']),int(p['weight_denominator']))*Fraction(len(rr),int(p['piece_reference_rows']))/Fraction(len(ids),len(oldids));mass+=w
                x,_=base_design.matrix(rr,result['model_id'])
                if null.size:check('scenario_estimability',bool(np.all(np.max(abs(x@null),axis=1)<=1e-8*(1+np.linalg.norm(x,axis=1)))))
                value+=float(w)*float(independent_p(result,rr).mean())
                if r['original_reference_all_scenarios_estimable']!='true':basevalue+=float(w)*float(independent_p(baseline_models[result['model_id']],scenario(p,ids,data['baseline'],r['target_id'])).mean())
            check('conditioned_mixture_mass',mass==1);values.append(value);bv.append(basevalue)
        delta=100*(values[0]-values[1]);base=float(source_contrasts[r['target_id'],r['reference_kind'],result['model_id']]['difference_pp']) if r['original_reference_all_scenarios_estimable']=='true' else 100*(bv[0]-bv[1])
        check('contrast_value',abs(delta-float(r['common_reference_new_estimate_pp']))<2e-7 and abs(base-float(r['common_reference_baseline_estimate_pp']))<2e-7 and abs(delta-base-float(r['change_at_common_reference_pp']))<2e-7)
        if n%64==0:print('STEP3_AUDIT_CONTRAST',n,r['fit_id'],flush=True)
    report=json.loads((folder/'report.json').read_text());check('scope',not report['stage6_complete'] and not report['intervals_computed'] and not report['score_replay_performed'])
    outcome=dict(passed=not failed,checks=checks,failed=failed,directory=directory,independent_probability_kernel=True,
        fixed_population_and_estimable_subreference_audited=True,formal_inference_validated=False,human_review=False)
    write_json(log/(folder.name+'-audit.json'),outcome);print(json.dumps(outcome,ensure_ascii=False),flush=True)
    if failed:raise SystemExit(1)


if __name__=='__main__':run()
