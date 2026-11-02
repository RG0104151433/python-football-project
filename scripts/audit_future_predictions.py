"""Independent expanded-normal/Poisson audit; no forecasting module imported."""
import argparse,csv,hashlib,json,math
from collections import Counter
from datetime import date,datetime
from pathlib import Path
import numpy as np
from scipy.special import ndtr
from scipy.stats import poisson

ROOT=Path(__file__).resolve().parents[1]
def audit(rid=None):
    def js(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
    def read(p):
        with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    rid=rid or js(ROOT/'outputs/logs/future_predictions/current.json')['run_id']
    log=ROOT/'outputs/logs/future_predictions'/rid;tab=ROOT/'outputs/tables/future_predictions'/rid
    man=js(log/'manifest.json');cfg=man['identity']['protocol'];checks=[]
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok:raise AssertionError(name)
    for group in ['inputs','code']:
        for p,h in man['identity'][group].items():check(group+':'+p,sha(ROOT/p)==h)
    for p,h in man['outputs'].items():check('sealed:'+p,sha(ROOT/p)==h)
    forecasts=read(tab/'forecasts.csv');ledger=read(tab/'new_record_ledger.csv');learning=read(tab/'new_learning_matches.csv')
    features=read(tab/'new_prematch_features.csv');new=read(tab/'new_analysis_matches.csv')
    check('52_unique_forecasts',len(forecasts)==len({r['match_id'] for r in forecasts})==52)
    check('two_rounds',Counter(r['round'] for r in forecasts)==Counter({'5':26,'6':26}))
    check('ledger_balance',len(ledger)==1803 and sum(r['included']=='true' for r in ledger)==len(learning)==1719)
    check('exact_new_feature_members',{r['match_id'] for r in learning}=={r['match_id'] for r in features})
    check('new_analysis_non_neutral',len(new)==1147 and all(r['is_neutral']=='false' for r in new))
    lookup={r['match_id']:r for r in ledger}
    for r in ledger:
        y=0 if int(r['home_score'])>int(r['away_score']) else 1 if r['home_score']==r['away_score'] else 2
        check('label:'+r['match_id'],y==int(r['outcome_index']) and int(r['home_win'])==int(y==0))
    check('no_same_day_feedback',all(r['prediction_cutoff']<r['date'] for r in features))
    train=read(ROOT/cfg['old_joint'])+[r for r in new if r['date']<cfg['model_training_end_exclusive']]
    models=js(log/'models.json');check('training_count_cutoff',len(train)==models['training_rows']==25599 and max(r['date'] for r in train)=='2025-12-29')
    designcounts={side:Counter((r[side+'_region'],r[side+'_unit']) for r in train) for side in ['home','away']}
    geo={}
    for r in sorted(train,key=lambda r:r['date']):
        for side in ['home','away']:geo[r[side+'_team_id']]=(r[side+'_region'],r[side+'_unit'])
    state=js(log/'rating_state.json');idx={t:i for i,t in enumerate(state['teams'])};m=np.array(state['mean']);cov=np.array(state['cov']);p=state['params']
    check('state_cutoff_and_covariance',state['last_day']=='2026-10-06' and np.max(abs(cov-cov.T))<1e-9 and np.linalg.eigvalsh(cov).min()>-1e-8)
    old=read(ROOT/cfg['old_learning']);entities={}
    for r in sorted(old,key=lambda r:r['date']):
        for side in ['home','away']:entities[r[side+'_team']]=r[side+'_entity_id']
    for r in ledger:
        if r['included']=='true':
            entities[r['home_team']]=r['home_entity'];entities[r['away_team']]=r['away_entity']
    def eta(model,g):
        mm=models['models'][model];cols=[]
        for name in mm['names']:
            if name=='intercept':v=1
            elif name.startswith('era:'):v=int(name=='era:2020_2024')
            elif name=='friendly':v=0
            else:
                side,kind,value=name.split(':');reg,unit=geo[g[side+'_team_id']]
                if kind=='region':v=int(reg==value or not reg and value=='unknown')
                else:
                    cc=designcounts[side];parent=next(a for a,u in cc if u==value)
                    anchor=max([u for a,u in cc if a==parent],key=lambda u:(cc[parent,u],u))
                    v=0 if reg!=parent else 1 if unit==value else -cc[parent,value]/cc[parent,anchor] if unit==anchor else 0
            cols.append(v)
        return float(np.array(cols)@np.array(mm['theta'][:-1])),math.exp(mm['theta'][-1])
    clean={r['home_team']:r['home_team_id'] for r in new}
    clean.update({r['away_team']:r['away_team_id'] for r in new})
    maxerr=0
    for r in forecasts:
        day=r['date'];a,b=entities[r['home_team']],entities[r['away_team']];i,j=idx[a],idx[b]
        dth=(date.fromisoformat(day)-date.fromisoformat(state['last'][a])).days/365.2425
        dta=(date.fromisoformat(day)-date.fromisoformat(state['last'][b])).days/365.2425
        nu=p['jump_rate']*(dth+dta);cap=int(poisson.isf(1e-12,nu));kk=np.arange(cap+1);w=poisson.pmf(kk,nu);w/=w.sum()
        base=cov[i,i]+cov[j,j]-2*cov[i,j]+p['q']*(dth+dta);mu=m[i]-m[j]
        check('strength:'+r['match_id'],abs(mu-float(r['strength_mean']))<1e-8 and abs(math.sqrt(base+nu*p['jump_sd']**2)-float(r['strength_sd']))<1e-8)
        cc=cov.copy();cc[i,i]+=p['q']*dth;cc[j,j]+=p['q']*dta
        dt=(date.fromisoformat(day)-date.fromisoformat(state['last_day'])).days/365.2425;h=len(idx)
        cc[h,h]+=p['home_q']*dt;aa=np.zeros(len(m));aa[i]=1;aa[j]=-1;aa[h]=int(r['venue'])
        nm=aa@m;vv=aa@cc@aa+p['jump_sd']**2*kk;scale=np.sqrt(1+vv)
        native=np.array([w@ndtr((nm-p['delta'])/scale),w@(ndtr((p['delta']-nm)/scale)-ndtr((-p['delta']-nm)/scale)),w@ndtr((-p['delta']-nm)/scale)])
        native=(1-p['epsilon'])*native+p['epsilon']/3
        published=np.array([float(r[k]) for k in ['native_home_probability','native_draw_probability','native_away_probability']])
        err=float(max(abs(native-published)));maxerr=max(maxerr,err)
        check('native:'+r['match_id'],err<2e-8 and abs(sum(published)-1)<2e-9)
        check('prospective:'+r['match_id'],datetime.fromisoformat(r['issued_at_utc']).date()<date.fromisoformat(day) and r['future_result_received']=='false')
        if not int(r['venue']):
            check('neutral_withheld:'+r['match_id'],r['main_home_probability']==r['latent_probability_p05']=='' and r['main_status']=='withheld_third_country_venue')
            continue
        g={'home_team_id':clean[r['home_team']],'away_team_id':clean[r['away_team']]}
        for model,field in [('M3_nested','main_home_probability'),('M1_strength','strength_reference_home_probability')]:
            e,s=eta(model,g);value=float(w@ndtr((e+s*mu)/np.sqrt(1+s*s*(base+p['jump_sd']**2*kk))))
            check(model+':'+r['match_id'],abs(value-float(r[field]))<2e-8)
            if model=='M3_nested':
                def cdf(x):return float(w@ndtr((x-mu)/np.sqrt(base+p['jump_sd']**2*kk)))
                for q,field2 in [(.05,'latent_probability_p05'),(.95,'latent_probability_p95')]:
                    low,high=mu-100,mu+100
                    for _ in range(70):
                        mid=(low+high)/2
                        if cdf(mid)<q:low=mid
                        else:high=mid
                    expected=float(ndtr(e+s*(low+high)/2))
                    check('quantile:'+r['match_id']+':'+str(q),abs(expected-float(r[field2]))<2e-8)
        check('binary_normalization:'+r['match_id'],abs(float(r['main_home_probability'])+float(r['main_nonhome_probability'])-1)<2e-9)
    for f in tab.glob('*.csv'):
        raw=f.read_bytes();check('format:'+f.name,raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw)
    result=dict(run_id=rid,passed=True,checks=len(checks),maximum_native_probability_error=maxerr,
        formal_inference=False,human_review=False,postmatch_evaluation_complete=False,
        auditor_sha256=sha(Path(__file__)),manifest_sha256=sha(log/'manifest.json'),details=checks)
    with (log/'independent_audit.json').open('w',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='details'}))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-id');audit(p.parse_args().run_id)
