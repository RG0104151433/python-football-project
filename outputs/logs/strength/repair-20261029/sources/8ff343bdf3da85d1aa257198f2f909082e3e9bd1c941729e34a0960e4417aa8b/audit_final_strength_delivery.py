"""Independent final arithmetic, baseline, distribution, chronology and restart."""
from pathlib import Path
from collections import Counter,defaultdict
import csv
import hashlib
import json
import math
import sys
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength.calibration import predict,online_offsets


def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fp(s):return hashlib.sha256(json.dumps(s,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def run():
    out=ROOT/'outputs/logs/strength/repair-20261029';checks=0;failed=[]
    def check(label,ok):
        nonlocal checks
        checks+=1
        if not ok:failed.append(label)
    normal=ROOT/json.loads((out/'delivery_normal.json').read_text())['directory'];strict=ROOT/json.loads((out/'delivery_strict.json').read_text())['directory']
    source=read(ROOT/'outputs/logs/strength/learning-b2889411cc93b44f88b6/learning_matches.csv');lookup={r['match_id']:r for r in source}
    study={r['match_id'] for r in source if r['accepted_current_study']=='true'}
    groups=defaultdict(list)
    for r in source:groups[r['date']].append(r)
    frequencies={0:np.ones(3),1:np.ones(3)};ratings=defaultdict(float);frequency={};fixed={}
    for day,rs in sorted(groups.items()):
        increments=defaultdict(float)
        for r in sorted(rs,key=lambda r:r['match_id']):
            mid=r['match_id'];h,a=r['home_entity_id'],r['away_entity_id'];venue=int(r['is_neutral']!='true')
            frequency[mid]=frequencies[venue]/frequencies[venue].sum()
            u=math.log(10)/800*(ratings[h]-ratings[a]+venue*100)
            z=np.array([u,math.log(.75),-u]);p=np.exp(z-z.max());p/=p.sum();fixed[mid]=p
            y=int(r['outcome_index']);s=(1.,.5,0.)[y];change=40*(s-(p[0]+.5*p[1]))
            increments[h]+=change;increments[a]-=change
        for t,d in increments.items():ratings[t]+=d
        for r in rs:frequencies[int(r['is_neutral']!='true')][int(r['outcome_index'])]+=1
    all_rows={};reports={}
    for folder in (normal,strict):
        m=json.loads((folder/'manifest.json').read_text());report=json.loads((folder/'report.json').read_text());reports[folder.name]=report
        for n,h in m['outputs'].items():check('hash:'+folder.name+n,sha(folder/n)==h)
        with zipfile.ZipFile(folder/'source_snapshot.zip') as z:
            for n,h in m['identity']['code'].items():check('archive:'+folder.name+n,fp(z.read(n).decode().replace('\r\n','\n'))==h)
        raw_folder=ROOT/report['raw_source'];check('raw_binding:'+folder.name,sha(raw_folder/'manifest.json')==m['identity']['raw_source_manifest_sha'])
        raw={r['match_id']:r for r in read(raw_folder/'prematch_features.csv')};rows=read(folder/'prematch_features.csv');all_rows[folder.name]={r['match_id']:r for r in rows}
        check('population:'+folder.name,len(rows)==38919 and set(all_rows[folder.name])==lookup.keys())
        check('study:'+folder.name,{r['match_id'] for r in read(folder/'study_prematch_features.csv')}==study and len(study)==24917)
        check('targets_absent:'+folder.name,not any(k in rows[0] for k in ('outcome_index','home_score','away_score','home_win')))
        for r in rows:
            mid=r['match_id'];probs=[float(r[k]) for k in ('p_home','p_draw','p_away')]
            check('prob:'+mid,all(0<p<1 for p in probs) and abs(sum(probs)-1)<2e-9)
            check('chronology:'+mid,all(r[k]=='initial_prior' or r[k]<r['date'] for k in ('prediction_cutoff','calibration_cutoff','shape_information_cutoff')))
            check('strength_unmodified:'+mid,all(r[k]==raw[mid][k] for k in ('difference','difference_variance','home_mean','away_mean','home_variance','away_variance','home_away_covariance')))
            vh,va,c,v=map(float,(r['home_variance'],r['away_variance'],r['home_away_covariance'],r['difference_variance']))
            check('covariance:'+mid,vh>0 and va>0 and c*c<=vh*va+1e-8 and abs(vh+va-2*c-v)<1e-8)
            check('poisson_variance:'+mid,abs(float(r['difference_base_variance'])+
                (float(r['home_jump_intensity'])+float(r['away_jump_intensity']))*float(r['jump_scale_sd'])**2-v)<1e-8)
        for metric in report['forecast_checks']+report['type_checks']:
            a,b=map(int,metric['period'].split('_')[1:])
            rs=[r for r in rows if a<=int(r['date'][:4])<=b and ('scope' not in metric or metric['scope']=='all_learning' or r['match_id'] in study)
                and ('friendly' not in metric or r['match_id'] in study and (lookup[r['match_id']]['tournament_group']=='friendly')==metric['friendly'])]
            n=len(rs);p=np.array([[float(r[k]) for k in ('p_home','p_draw','p_away')] for r in rs]);y=np.array([int(lookup[r['match_id']]['outcome_index']) for r in rs])
            loss=float(-np.log(p[np.arange(n),y]).mean());bias=float(np.mean(p[:,0]-(y==0)));bin_error=0.
            for k in range(3):
                for j in range(5):
                    mask=np.minimum(4,(p[:,k]*5).astype(int))==j
                    if mask.sum()>=200:bin_error=max(bin_error,abs(float(p[mask,k].mean()-np.mean(y[mask]==k))))
            check('metric:'+metric['period']+str(metric.get('scope',metric.get('friendly'))),n==metric['count'] and abs(loss-metric['log_loss'])<1e-8 and abs(bias-metric.get('home_bias',metric.get('home_probability_bias')))<1e-8)
            gates=[abs(bias)<=.03,bin_error<=.1]
            if 'scope' in metric:
                f=np.array([frequency[r['match_id']] for r in rs]);e=np.array([fixed[r['match_id']] for r in rs])
                fl=float(-np.log(f[np.arange(n),y]).mean());el=float(-np.log(e[np.arange(n),y]).mean())
                accuracy=float(np.mean(np.argmax(p,axis=1)==y));fa=float(np.mean(np.argmax(f,axis=1)==y))
                gates+=[fl-loss>=.005,accuracy>=fa-.01,loss<=el+.01]
                check('independent_baselines:'+metric['period']+metric['scope'],abs(fl-metric['frequency_log_loss'])<1e-9 and abs(el-metric['fixed_step_log_loss'])<1e-9)
            check('independent_all_gates:'+metric['period']+str(metric.get('scope',metric.get('friendly'))),all(gates) and metric['passed'])
    aa,bb=all_rows[normal.name],all_rows[strict.name]
    maxp=max(abs(float(aa[mid][k])-float(bb[mid][k])) for mid in aa for k in ('p_home','p_draw','p_away'))
    check('complete_precision',maxp<=.01)
    report=reports[normal.name];states=json.loads((normal/'checkpoints.json').read_text())
    rawstates=json.loads((ROOT/report['raw_source']/'checkpoints.json').read_text())
    for boundary in ('1979-12-31','2019-12-31'):
        core=CollapsedJumpFilter.restore(rawstates[boundary]['state']);day=min(d for d in groups if d>boundary)
        gs=[dict(match_id=r['match_id'],home=r['home_entity_id'],away=r['away_entity_id'],venue=int(r['is_neutral']!='true'),
            friendly=r['tournament_group']=='friendly',outcome=int(r['outcome_index'])) for r in groups[day]]
        raw=core.day(day,gs);p=np.array([[float(f'{r[k]:.10f}') for k in ('p_home','p_draw','p_away')] for r in raw]);p=np.maximum(p,1e-12);p/=p.sum(axis=1,keepdims=True)
        cc=np.array([[int(g['friendly']),int(g['venue']==0)] for g in sorted(gs,key=lambda r:r['match_id'])]);shaped=np.zeros_like(p)
        for context in set(map(tuple,cc)):
            state=next(s for s in states[boundary]['shape_for_next_year'] if (s['friendly'],s['neutral'])==context)
            mask=(cc==context).all(axis=1);shaped[mask]=predict(p[mask],state,9)
        forecast,_=online_offsets(shaped,np.array([r['outcome_index'] for r in raw]),[day]*len(raw),cc,.02,9,states[boundary]['residual_states'])
        check('complete_core_shape_residual_restart:'+boundary,all(max(abs(forecast[i,k]-float(aa[r['match_id']][name])) for k,name in enumerate(('p_home','p_draw','p_away')))<3e-9 for i,r in enumerate(raw)))
    check('raw_unchanged',sha(ROOT/'data/raw/international_results/results.csv')=='5dcefd1aa0483979ea8378cef5be448d2005609d39945ea162378561a30a6767')
    check('clean_unchanged',sha(ROOT/'data/processed/prep-3fab808178cf8ad71d88/matches_clean.csv')=='69ba00073970fe011a62f5871c08ace6285d7fe75d5a0d79afdac0ef972de9dc')
    result=dict(passed=not failed,checks=checks,failed=failed,normal=normal.relative_to(ROOT).as_posix(),strict=strict.relative_to(ROOT).as_posix(),
        max_complete_probability_difference=maxp,independent_baselines_reconstructed=True,complete_restart_verified=True,
        human_review='not_performed',prospective_test=False)
    (out/'final_delivery_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result),flush=True)
    if failed:raise SystemExit(1)


if __name__=='__main__':run()
