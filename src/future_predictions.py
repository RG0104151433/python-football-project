"""Prospective UNL forecast package: versioned eligibility, state continuation, frozen issue.

Only actual prior outcomes update ratings. Joint predictions are binary; native
rating WDL is auxiliary. Latent intervals condition on model and coefficients.
"""
from collections import Counter,defaultdict
from datetime import date,datetime,timezone
import io,json,math,re,zipfile
import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr
from scipy.stats import poisson
from threadpoolctl import threadpool_limits
from src.data_contract import (atomic_bytes,csv_bytes,file_hash,fingerprint,write_json,
                               normalize,parse_date,parse_score,parse_neutral,tournament_group,team_slug)
from src.strength.io import ROOT,read_rows,environment
from src.strength.prepare import membership,episode,make_windows
from src.strength.collapsed_jump import CollapsedJumpFilter
from src.history_window.ratings import numerical_cache,full_forecast
from src.strength_joint.design import Design
from src.strength_joint.model import predict,Kernel
from src.strength_joint.validation import before_day
from src.strength_predictive_validation import fit_past


def latent_probability_range(mu,base,nu,sd,eta,b,quantiles=(.05,.95)):
    """Central latent Q=Phi(eta+b*D) range; NOT sampling/parameter CI."""
    if base<=0 or nu<0 or sd<0 or b<=0:raise ValueError('INVALID_LATENT_DISTRIBUTION')
    cap=int(poisson.isf(1e-12,nu)) if nu else 0
    k=np.arange(cap+1);weights=poisson.pmf(k,nu);weights/=weights.sum()
    scales=np.sqrt(base+k*sd*sd)
    def cdf(x):return float(weights@ndtr((x-mu)/scales))
    span=12*max(scales)+abs(mu)+1
    xx=[brentq(lambda x:cdf(x)-q,mu-span,mu+span,xtol=1e-12) for q in quantiles]
    return [float(ndtr(eta+b*x)) for x in xx]


def update_records(raw,old_learning,crosswalk,registry,state,cfg,pilot,former,events):
    windows=make_windows(pilot,former)
    seen=set();ledger=[];learning=[];facts={}
    for r in old_learning:
        for side in ['home','away']:
            label=r[side+'_team']
            facts[label]=r[side+'_entity_id']
    pair_counts=Counter((r['date'],*sorted([r['home_team'],r['away_team']])) for r in raw if r['date']>'2024-12-31')
    raw_sha=cfg['raw_sha256']
    for no,r in enumerate(raw,1):
        if not '2024-12-31'<r['date']<cfg['information_date_exclusive']:continue
        mid='results:'+fingerprint([r[k] for k in ['date','home_team','away_team','home_score','away_score','tournament','city','country','neutral']])
        issues=[];new=dict(match_id=mid,source_record_id=f'results:{raw_sha}:{no}',date=r['date'],
            home_team=normalize(r['home_team']),away_team=normalize(r['away_team']),tournament=normalize(r['tournament']))
        if mid in seen:issues.append('duplicate_content')
        seen.add(mid)
        if pair_counts[r['date'],*sorted([r['home_team'],r['away_team']])]>1:issues.append('duplicate_or_conflicting_pair')
        try:
            parse_date(r['date']);hs,aws=parse_score(r['home_score']),parse_score(r['away_score'])
            neutral=parse_neutral(r['neutral'])
        except ValueError as exc:
            issues.append('invalid_required_field:'+str(exc));hs=aws=0;neutral=None
        for side in ['home','away']:
            label=new[side+'_team'];tid='team:'+team_slug(label);code=crosswalk.get(tid,{}).get('fifa_code','')
            ok,why=membership(r['date'],label,code,registry,events)
            entity=episode(label,tid,r['date'],windows)
            new[side+'_team_id']=tid;new[side+'_entity']=entity
            if not ok:issues.append(side+':'+why)
            if entity not in state['teams'] or facts.get(label)!=entity:issues.append(side+':identity_not_continuable')
        if new['home_team']==new['away_team']:issues.append('self_match')
        group=tournament_group(new['tournament'])
        if group=='unknown':issues.append('unknown_tournament')
        outcome=0 if hs>aws else 1 if hs==aws else 2
        new.update(home_score=hs,away_score=aws,is_neutral=neutral,tournament_group=group,
                   outcome_index=outcome,home_win=int(outcome==0),included=not issues,
                   status='included_conditional_membership_continuation' if not issues else 'excluded_or_pending',
                   reasons=';'.join(issues),identity_assumption='mapped association continuation beyond2024, no new historical merge')
        ledger.append(new)
        if not issues:
            learning.append(dict(match_id=mid,date=r['date'],home=new['home_entity'],away=new['away_entity'],
                home_label=new['home_team'],away_label=new['away_team'],venue=0 if neutral else 1,
                friendly=group=='friendly',outcome=outcome,study=False))
    return sorted(ledger,key=lambda r:(r['date'],r['match_id'])),sorted(learning,key=lambda r:(r['date'],r['match_id']))


