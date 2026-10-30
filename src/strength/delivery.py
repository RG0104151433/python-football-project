"""Final stage2 pipeline: archived jump scores, past shape fit, dynamic residual.

No joint era/tournament/geography outcome analysis is fitted here.
"""
from collections import defaultdict
from datetime import date
from pathlib import Path
import argparse
import json
import numpy as np
from .calibration import contextual_year,online_offsets
from .global_run import load,gate
from .baseline import frequency,fixed_step
from .experiment import score,calibration
from .io import ROOT,read_rows,publish,identify
from ..data_contract import file_hash,write_json


def run(strict=False):
    path=ROOT/'config/strength_final_delivery.json';protocol=json.loads(path.read_text(encoding='utf-8'))
    cfg,games,inputs=load('config/strength_global_v3.json');lookup={g['match_id']:g for g in games}
    source=ROOT/protocol['strict_source' if strict else 'normal_source']
    man=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    if file_hash(source/'prematch_features.csv')!=man['outputs']['prematch_features.csv']:raise ValueError('Score input changed')
    raw=read_rows(source/'prematch_features.csv');raw_report=json.loads((source/'report.json').read_text())
    params=raw_report['parameters'];ys=np.array([lookup[r['match_id']]['outcome'] for r in raw])
    years=np.array([int(r['date'][:4]) for r in raw]);cc=np.array([[int(lookup[r['match_id']]['friendly']),int(lookup[r['match_id']]['venue']==0)] for r in raw])
    pp=np.array([[float(r[k]) for k in ('p_home','p_draw','p_away')] for r in raw]);pp=np.maximum(pp,1e-12);pp/=pp.sum(axis=1,keepdims=True)
    shaped=pp.copy();shape_states=[];order=17 if strict else 9
    for year in range(1960,2026):
        past=(years>=year-10)&(years<year);now=years==year
        # Fit2025 state from existing history only, issue no2025 predictions.
        if now.any():predicted,states=contextual_year(pp[past],ys[past],cc[past],pp[now],cc[now],protocol['shape_method'],8,100,order);shaped[now]=predicted
        else:
            fake=np.ones((4,3))/3;contexts=np.array([[0,0],[0,1],[1,0],[1,1]])
            _,states=contextual_year(pp[past],ys[past],cc[past],fake,contexts,protocol['shape_method'],8,100,order)
        shape_states.extend(dict(year=year,training_end=year-1,**s) for s in states)
    mask=years>=1960;anchor=[r for i,r in enumerate(raw) if mask[i]]
    calibrated,offset_states=online_offsets(shaped[mask],ys[mask],[r['date'] for r in anchor],cc[mask],protocol['offset_diffusion'],order)
    final_pp=pp.copy();final_pp[mask]=calibrated
    day_state={(s['date'],s['friendly'],s['neutral']):s for s in offset_states}
    identity=dict(protocol_sha=file_hash(path),strict=strict,inputs=inputs,raw_source_manifest_sha=file_hash(source/'manifest.json'))
    prepared=identify('strength-delivery',identity,'data/processed/strength');features=[];last={}
    byday=defaultdict(list)
    for i,r in enumerate(raw):byday[r['date']].append((i,r))
    for day,rs in sorted(byday.items()):
        for i,r in rs:
            h,a=r['home'],r['away'];dh=(date.fromisoformat(day)-date.fromisoformat(last[h])).days if h in last else None
            da=(date.fromisoformat(day)-date.fromisoformat(last[a])).days if a in last else None
            mh=params['jump_rate']*(dh or 0)/365.2425;ma=params['jump_rate']*(da or 0)/365.2425
            totalv=float(r['difference_variance']);basev=totalv-(mh+ma)*params['jump_sd']**2
            if basev<=0:raise ValueError('Negative reconstructed base difference variance')
            cutoff=day_state[(day,int(cc[i,0]),int(cc[i,1]))]['prediction_cutoff'] if years[i]>=1960 else 'initial_prior'
            features.append(dict(r,raw_rating_run_id=r['rating_run_id'],rating_run_id=prepared[0],
                raw_p_home=r['p_home'],raw_p_draw=r['p_draw'],raw_p_away=r['p_away'],
                p_home=float(final_pp[i,0]),p_draw=float(final_pp[i,1]),p_away=float(final_pp[i,2]),
                shape_p_home=float(shaped[i,0]),shape_p_draw=float(shaped[i,1]),shape_p_away=float(shaped[i,2]),
                calibration_cutoff=cutoff,shape_information_cutoff=f'{years[i]-1}-12-31' if years[i]>=1960 else 'initial_prior',
                calibration_phase='shape_then_dynamic_residual' if years[i]>=1960 else 'warmup_identity',
                home_days_since_last=dh,away_days_since_last=da,home_jump_intensity=mh,away_jump_intensity=ma,
                jump_scale_sd=params['jump_sd'],difference_base_variance=basev,
                strength_distribution='normal_plus_compound_Poisson; total_variance_not_full_distribution',
                pipeline_rules_version='strength-final-v1'))
        for _,r in rs:last[r['home']]=day;last[r['away']]=day
    study={g['match_id'] for g in games if g['study']};sf=[r for r in features if r['match_id'] in study]
    if len(features)!=38919 or len(sf)!=24917:raise ValueError('Population changed')
    target_rows=[dict(r,outcome_index=lookup[r['match_id']]['outcome']) for r in features]
    freq=frequency(games,1950);elo=fixed_step(games,40,100,.75,1950);checks=[];types=[]
    for aa,bb in protocol['periods']:
        period=dict(id=f'reused_{aa}_{bb}',start=f'{aa}-01-01',end=f'{bb}-12-31')
        checks.extend(gate(target_rows,freq,elo,period,study,cfg))
        for fr in (False,True):
            rs=[r for r in target_rows if aa<=int(r['date'][:4])<=bb and r['match_id'] in study and lookup[r['match_id']]['friendly']==fr]
            bias=float(np.mean([r['p_home']-int(r['outcome_index']==0) for r in rs]));bins=calibration(rs,'final')
            error=max((abs(b['mean_probability']-b['observed_frequency']) for b in bins if b['count']>=200),default=0)
            types.append(dict(period=period['id'],friendly=fr,**score(rs),home_bias=bias,max_bin_error=error,passed=abs(bias)<=.03 and error<=.1))
    checkpoints={}
    for boundary in ('1979-12-31','1989-12-31','1999-12-31','2009-12-31','2019-12-31','2024-12-31'):
        selected={}
        for s in offset_states:
            if s['date']<=boundary:selected[(s['friendly'],s['neutral'])]=s
        next_year=int(boundary[:4])+1
        checkpoints[boundary]=dict(schema_version='strength-calibration-checkpoint-v1',asof=boundary,
            shape_for_next_year=[s for s in shape_states if s['year']==next_year],
            residual_states=list(selected.values()),raw_core_directory=source.relative_to(ROOT).as_posix(),
            raw_final_checkpoint_supplement=None if strict else protocol['raw_final_checkpoint_supplement'],
            purpose='precision_crosscheck_not_production_resume' if strict else 'production_research_resume')
    report=dict(protocol=protocol,strict=strict,raw_source=source.relative_to(ROOT).as_posix(),forecast_checks=checks,type_checks=types,
        all_forecast_gates_passed=all(r['passed'] for r in checks+types),rows=len(features),study_rows=len(sf),
        original_thresholds_changed=False,history_reused=True,prospective_test_performed=False,
        independent_audit_required_before_adoption=True,joint_outcome_model_fitted=False,
        uncertainty='score: conditional collapsed Poisson + Gaussian ADF; calibration: modular conditional Laplace/GH; not full joint Bayesian or real-world coverage guarantee')
    output,_=publish('strength-delivery',identity,prepared=prepared,base_dir='data/processed/strength',
        csvs={'prematch_features.csv':features,'study_prematch_features.csv':sf},
        jsons={'report.json':report,'checkpoints.json':checkpoints,'shape_states.json':shape_states},
        texts={'data_dictionary.md':'# 第二环节最终接口\n\n一场一行，score不含当前赛果。p_*为先形状后动态残差的最终三概率；raw_p_*为评分器原概率。rating_run_id绑定最终管线，raw_rating_run_id绑定底层评分器。difference_variance为含当前Poisson位移的总方差；difference_base_variance、双方jump_intensity及jump_scale_sd共同描述赛前差值分布，不能将总方差一个数当完整正态分布。校准没有修改潜在实力。home/away均值和协方差含底层当前跳变的边际未知。calibration_cutoff为动态残差之前日期，shape_information_cutoff为年度形状拟合截止。1950—1959校准为恒等热身，1960起先预测后更新。没有联合年代/赛事/地域效果或因果结果。\n'})
    write_json(ROOT/'outputs/logs/strength/repair-20261029'/('delivery_strict.json' if strict else 'delivery_normal.json'),dict(directory=output.relative_to(ROOT).as_posix(),manifest_sha=file_hash(output/'manifest.json')))
    print('FINAL_DELIVERY',output.relative_to(ROOT).as_posix(),report['all_forecast_gates_passed'],flush=True)
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--strict',action='store_true');run(p.parse_args().strict)
