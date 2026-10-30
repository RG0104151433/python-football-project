"""Past-only annual forecasts for the fixed Q5 scoring/model family.

All historical periods have already informed research choices. These are
retrospective rolling forecasts, not a new untouched real-world holdout.
"""
from pathlib import Path
import json,time,io,zipfile
import numpy as np
from scipy.optimize import minimize
from scipy.special import log_ndtr
from src.data_contract import atomic_bytes,csv_bytes,file_hash,fingerprint,write_json
from src.strength.io import ROOT,environment
from src.strength_joint.contract import load
from src.strength_joint.design import Design
from src.strength_joint.model import Kernel,objective,slopes,predict


def fit_past(rows,design,model,numerics,precision=1.):
    x,names=design.matrix(rows,model);kernel=Kernel(rows);s=slopes(rows,model)
    y=np.array([int(r['home_win']) for r in rows]);trials=[]
    bound=numerics['coefficient_bound'];bounds=[(-bound,bound)]*len(names)+[(np.log(.0001),np.log(8.))]*s.shape[1]
    def penalized(theta):
        loss,gradient=objective(theta,x,kernel,y,s)
        return loss+precision*np.dot(theta,theta)/(2*len(y)),gradient+precision*theta/len(y)
    for initial in numerics['starts']:
        theta=np.r_[np.zeros(len(names)),np.full(s.shape[1],np.log(initial))]
        result=minimize(penalized,theta,jac=True,method='L-BFGS-B',bounds=bounds,
            options=dict(maxiter=1200,gtol=1e-8,ftol=1e-14,maxls=40,maxcor=30))
        loss,g=penalized(result.x)
        trials.append(dict(theta=result.x.tolist(),loss=loss,gradient=float(max(abs(g))),success=bool(result.success)))
    best=min(trials,key=lambda r:r['loss']);spread=max(r['loss'] for r in trials)-best['loss']
    if not best['success'] or best['gradient']>3e-6 or spread>1e-8:
        raise ValueError('ROLLING_FIT_FAILED: '+repr(dict(model=model,trials=trials)))
    return dict(model_id=model,mode='mixture',theta=best['theta'],names=names,
        slope_names=[] if not s.shape[1] else ['log_b'],trials=trials,
        ridge_precision=precision,rows=len(rows),past_date_max=max(r['date'] for r in rows),
        future_only_columns=[name for name,column in zip(names,x.T) if not np.any(column)],
        multistart_loss_spread=spread,numerical_fit_passed=True)


def metrics(rr):
    p=np.array([float(r['probability']) for r in rr]);y=np.array([int(r['home_win']) for r in rr])
    pp=np.clip(p,1e-15,1-1e-15)
    return dict(matches=len(rr),log_loss=float(-np.mean(y*np.log(pp)+(1-y)*np.log1p(-pp))),
        brier=float(np.mean((p-y)**2)),binary_accuracy=float(np.mean((p>=.5)==y)),
        mean_probability=float(p.mean()),observed_home_win_rate=float(y.mean()),
        calibration_bias_pp=100*float(p.mean()-y.mean()),numerical_probability_clips=int(np.sum(p!=pp)))