def geo_map(old):
    geo={}
    for r in sorted(old,key=lambda r:r['date']):
        for side in ['home','away']:
            if r[side+'_region'] and r[side+'_unit']:
                geo[r[side+'_team_id']]=(r[side+'_region'],r[side+'_unit'])
    return geo


def as_joint(record,feature,geo):
    hr,hu=geo.get(record['home_team_id'],('',''));ar,au=geo.get(record['away_team_id'],('',''))
    return dict(record,year=int(record['date'][:4]),era='2020_2024',home_region=hr,home_unit=hu,away_region=ar,away_unit=au,
        outcome=['home','draw','away'][int(record.get('outcome_index',1))],
        strength_difference=feature['strength_difference'],strength_difference_base_variance=feature['strength_difference_base_variance'],
        strength_difference_variance=feature['strength_difference_variance'],home_jump_intensity=feature['home_jump_intensity'],
        away_jump_intensity=feature['away_jump_intensity'],jump_scale_sd=feature['jump_scale_sd'],prediction_cutoff=feature['prediction_cutoff'])


def run():
    cfg_path='config/future_predictions.json';cfg=json.loads((ROOT/cfg_path).read_text(encoding='utf-8-sig'))
    inputs={cfg_path:file_hash(ROOT/cfg_path)}
    def take(p,expected=None):
        h=file_hash(ROOT/p)
        if expected is not None and h!=expected:raise ValueError('INPUT_CHANGED:'+p)
        inputs[p]=h;return ROOT/p
    raw=read_rows(take(cfg['raw_file'],cfg['raw_sha256']))
    base=cfg['checkpoint_directory'];man=json.loads(take(base+'/manifest.json').read_text(encoding='utf-8-sig'))
    states=json.loads(take(base+'/checkpoints.json',man['outputs']['checkpoints.json']).read_text(encoding='utf-8-sig'))
    state=states[cfg['checkpoint_date']]['state']
    if state['last_day']!=cfg['checkpoint_date']:raise ValueError('CHECKPOINT_CUTOFF_CHANGED')
    old_learning=read_rows(take(cfg['old_learning']));old_joint=read_rows(take(cfg['old_joint']))
    cross={r['source_team_id']:r for r in read_rows(take(cfg['crosswalk']))}
    registry={r['fifa_code']:r for r in read_rows(take(cfg['registry']))}
    pilot=json.loads(take('config/strength_pilot.json').read_text(encoding='utf-8-sig'))
    former=read_rows(take(pilot['former_names_path']))
    events={r['source_team_label']:r['start'] for r in json.loads(take(pilot['admission_events_path']).read_text(encoding='utf-8-sig'))['events']}
    fixtures=read_rows(take(cfg['fixture_file']));jointcfg=json.loads(take('config/strength_joint.json').read_text(encoding='utf-8-sig'))
    if len(fixtures)!=52 or Counter(r['round'] for r in fixtures)!=Counter({'5':26,'6':26}):raise ValueError('FIXTURE_SCOPE_CHANGED')
    files=['src/future_predictions.py','scripts/predict_future_matches.py','tests/test_future_predictions.py',
           'src/strength_predictive_validation.py','src/data_contract.py','src/history_window/replay.py','src/history_window/ratings.py',
           *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'src/strength').glob('*.py'))],
           *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'src/strength_joint').glob('*.py'))]]
    identity=dict(protocol=cfg,inputs=inputs,code={p:file_hash(ROOT/p) for p in files},environment=environment())
    rid='future-unl-'+fingerprint(identity)[:20];folder=ROOT/'outputs/logs/future_predictions'/rid
    table=ROOT/'outputs/tables/future_predictions'/rid
    folder.mkdir(parents=True,exist_ok=True);table.mkdir(parents=True,exist_ok=True)
    if (folder/'manifest.json').exists():
        for p,h in json.loads((folder/'manifest.json').read_text(encoding='utf-8-sig'))['outputs'].items():
            if file_hash(ROOT/p)!=h:raise ValueError('PREDICTION_SEAL_CHANGED')
        print('FORECAST_ALREADY_SEALED',rid,flush=True);return folder,table
    issued=datetime.now(timezone.utc).isoformat()
    # A run with a future fixture that is no longer prospective must not silently reissue.
    if issued[:10]>=min(r['date'] for r in fixtures):raise ValueError('PREDICTION_NOT_PROSPECTIVE')
    write_json(folder/'started.json',dict(identity=identity,issued_at_utc=issued))
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
        for p in files+[cfg_path,cfg['fixture_file']]:z.writestr(zipfile.ZipInfo(p,(1980,1,1,0,0,0)),(ROOT/p).read_bytes())
    atomic_bytes(folder/'source_snapshot.zip',buf.getvalue())
    try:
        ledger,games=update_records(raw,old_learning,cross,registry,state,cfg,pilot,former,events)
        engine=CollapsedJumpFilter.restore(state);geo=geo_map(old_joint)
        records={r['match_id']:r for r in ledger};new_joint=[];features=[];grouped=defaultdict(list)
        for g in games:grouped[g['date']].append(g)
        with numerical_cache(),threadpool_limits(limits=1):
            for n,(day,batch) in enumerate(sorted(grouped.items())):
                ff=before_day(engine,day,batch);features+=ff
                for f in ff:
                    r=records[f['match_id']]
                    if not r['is_neutral'] and all(r[s+'_team_id'] in geo for s in ['home','away']):
                        new_joint.append(as_joint(r,f,geo))
                engine.day(day,batch)
                if n%30==0:print('UPDATE_DATE',day,n,len(features),flush=True)
            write_json(folder/'rating_state.json',engine.state())
            train=old_joint+[r for r in new_joint if r['date']<cfg['model_training_end_exclusive']]
            train=sorted(train,key=lambda r:(r['date'],r['match_id']))
            if max(r['date'] for r in train)>=cfg['model_training_end_exclusive']:raise ValueError('COEFFICIENT_LEAKAGE')
            design=Design(train);models={}
            for model in cfg['models']:
                print('FIT_2026',model,len(train),flush=True)
                models[model]=fit_past(train,design,model,jointcfg['numerics'],cfg['ridge_precision'])
            targets=[]
            for i,r in enumerate(fixtures,1):
                ids={s:'team:'+team_slug(r[s+'_team']) for s in ['home','away']}
                ents={s:episode(r[s+'_team'],ids[s],r['date'],make_windows(pilot,former)) for s in ids}
                if any(t not in engine.index or engine.counts[t]<5 for t in ents.values()):raise ValueError('UNKNOWN_OR_COLD_TARGET')
                targets.append(dict(r,match_id='future:unl-2026:'+str(i).zfill(3),home=ents['home'],away=ents['away'],
                    home_team_id=ids['home'],away_team_id=ids['away'],venue=int(r['venue']),friendly=False,
                    tournament_group='non_friendly'))
            predicted=[]
            for g in targets:
                f=before_day(engine,g['date'],[g])[0]
                row=as_joint(g,f,geo)
                native=full_forecast(engine,g['date'],[g])[0]
                nativep=[native[k] for k in ['p_home','p_draw','p_away']]
                if abs(sum(nativep)-1)>1e-9 or min(nativep)<0:raise ValueError('INVALID_NATIVE_PROBABILITY')
                out=dict(match_id=g['match_id'],date=g['date'],round=int(g['round']),group=g['group'],home_team=g['home_team'],away_team=g['away_team'],
                    kickoff_cet=g['kickoff_cet'],issued_at_utc=issued,information_date_exclusive=cfg['information_date_exclusive'],
                    actual_latest_learning_date=engine.last_day,coefficient_training_max=max(r['date'] for r in train),
                    main_home_probability=None,main_nonhome_probability=None,main_pick='',main_status='withheld_third_country_venue' if not g['venue'] else 'issued_binary',
                    strength_reference_home_probability=None,latent_probability_p05=None,latent_probability_p95=None,
                    native_home_probability=nativep[0],native_draw_probability=nativep[1],native_away_probability=nativep[2],
                    native_pick=['home','draw','away'][int(np.argmax(nativep))],native_entropy=float(-sum(p*math.log(p) for p in nativep if p)/math.log(3)),
                    venue=g['venue'],venue_basis=g['venue_basis'],home_history=engine.counts[g['home']],away_history=engine.counts[g['away']],
                    strength_mean=f['strength_difference'],strength_sd=math.sqrt(f['strength_difference_variance']),
                    outcome_variance=None,round6_preliminary=int(g['round'])==6,
                    uncertainty_type='conditional latent-strength90, not confidence/parameter/model error interval',future_result_received=False)
                if g['venue']:
                    fitted=models['M3_nested'];p=float(predict(fitted,[row],design)[0]);ref=float(predict(models['M1_strength'],[row],design)[0])
                    x,_=design.matrix([row],'M3_nested');theta=np.array(fitted['theta']);eta=float(x[0]@theta[:-1]);b=float(np.exp(theta[-1]))
                    lo,hi=latent_probability_range(f['strength_difference'],f['strength_difference_base_variance'],f['home_jump_intensity']+f['away_jump_intensity'],f['jump_scale_sd'],eta,b,cfg['uncertainty_quantiles'])
                    out.update(main_home_probability=p,main_nonhome_probability=1-p,main_pick='home' if p>=.5 else 'nonhome',
                        strength_reference_home_probability=ref,latent_probability_p05=lo,latent_probability_p95=hi,outcome_variance=p*(1-p))
                predicted.append(out)
        if engine.last_day>=cfg['information_date_exclusive']:raise ValueError('RATING_LEAKAGE')
        csvs=dict(new_record_ledger=ledger,new_learning_matches=games,new_prematch_features=features,
                  new_analysis_matches=new_joint,forecasts=predicted)
        for name,rr in csvs.items():
            cols=list(dict.fromkeys(k for r in rr for k in r));atomic_bytes(table/(name+'.csv'),csv_bytes(cols,rr))
        write_json(folder/'models.json',dict(models=models,era_extension=cfg['era_extension'],training_ids_sha256=fingerprint([r['match_id'] for r in train]),training_rows=len(train)))
        write_json(table/'display_data.json',dict(run_id=rid,issued_at_utc=issued,forecasts=predicted,
            scope=cfg['primary_target'],native_threeway=cfg['native_threeway'],uncertainty_scope=cfg['uncertainty_scope'],
            scores_predicted=False,actual_results_available=False,formal_inference=False))
        review=dict(passed=True,new_raw_rows=len(ledger),included_learning_rows=len(games),
            excluded_or_pending=len(ledger)-len(games),new_analysis_rows=len(new_joint),coefficient_training_rows=len(train),
            coefficient_training_max=max(r['date'] for r in train),rating_last_day=engine.last_day,
            forecasts=len(predicted),primary_issued=sum(r['main_status']=='issued_binary' for r in predicted),
            withheld_main=sum(r['main_status']!='issued_binary' for r in predicted),native_auxiliary_forecasts=len(predicted),
            no_future_outcomes=True,new_fits=len(models),formal_inference=False,human_review=False,
            actual_postmatch_evaluation_complete=False,raw_overwritten=False,earlier_results_overwritten=False)
        write_json(folder/'review.json',review)
        write_json(folder/'manifest.json',dict(identity=identity,outputs={p.relative_to(ROOT).as_posix():file_hash(p) for d in [folder,table] for p in d.iterdir() if p.is_file() and p.name not in ['manifest.json','failure.json']}))
        write_json(ROOT/'outputs/logs/future_predictions/current.json',dict(run_id=rid,log_directory=folder.relative_to(ROOT).as_posix(),table_directory=table.relative_to(ROOT).as_posix(),issued_at_utc=issued,manifest_sha256=file_hash(folder/'manifest.json'),postmatch_pending=True))
        print('FORECAST_ISSUED',rid,json.dumps(review),flush=True)
        return folder,table
    except Exception as exc:
        write_json(folder/'failure.json',dict(type=type(exc).__name__,message=str(exc)));raise
