"""Independent saved-output/source/time/restart checks for repaired strength."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse
import csv
import hashlib
import json
import math
import sys
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.strength.calibration import predict,online_offsets,switching_mixture


def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fp(t):return hashlib.sha256(json.dumps(t,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main(normal=None,strict=None):
    checks=0;fail=[]
    def check(label,ok):
        nonlocal checks
        checks+=1
        if not ok:fail.append(label)
    def manifest(folder):
        m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        for n,h in m['outputs'].items():check('hash:'+folder.name+n,sha(folder/n)==h)
        with zipfile.ZipFile(folder/'source_snapshot.zip') as archive:
            for n,h in m['identity']['code'].items():check('archive:'+folder.name+n,fp(archive.read(n).decode().replace('\r\n','\n'))==h)
        return m
    source=read(ROOT/'outputs/logs/strength/learning-b2889411cc93b44f88b6/learning_matches.csv')
    lookup={r['match_id']:r for r in source};study={r['match_id'] for r in source if r['accepted_current_study']=='true'}
    pairs={'jump_small':('jump-ratings-2011739ec6714deca2e6','jump-ratings-7abc686ca7ad9c60ef62'),
           'jump_full':('jump-ratings-451ecade0bf84ee0bfb6','jump-ratings-0deb26fde40475629288')}
    numeric=[]
    for model,(aa,bb) in pairs.items():
        folders=[ROOT/'data/processed/strength'/x for x in (aa,bb)];data=[]
        for folder in folders:
            m=manifest(folder);rows=read(folder/'prematch_features.csv');data.append({r['match_id']:r for r in rows})
            for p,h in m['identity']['inputs'].items():check('input:'+p,sha(ROOT/p)==h)
            check('jump_population:'+folder.name,len(rows)==38919 and set(data[-1])==lookup.keys())
            counts=Counter();batches=defaultdict(list)
            for r in rows:batches[r['date']].append(r)
            for day,gs in sorted(batches.items()):
                for r in gs:
                    mid=r['match_id'];check('date:'+mid,r['date']==lookup[mid]['date'] and (r['prediction_cutoff']=='initial_prior' or r['prediction_cutoff']<day))
                    probs=[float(r[k]) for k in ('p_home','p_draw','p_away')]
                    check('prob:'+mid,all(0<=p<=1 for p in probs) and abs(sum(probs)-1)<2e-9)
                    h,a,c,v=[float(r[k]) for k in ('home_variance','away_variance','home_away_covariance','difference_variance')]
                    check('cov:'+mid,h>0 and a>0 and c*c<=h*a+1e-8 and abs(h+a-2*c-v)<1e-8)
                    check('history:'+mid,int(r['home_history'])==counts[r['home']] and int(r['away_history'])==counts[r['away']])
                for r in gs:counts[r['home']]+=1;counts[r['away']]+=1
            states=json.loads((folder/'checkpoints.json').read_text(encoding='utf-8'))
            for key,value in states.items():
                st=value['state'];check('snapshot_dates:'+folder.name+key,st['last_day']<=key and all(x<=key for x in st['last'].values()))
                check('snapshot_psd:'+folder.name+key,np.linalg.eigvalsh(st['cov']).min()>=-1e-8)
            for boundary in ('1979-12-31','2019-12-31'):
                restored=CollapsedJumpFilter.restore(states[boundary]['state'])
                day=min(r['date'] for r in source if r['date']>boundary)
                gs=[dict(match_id=r['match_id'],home=r['home_entity_id'],away=r['away_entity_id'],venue=0 if r['is_neutral']=='true' else 1,
                    friendly=r['tournament_group']=='friendly',outcome=int(r['outcome_index'])) for r in source if r['date']==day]
                actual=restored.day(day,gs)
                check('restart:'+folder.name+boundary,all(max(abs(r[k]-float(data[-1][r['match_id']][k])) for k in ('p_home','p_draw','p_away','difference','difference_variance'))<2e-9 for r in actual))
        maxp=max(abs(float(data[0][mid][k])-float(data[1][mid][k])) for mid in data[0] for k in ('p_home','p_draw','p_away'))
        maxd=max(abs(float(data[0][mid]['difference'])-float(data[1][mid]['difference'])) for mid in data[0])
        check('full_numeric:'+model,maxp<=.01);numeric.append(dict(model=model,max_probability_difference=maxp,max_strength_difference=maxd))
    if normal:
        normal=ROOT/normal;strict=ROOT/strict;manifest(normal);manifest(strict)
        report=json.loads((normal/'report.json').read_text(encoding='utf-8'));sr=json.loads((strict/'report.json').read_text(encoding='utf-8'))
        rows=read(normal/'prematch_features.csv');strict_rows={r['match_id']:r for r in read(strict/'prematch_features.csv')}
        check('calibrated_study_ids',{r['match_id'] for r in read(normal/'study_prematch_features.csv')}==study)
        maxp=0
        for r in rows:
            check('calibration_time:'+r['match_id'],r['calibration_cutoff']=='initial_prior' or r['calibration_cutoff']<r['date'])
            check('selector_time:'+r['match_id'],r['selector_cutoff']<r['date'])
            check('same_selected_model:'+r['match_id'],r['selected_model']==strict_rows[r['match_id']]['selected_model'])
            maxp=max(maxp,max(abs(float(r[k])-float(strict_rows[r['match_id']][k])) for k in ('p_home','p_draw','p_away')))
        check('calibration_quadrature_tightening',maxp<=.01)
        numeric.append(dict(model='complete_calibrated_pipeline',max_probability_difference=maxp,max_strength_difference=None))
        for metric in report['forecast_checks']+report['type_checks']:
            a,b=map(int,metric['period'].split('_')[1:])
            selected=[r for r in rows if a<=int(r['date'][:4])<=b and
                ('scope' not in metric or metric['scope']=='all_learning' or r['match_id'] in study) and
                ('friendly' not in metric or r['match_id'] in study and (lookup[r['match_id']]['tournament_group']=='friendly')==metric['friendly'])]
            n=len(selected);bias=sum(float(r['p_home'])-int(lookup[r['match_id']]['outcome_index']=='0') for r in selected)/n
            loss=-sum(math.log(float(r[('p_home','p_draw','p_away')[int(lookup[r['match_id']]['outcome_index'])]])) for r in selected)/n
            check('independent_metric:'+str(metric.get('friendly',metric.get('scope')))+metric['period'],
                  n==metric['count'] and abs(loss-metric['log_loss'])<1e-8 and abs(bias-metric.get('home_bias',metric.get('home_probability_bias')))<1e-8)
            check('gate_pass:'+metric['period']+str(metric.get('friendly',metric.get('scope'))),metric['passed'])
        check('strict_all_gates',sr['all_forecast_gates_passed'])
        # Restore complete probability correction at first2020 date, not only core ratings.
        states=json.loads((normal/'calibration_states.json').read_text(encoding='utf-8'))
        day=min(r['date'] for r in rows if r['date']>'2019-12-31');current=[r for r in rows if r['date']==day]
        for final_model in {r['selected_model'] for r in current}:
            raw_name=final_model.split('__switching__')[0];rate=float(final_model.rsplit('__',1)[1])
            raw_index={r['match_id']:r for r in read(ROOT/report['source_directories'][raw_name]/'prematch_features.csv')}
            raw=np.array([[float(raw_index[r['match_id']][k]) for k in ('p_home','p_draw','p_away')] for r in current]);raw=np.maximum(raw,1e-12);raw/=raw.sum(axis=1,keepdims=True)
            targets=np.array([int(lookup[r['match_id']]['outcome_index']) for r in current]);contexts=np.array([[int(lookup[r['match_id']]['tournament_group']=='friendly'),int(lookup[r['match_id']]['is_neutral']=='true')] for r in current])
            past=[s for s in states if s['model']==final_model and s.get('date','9999')<day]
            latest={}
            for s in past:
                key=(s['friendly'],s['neutral'])
                if key not in latest or s['date']>latest[key]['date']:latest[key]=s
            experts=next(iter(latest.values()))['expert_names'];pp=[]
            for expert in experts:
                if '__online_offset__' in expert:
                    history={}
                    for s in states:
                        if s['model']==expert and s.get('date','9999')<day:
                            key=(s['friendly'],s['neutral'])
                            if key not in history or s['date']>history[key]['date']:history[key]=s
                    predicted,_=online_offsets(raw,targets,[day]*len(current),contexts,float(expert.rsplit('__',1)[1]),9,list(history.values()))
                else:
                    predicted=np.zeros_like(raw)
                    for context in set(map(tuple,contexts)):
                        s=next(s for s in states if s['model']==expert and s.get('year')==2020 and (s['friendly'],s['neutral'])==context)
                        mask=(contexts==context).all(axis=1);predicted[mask]=predict(raw[mask],s,9)
                pp.append(predicted)
            prior=np.array([.5/sum('__online_' in e for e in experts) if '__online_' in e else .5/sum('__online_' not in e for e in experts) for e in experts])
            restored,_=switching_mixture(np.stack(pp,axis=1),targets,[day]*len(current),contexts,prior,rate,list(latest.values()))
            check('full_probability_restart:'+final_model,all(max(abs(restored[i,j]-float(r[k])) for j,k in enumerate(('p_home','p_draw','p_away')))<2e-9
                for i,r in enumerate(current) if r['selected_model']==final_model))
    result=dict(passed=not fail,checks=checks,failed=fail,numeric_comparisons=numeric,human_review='not_performed',prospective_test=False)
    p=ROOT/'outputs/logs/strength/repair-20261029'/('complete_audit.json' if normal else 'raw_jump_audit.json')
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result),flush=True)
    if fail:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--normal');p.add_argument('--strict');a=p.parse_args();main(a.normal,a.strict)