def run():
    started=time.perf_counter();cfg,rows,_,_,inputs=load()
    protocol=dict(schema_version='strength-past-only-prediction-v2',decision_log_id='R20261031-03',
        first_forecast_year=1990,last_forecast_year=2024,training_start=1980,
        refit='once each year; no same-year fitting outcomes; raw strength updates use prior dates only',
        models=['M0_nested','M1_strength','M3_nested'],ridge_precision=1.,
        vocabulary='each year constructs Design from training rows only; unseen fine units use region-centred zero effect; unobserved fixed-schema columns use ridge zero prior',
        geographic_encoding_weights_use_past_only=True,
        target='home win versus draw/away; not full WDL',historical_choices_reused=True,new_blind_holdout=False)
    source_paths=[ROOT/'src/strength_predictive_validation.py',ROOT/'scripts/analyze_strength_predictive_validation.py',
        *ROOT.glob('src/strength_joint/*.py'),ROOT/'src/data_contract.py']
    identity=dict(protocol=protocol,inputs=inputs,code={p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(source_paths)},environment=environment())
    folder=ROOT/'outputs/tables/strength_joint'/('rolling-prediction-'+fingerprint(identity)[:20])
    predictions=[];models={};yearly=[]
    for year in range(1990,2025):
        train=[r for r in rows if int(r['year'])<year];test=[r for r in rows if int(r['year'])==year]
        design=Design(train)
        for model in protocol['models']:
            fitted=fit_past(train,design,model,cfg['numerics']);models[f'{year}:{model}']=fitted
            fitted['encoding']=dict(training_rows=len(train),date_max=max(r['date'] for r in train),uses_test_rows=False,
                anchors={side+':'+region:unit for (side,region),unit in design.anchor.items()},
                weights={side+':'+region+':'+unit:value for (side,region,unit),value in design.weights.items()},
                unseen_test_home_units=sum(r['home_unit'] not in design.units.get(('home',r['home_region']),[]) for r in test),
                unseen_test_away_units=sum(r['away_unit'] not in design.units.get(('away',r['away_region']),[]) for r in test))
            p=predict(fitted,test,design)
            rr=[dict(match_id=r['match_id'],date=r['date'],year=year,era=r['era'],tournament_group=r['tournament_group'],
                home_region=r['home_region'],home_unit=r['home_unit'],model_id=model,home_win=int(r['home_win']),
                probability=float(v),training_date_max=fitted['past_date_max'],strength_prediction_cutoff=r['prediction_cutoff'],
                scope='retrospective_past_only_annual_binary_forecast') for r,v in zip(test,p)]
            predictions.extend(rr);yearly.append(dict(year=year,model_id=model,**metrics(rr)))
        print('ROLLING_YEAR_COMPLETE',year,len(train),len(test),flush=True)
    comparisons=[];calibration=[]
    for model in protocol['models']:
        rr=[r for r in predictions if r['model_id']==model]
        comparisons.append(dict(group='all',model_id=model,**metrics(rr)))
        for field in ('era','tournament_group','home_region'):
            for value in sorted({r[field] for r in rr}):
                ss=[r for r in rr if r[field]==value]
                comparisons.append(dict(group=field+':'+value,model_id=model,**metrics(ss)))
        for bin_index in range(10):
            ss=[r for r in rr if min(int(r['probability']*10),9)==bin_index]
            if ss:calibration.append(dict(model_id=model,bin_lower=bin_index/10,bin_upper=(bin_index+1)/10,**metrics(ss)))
    content={'predictions.csv':csv_bytes(list(predictions[0]),predictions),'yearly_metrics.csv':csv_bytes(list(yearly[0]),yearly),
        'group_metrics.csv':csv_bytes(list(comparisons[0]),comparisons),'calibration_bins.csv':csv_bytes(list(calibration[0]),calibration),
        'models.json':(json.dumps(models,sort_keys=True,indent=2,allow_nan=False)+'\n').encode(),
        'protocol.json':(json.dumps(protocol,sort_keys=True,indent=2)+'\n').encode()}
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
        for name in identity['code']:z.writestr(zipfile.ZipInfo(name,(1980,1,1,0,0,0)),(ROOT/name).read_bytes())
    content['source_snapshot.zip']=buf.getvalue()
    for name,data in content.items():
        if (folder/name).exists() and (folder/name).read_bytes()!=data:raise ValueError('ROLLING_OUTPUT_COLLISION')
        atomic_bytes(folder/name,data)
    write_json(folder/'manifest.json',dict(identity=identity,outputs={name:file_hash(folder/name) for name in content}))
    write_json(ROOT/'outputs/logs/strength_inference/prediction_pointer.json',dict(directory=folder.relative_to(ROOT).as_posix(),manifest_sha256=file_hash(folder/'manifest.json'),
        seconds=time.perf_counter()-started,formal_new_future_validation=False))
    print('ROLLING_COMPLETE',folder.relative_to(ROOT).as_posix(),flush=True)
