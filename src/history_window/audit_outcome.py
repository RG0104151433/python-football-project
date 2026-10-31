"""Independent arithmetic and historical-input reconstruction for stage4."""
from collections import Counter,defaultdict
import math
import numpy as np
from threadpoolctl import threadpool_limits
from src.data_contract import file_hash,write_json,fingerprint
from src.strength.io import ROOT,read_rows
from src.strength_joint.design import Design
from src.strength_joint.model import predict
from .contracts import read_json


def audit_outcome(run_directory=None,refit_examples=False):
    pointer=ROOT/'outputs/logs/history_window/outcome_pointer.json'
    if run_directory is None:run_directory=read_json(pointer)['log_directory']
    log=ROOT/run_directory;man=read_json(log/'manifest.json');cfg=read_json(log/'protocol.json')
    rid=log.name;table=ROOT/'outputs/tables/history_window'/rid
    checks=[];failures=[]
    def ck(name,passed):
        checks.append(name)
        if not passed:failures.append(name)
    for name,h in man['outputs'].items():ck('output_hash:'+name,file_hash(ROOT/name)==h)
    for name,h in man['identity']['inputs'].items():ck('input_hash:'+name,file_hash(ROOT/name)==h)
    source=read_rows(ROOT/'data/processed/strength/joint-preparation-6fa9d025ba40d11cd2f8/analysis_matches.csv')
    fact={r['match_id']:r for r in source};preds=read_rows(table/'predictions.csv');models=read_json(log/'models.json')
    boundaries=read_rows(table/'training_boundaries.csv');byjob=defaultdict(list);bywindow=defaultdict(list)
    for r in preds:byjob[r['model_key']].append(r);bywindow[r['window']].append(r)
    eps=cfg['probability_clip'];stats={}
    def summarize(rr):
        n=len(rr);ll=0.;br=0.;bias=0.;correct=0;clipped=0
        for r in rr:
            p=float(r['probability']);y=int(r['home_win']);q=min(1-eps,max(eps,p))
            ll-=y*math.log(q)+(1-y)*math.log1p(-q);br+=(p-y)**2;bias+=p-y;correct+=int((p>=.5)==bool(y));clipped+=int(p!=q)
        return dict(matches=n,primary_log_loss=ll/n,loss_sum=float(f'{ll:.10f}'),brier=br/n,
                    binary_accuracy=correct/n,calibration_bias_pp=100*bias/n,primary_probability_clips=clipped)
    for r in preds:
        f=fact[r['match_id']];p=float(r['probability'])
        ck('forecast:'+r['policy_id']+r['match_id'],int(r['home_win'])==int(f['home_win']) and r['date']==f['date'] and
           r['rating_cutoff']==f['prediction_cutoff'] and r['training_max']<r['date'] and r['rating_cutoff']<r['date'] and 0<=p<=1)
    ck('prediction_count',len(preds)==99594 and len({(r['policy_id'],r['match_id']) for r in preds})==99594)
    with threadpool_limits(limits=1):
        for b in boundaries:
            year=int(b['year']);w=b['window'];left='1980-01-01' if w=='cumulative' else f'{max(1980,year-int(w[:-1]))}-01-01'
            train=sorted((r for r in source if left<=r['date']<f'{year}-01-01'),key=lambda r:(r['date'],r['match_id']))
            target=sorted((r for r in source if int(r['year'])==year),key=lambda r:(r['date'],r['match_id']))
            key=f'{year}:{w}';model=models[key];rr=byjob[key]
            ck('training_boundary:'+key,b['left_inclusive']==left and int(b['rows'])==len(train) and b['actual_max']==max(r['date'] for r in train))
            ck('training_digest:'+key,fingerprint(sorted(r['match_id'] for r in train))==b['training_id_set_sha256']==model['training_id_set_sha256'])
            ck('training_feedback:'+key,int(b['preceding_year_rows'])==sum(int(r['year'])==year-1 for r in train) and int(b['same_year_training_rows'])==0)
            ck('sample:'+key,[r['match_id'] for r in rr]==[r['match_id'] for r in target])
            design=Design(train);expected=predict(model,target,design)
            maximum=float(np.max(np.abs(expected-np.array([float(r['probability']) for r in rr]))))
            ck('all_predictions_from_model:'+key,maximum<=5.1e-11)
            ck('encoding_past_only:'+key,model['encoding']['uses_test_rows'] is False and model['encoding']['weights']=={s+':'+g+':'+u:v for (s,g,u),v in design.weights.items()})
            ck('numerical_gate:'+key,model['numerical_fit_passed'] and model['multistart_loss_spread']<=1e-8 and all(t['gradient']<=3e-6 for t in [min(model['trials'],key=lambda t:t['loss'])]))
            stats[year,w]=summarize(rr)
    annual=read_rows(table/'yearly_metrics.csv')
    for r in annual:
        s=stats[int(r['year']),r['window']]
        for k,v in s.items():ck('annual:'+r['year']+r['window']+k,abs(float(r[k])-v)<1e-8)
    groups=read_rows(table/'group_metrics.csv')
    for r in groups:
        rr=bywindow[r['window']];g=r['group']
        if g=='development':rr=[x for x in rr if int(x['year'])<=2009]
        elif g=='adaptive_evaluation':rr=[x for x in rr if int(x['year'])>=2010]
        elif g!='all':
            field,value=g.split(':',1);rr=[x for x in rr if x[field]==value]
        for k,v in summarize(rr).items():ck('group:'+g+r['window']+k,abs(float(r[k])-v)<1e-8)
    decisions=read_rows(table/'selection_decisions.csv');chosen={}
    for r in decisions:
        year=int(r['year']);candidates=[]
        for w in cfg['windows']:
            lab='cumulative' if w is None else str(w)+'y';n=sum(stats[y,lab]['matches'] for y in range(2000,year));ll=sum(stats[y,lab]['loss_sum'] for y in range(2000,year))
            candidates.append((ll/n,-(100000 if w is None else w),lab))
        chosen[year]=min(candidates)[2]
        ck('past_selection:'+str(year),r['selected_window']==chosen[year] and int(r['selection_last_year'])==year-1 and r['selection_uses_current_year_outcomes']=='false')
    adaptive=read_rows(table/'adaptive_predictions.csv');lookup={(r['window'],r['match_id']):r for r in preds}
    for r in adaptive:
        actual=lookup[chosen[int(r['year'])],r['match_id']]
        ck('adaptive:'+r['match_id'],r['probability']==actual['probability'] and r['home_win']==actual['home_win'] and r['selected_window']==actual['window'])
    ck('adaptive_count',len(adaptive)==9727 and len({r['match_id'] for r in adaptive})==9727)
    for r in read_rows(table/'adaptive_metrics.csv'):
        rr=adaptive if r['group']=='adaptive_evaluation' else [x for x in adaptive if x['year']==r['group'].split(':')[1]]
        for k,v in summarize(rr).items():ck('adaptive_metric:'+r['group']+k,abs(float(r[k])-v)<1e-8)
    feedback=read_rows(table/'feedback_ledger.csv');ck('feedback_count',len(feedback)==99594)
    from datetime import date,timedelta
    for r in feedback:
        original=lookup[(r['policy_id'].replace('outcome-',''),r['match_id'])]
        ck('feedback:'+r['prediction_id'],r['actual_home_win']==original['home_win'] and r['predicted_home_probability']==original['probability'] and
            r['result_eligible_from']==(date.fromisoformat(original['date'])+timedelta(days=1)).isoformat() and
            r['next_scheduled_model_refit']==str(int(original['year'])+1)+'-01-01' and r['label_source']=='actual_outcome')
    pairrows=read_rows(table/'paired_losses.csv')
    for r in pairrows:
        def sub(w):
            rr=bywindow[w]
            return {x['match_id']:x for x in rr if r['group']=='all' or (r['group']=='development' and int(x['year'])<=2009) or (r['group']=='adaptive_evaluation' and int(x['year'])>=2010)}
        a,b=sub(r['policy_a']),sub(r['policy_b']);d=[]
        for mid in sorted(a):
            y=int(a[mid]['home_win']);pa=min(1-eps,max(eps,float(a[mid]['probability'])));pb=min(1-eps,max(eps,float(b[mid]['probability'])))
            d.append(-y*math.log(pa)-(1-y)*math.log1p(-pa)+y*math.log(pb)+(1-y)*math.log1p(-pb))
        ck('paired_loss:'+r['group']+r['policy_a']+r['policy_b'],abs(sum(d)/len(d)-float(r['mean_loss_a_minus_b']))<1e-8 and len(d)==int(r['matches']))
    # Existing baseline is a cross-version numerical reference, never a second sample.
    old=read_rows(ROOT/'outputs/tables/strength_joint/rolling-prediction-4722c7b1b5f63cef35e3/predictions.csv')
    old={r['match_id']:r for r in old if r['model_id']=='M3_nested' and int(r['year'])>=2000}
    error=max(abs(float(r['probability'])-float(old[r['match_id']]['probability'])) for r in bywindow['cumulative'])
    ck('legacy_cumulative_probability_reference',error<2e-6)
    refits=[]
    if refit_examples:
        from .training import fit_year
        joint=read_json(ROOT/cfg['study_config'])
        with threadpool_limits(limits=1):
            for y,w in [(2000,2),(2024,20),(2024,None)]:
                pp,_,_,_=fit_year(sorted(source,key=lambda r:(r['date'],r['match_id'])),y,w,cfg,joint['numerics'])
                oldrows=byjob[f"{y}:{'cumulative' if w is None else str(w)+'y'}"]
                same=all(float(a['probability'])==float(b['probability']) for a,b in zip(pp,oldrows))
                ck('fresh_repeat:'+str(y)+str(w),same);refits.append(dict(year=y,window=w,identical_probabilities=same))
    report=dict(passed=not failures,checks=len(checks),failures=failures,run_id=rid,prediction_rows=len(preds),adaptive_rows=len(adaptive),
        legacy_cumulative_max_probability_difference=error,refit_examples=refits,human_review=False,formal_inference=False,
        independent_arithmetic=True,model_prediction_reconstruction=True)
    write_json(log/'independent_audit.json',report)
    if failures:raise ValueError('OUTCOME_AUDIT_FAILED:'+repr(failures[:10]))
    adoption=dict(run_id=rid,manifest_sha256=file_hash(log/'manifest.json'),independent_audit_sha256=file_hash(log/'independent_audit.json'),
        numerical_and_descriptive_admitted=True,formal_inference_admitted=False,decision_log_id=cfg['decision_log_id'])
    write_json(log/'adoption.json',adoption)
    ptr=read_json(pointer)
    if ptr['run_id']==rid:
        ptr.update(independent_audit_pending=False,adoption=(log/'adoption.json').relative_to(ROOT).as_posix());write_json(pointer,ptr)
    print(report,flush=True);return report
