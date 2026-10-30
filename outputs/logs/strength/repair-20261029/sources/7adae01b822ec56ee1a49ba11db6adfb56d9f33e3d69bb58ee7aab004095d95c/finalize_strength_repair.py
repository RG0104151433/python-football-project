"""Use verified stage2 results to publish adoption and same-version handoff only.

No joint outcome model or new era/tournament/geography effect is computed.
"""
from pathlib import Path
from collections import Counter
import itertools
import json
import sys
import xml.etree.ElementTree as ET
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.strength.io import read_rows,publish
from src.data_contract import file_hash,write_json


def run():
    out=ROOT/'outputs/logs/strength/repair-20261029'
    def js(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
    evidence=dict(raw_audit='outputs/logs/strength/repair-20261029/raw_jump_audit.json',
        final_audit='outputs/logs/strength/repair-20261029/final_delivery_audit.json',
        raw_replay='outputs/logs/strength/repair-20261029/replay_jump_full.json',
        final_replay='outputs/logs/strength/repair-20261029/delivery_reproducibility.json',
        local_reference='outputs/logs/strength/collapsed-jump-reference-13545517c92599400545/report.json',
        simulations='outputs/logs/strength/jump-repair-simulation-434a1b6d1bf4f3eb4d37/report.json',
        unseen_simulation='outputs/logs/strength/unseen-jump-validation-68be7631b8bd341ed48a/report.json')
    checks={k:js(p)['passed'] for k,p in evidence.items() if k!='simulations'}
    checks['simulation_selected_core']=js(evidence['simulations'])['engineering_simulation_gate_by_model']['jump_full']
    suite=ET.parse(out/'strength_tests.xml').getroot().find('testsuite')
    checks['tests']=int(suite.get('failures'))==0 and int(suite.get('errors'))==0
    normal=out/'delivery_normal.json';strict=out/'delivery_strict.json'
    nd=ROOT/json.loads(normal.read_text())['directory'];sd=ROOT/json.loads(strict.read_text())['directory']
    nr=json.loads((nd/'report.json').read_text());sr=json.loads((sd/'report.json').read_text())
    checks.update(normal_forecast=nr['all_forecast_gates_passed'],strict_forecast=sr['all_forecast_gates_passed'])
    if js(evidence['final_audit'])['normal']!=nd.relative_to(ROOT).as_posix():raise ValueError('Stale final audit')
    if js(evidence['final_replay'])['source_directory']!=nd.relative_to(ROOT).as_posix():raise ValueError('Stale repeat proof')
    initials={}
    for filename in ('initial_1960_1.0.json','initial_1950_0.5.json','initial_1950_2.0.json'):
        pointer=json.loads((out/filename).read_text());folder=ROOT/pointer['directory']
        rows=read_rows(folder/'study_differences.csv');initials[folder.name]={r['match_id']:r for r in rows}
        checks['initial_'+folder.name]=len(rows)==24917
        evidence['initial_'+folder.name]=pointer['directory']+'/manifest.json'
    if not all(checks.values()):raise RuntimeError('Stage2 gate failure: '+str(checks))
    facts_path=ROOT/'outputs/tables/regions/regions-0a1c61664a722e6c641f/analysis_matches.csv';facts=read_rows(facts_path)
    features={r['match_id']:r for r in read_rows(nd/'study_prematch_features.csv')}
    if len(features)!=24917 or {r['match_id'] for r in facts}!=features.keys():raise ValueError('Same-version join mismatch')
    retained=['match_id','date','year','era','tournament_group','home_team_id','away_team_id','home_team','away_team',
        'home_region','home_unit','away_region','away_unit','direction','relation','home_win','outcome','result_basis','source_record_id']
    joined=[]
    for f in facts:
        mid=f['match_id'];r=features[mid];variants=[index[mid] for index in initials.values()]
        if r['date']!=f['date']:raise ValueError('Date mismatch')
        maxchange=max(float(x['max_probability_change']) for x in variants)
        gaps=[float(r['difference']),*[float(x['difference']) for x in variants]]
        joined.append(dict(**{k:f[k] for k in retained},strength_difference=float(r['difference']),
            strength_difference_variance=float(r['difference_variance']),strength_difference_base_variance=float(r['difference_base_variance']),
            home_jump_intensity=float(r['home_jump_intensity']),away_jump_intensity=float(r['away_jump_intensity']),jump_scale_sd=float(r['jump_scale_sd']),
            home_rating_entity=r['home'],away_rating_entity=r['away'],home_variance=float(r['home_variance']),away_variance=float(r['away_variance']),
            home_away_covariance=float(r['home_away_covariance']),home_history=int(r['home_history']),away_history=int(r['away_history']),
            cold_start=r['cold_start']=='true',previously_disconnected=r['previously_disconnected']=='true',
            initialization_raw_probability_max_change=maxchange,initialization_sensitive=maxchange>.01,
            initialization_gap_min=min(gaps),initialization_gap_max=max(gaps),
            rating_run_id=r['rating_run_id'],raw_rating_run_id=r['raw_rating_run_id'],rating_rules_version=r['pipeline_rules_version'],
            prediction_cutoff=r['prediction_cutoff']))
    support=[]
    for key in ('era','tournament_group','home_region','away_region','home_unit','away_unit'):
        for level in sorted({r[key] for r in joined}):
            rs=[r for r in joined if r[key]==level];gaps=np.array([r['strength_difference'] for r in rs])
            support.append(dict(variable=key,level=level,matches=len(rs),cold_start=sum(r['cold_start'] for r in rs),
                initialization_sensitive=sum(r['initialization_sensitive'] for r in rs),
                score_min=float(gaps.min()),score_q05=float(np.quantile(gaps,.05)),score_median=float(np.median(gaps)),
                score_q95=float(np.quantile(gaps,.95)),score_max=float(gaps.max())))
    counts=Counter()
    for r in joined:
        b=int(np.searchsorted([-2,-1,0,1,2],r['strength_difference'],side='right'))
        counts[(r['era'],r['tournament_group'],r['home_region'],r['away_region'],b)]+=1
    cells=[]
    for e,t,h,a,b in itertools.product(sorted({r['era'] for r in joined}),['friendly','non_friendly'],
        sorted({r['home_region'] for r in joined}),sorted({r['away_region'] for r in joined}),range(6)):
        cells.append(dict(era=e,tournament_group=t,home_region=h,away_region=a,score_bin=b,matches=counts[(e,t,h,a,b)]))
    protocol=json.loads((ROOT/'config/strength_final_delivery.json').read_text())
    adoption=dict(status='all_required_stage2_engineering_gates_passed_ready_for_stage3_design',
        all_required_stage2_checks_passed=True,checks=checks,adopted_pipeline=nd.relative_to(ROOT).as_posix(),strict_pipeline=sd.relative_to(ROOT).as_posix(),
        selected_raw_core=nr['raw_source'],selected_shape_method=protocol['shape_method'],selected_residual_diffusion=protocol['offset_diffusion'],
        statistical_scope='reused-history development/engineering acceptance; not independent prospective or causal certification',
        all_old_failed_candidates_relabelled_pass=False,global_optimality_proven=False,prospective_test=False,human_review='not_performed',
        joint_outcome_fit_performed=False,tests_passed=int(suite.get('tests')),study_rows=24917,
        cold_start=sum(r['cold_start'] for r in joined),initialization_sensitive=sum(r['initialization_sensitive'] for r in joined),
        previously_disconnected=sum(r['previously_disconnected'] for r in joined),
        evidence={k:dict(path=p,sha256=file_hash(ROOT/p),embedded_path='proofs/'+k+'.json') for k,p in evidence.items()},
        test_report='tests.xml',
        source_forecast_metrics_unchanged=True,initialization_sensitivity_is_not_a_claim_of_point_invariance=True)
    packet,_=publish('joint-preparation',dict(normal_manifest_sha=file_hash(nd/'manifest.json'),strict_manifest_sha=file_hash(sd/'manifest.json'),
        region_source_sha=file_hash(facts_path),evidence=adoption['evidence'],tests_sha=file_hash(out/'strength_tests.xml'),runner_sha=file_hash(Path(__file__))),
        base_dir='data/processed/strength',csvs={'analysis_matches.csv':joined,'support.csv':support,'support_cells.csv':cells},
        jsons={'adoption.json':adoption,'interface.json':dict(status='handoff_only_no_joint_fit',
            distribution='normal_plus_compound_Poisson; do not replace by a normal with total variance',
            forbidden_predictors=['home_win','outcome','home_score','away_score','p_home','p_draw','p_away','home_term'],
            initialization_range_is_not_confidence_interval=True,score_support_bins=[-2,-1,0,1,2],
            old_q4_interval_reuse_allowed=False)},
        texts={'data_dictionary.md':'# 新版共同分析准备表\n\n仍为原24917场，非联合拟合结果。strength_difference为赛前差均值；base_variance与双方Poisson强度及jump_scale_sd给出当前分布，total_variance只是二阶摘要。目标home_win含平局分母，outcome为辅助三结果。初始化标记基于本轮完整跳变核心的原概率变动，不能当最终校准概率的置信区间或删行依据。support_cells仅场数，不产生地区胜率或第三环节结论。\n',
            'runner_snapshot.py':Path(__file__).read_text(encoding='utf-8'),
            'tests.xml':(out/'strength_tests.xml').read_bytes().decode('utf-8'),
            **{'proofs/'+k+'.json':(ROOT/p).read_bytes().decode('utf-8') for k,p in evidence.items()}})
    write_json(out/'adoption_pointer.json',dict(directory=packet.relative_to(ROOT).as_posix(),manifest_sha=file_hash(packet/'manifest.json')))
    print('ADOPTED',packet.relative_to(ROOT).as_posix(),json.dumps({k:v for k,v in adoption.items() if k not in ('checks','evidence')}),flush=True)
    return packet


if __name__=='__main__':run()
