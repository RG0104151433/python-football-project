"""Stage6 steps1/2 and step3 inputs only: no score replay, fitting or intervals."""
from collections import Counter, defaultdict
from datetime import date
from fractions import Fraction
from pathlib import Path
import gzip
import io
import json
import math
import zipfile
import numpy as np
from src.data_contract import csv_bytes, atomic_bytes, file_hash, fingerprint, write_json
from src.strength.io import ROOT, read_rows, environment
from src.strength.global_run import load as load_learning
from src.strength_joint.contract import load as load_joint
from src.strength_joint.contrasts import recipes
from src.strength_joint.design import Support, group_matches


def timeline(games, start):
    """Outcome-free prior dates/counts. ALL appearances on a date precede updates."""
    batches=defaultdict(list)
    for g in games:
        if int(g['date'][:4])>=start:batches[g['date']].append(g)
    last={};counts=Counter();previous=None;out={}
    for day,gs in sorted(batches.items()):
        for g in gs:
            h,a=g['home'],g['away']
            out[g['match_id']]=dict(date=day,home_entity=h,away_entity=a,
                prediction_cutoff=previous or 'initial_prior',home_previous_date=last.get(h,''),away_previous_date=last.get(a,''),
                home_elapsed_years=(date.fromisoformat(day)-date.fromisoformat(last.get(h,day))).days/365.2425,
                away_elapsed_years=(date.fromisoformat(day)-date.fromisoformat(last.get(a,day))).days/365.2425,
                home_history=counts[h],away_history=counts[a])
        for g in gs:
            for side in ('home','away'):counts[g[side]]+=1;last[g[side]]=day
        previous=day
    return out


def decompose(total, nh, na, scale):
    base=total-(nh+na)*scale*scale
    if not math.isfinite(base) or base<=0 or min(nh,na,scale)<0:raise ValueError('Invalid reconstructed score distribution')
    return base


def verify_manifest(folder):
    folder=Path(folder);m=json.loads((folder/'manifest.json').read_text())
    for name,h in m['outputs'].items():
        if file_hash(folder/name)!=h:raise ValueError('Input artifact changed: '+str(folder/name))
    return m


def reference_id(reference, rule, kind):
    return 'reference-'+fingerprint(dict(rule=rule,kind=kind,rows=[(r['match_id'],r['strength_difference'],
        r['strength_difference_base_variance'],r['home_jump_intensity'],r['away_jump_intensity'],r['jump_scale_sd']) for r in reference]))[:20]


def concentration(rs):
    n=len(rs);out={}
    for field in ('year','home_team_id','away_team_id'):
        counts=Counter(r[field] for r in rs)
        out[field+'_categories']=len(counts)
        out[field+'_largest_share']=max(counts.values())/n if n else None
        out[field+'_hhi']=sum((c/n)**2 for c in counts.values()) if n else None
    return out


def mixture_fraction(target, arm_index, scenario, reference, rows, geography):
    tid=target['target_id']
    if not tid.startswith('Q3:'):return Fraction(1,1)
    comp=next(c for c in geography['comparisons'] if c['id']==target['source_row_key'])
    group=geography['groups'][comp['arm1' if arm_index==1 else 'arm2']]
    if comp['id'].startswith('B_'):
        h=scenario[0]['home_unit'];a=scenario[0]['away_unit']
        cc=Counter(r['away_unit'] for r in rows if r['home_unit']==h and r['away_unit'] and group_matches(r,group))
        return Fraction(len(scenario)*cc[a],len(reference)*sum(cc.values()))
    cc=Counter(r['home_unit'] for r in rows if group_matches(r,group))
    return Fraction(cc[scenario[0]['home_unit']],sum(cc.values()))


def references(rows, targets, geography, design, joint_cfg, main_contrasts):
    support=Support(rows,joint_cfg['support_bins'],joint_cfg['sparse_cell_warning'])
    saved={(r['target_id'],r['reference_kind']):r for r in main_contrasts if r['model_id']=='M3_nested'}
    unique={};scopes=[];mixtures=[]
    for t in targets:
        ref,arms,rule,label=recipes(t,rows,geography,design)
        if arms is None:raise ValueError('Unexpected absent target recipe')
        bad=set()
        for arm in arms:
            for _,rr in arm:
                zero,_,outside=support.flags(rr)
                bad.update(r['match_id'] for r,z,o in zip(rr,zero,outside) if z or o)
        narrow=[r for r in ref if r['match_id'] not in bad]
        if not narrow:raise ValueError('Empty existing overlap reference')
        for kind,current in [('full',ref),('cell_range_overlap',narrow)]:
            rr,aa,rule,label=recipes(t,rows,geography,design,current)
            rid=reference_id(rr,rule,kind);original=saved[t['target_id'],kind]
            if rid!=original['reference_id'] or len(rr)!=int(original['reference_rows']):raise ValueError('Reference differs from adopted result')
            ids=[r['match_id'] for r in rr]
            if rid in unique and unique[rid]!=ids:raise ValueError('Reference ID collision')
            unique[rid]=ids
            record=dict(target_id=t['target_id'],reference_kind=kind,reference_id=rid,label=label,
                fitted_matches=24917,reference_rows=len(rr),full_parent_reference_rows=len(ref),retained_fraction=len(rr)/len(ref),
                original_status=t['status'],reference_selection='frozen baseline IDs and exact equal weights; no alternate-score re-selection',
                home_unknown=sum(not r['home_region'] for r in rr),away_unknown=sum(not r['away_region'] for r in rr),
                cold_start=sum(r['cold_start']=='true' for r in rr),previously_disconnected=sum(r['previously_disconnected']=='true' for r in rr),
                initialization_sensitive=sum(r['initialization_sensitive']=='true' for r in rr),
                date_min=min(r['date'] for r in rr),date_max=max(r['date'] for r in rr),
                era_categories=len({r['era'] for r in rr}),type_categories=len({r['tournament_group'] for r in rr}),**concentration(rr))
            for armnum,arm in enumerate(aa,1):
                mass=Fraction(0,1);flags_mass=np.zeros(4);row_mass=defaultdict(float)
                for k,(weight,ss) in enumerate(arm):
                    fraction=mixture_fraction(t,armnum,ss,rr,rows,geography)
                    if abs(float(fraction)-weight)>1e-14:raise ValueError('Scenario mixture differs')
                    mass+=fraction
                    z,s,o=support.flags(ss);flags_mass+=float(fraction)*np.array([z.mean(),s.mean(),o.mean(),np.mean(z|o)])
                    for x in ss:row_mass[x['match_id']]+=float(fraction)/len(ss)
                    fields={}
                    for field in ('era','tournament_group','home_region','home_unit','away_region','away_unit'):
                        values={x[field] for x in ss};fields[field+'_constant']=next(iter(values)) if len(values)==1 else '__varies__'
                    mixtures.append(dict(target_id=t['target_id'],reference_kind=kind,reference_id=rid,arm=armnum,piece=k,
                        piece_reference_rows=len(ss),weight_numerator=fraction.numerator,weight_denominator=fraction.denominator,**fields))
                if mass!=1 or set(row_mass)!=set(ids) or max(abs(v-1/len(rr)) for v in row_mass.values())>1e-14:raise ValueError('Scenario weights do not preserve reference')
                for field,value in zip(('zero_cell_fraction','sparse_cell_fraction','outside_score_range_fraction','unsupported_union_fraction'),flags_mass):
                    record[f'arm{armnum}_{field}']=float(value)
                for field in ('zero_cell_fraction','sparse_cell_fraction','outside_score_range_fraction'):
                    if abs(record[f'arm{armnum}_{field}']-float(original[f'arm{armnum}_{field}']))>2e-8:raise ValueError('Support diagnostic changed')
            record['evidence_scope']='MODEL_CONDITIONAL_EXTRAPOLATION' if kind=='full' else 'NARROW_REFERENCE_CONDITIONAL_NOT_GENERAL_POPULATION'
            record['original_missing_support_restored']=False
            record['interval_admission']='NOT_ADMITTED'
            record['limitation']='coarse cells omit opponent-unit detail and uncertainty axes; nonempty cells/ranges not sufficient overlap proof'
            if t['source_row_key']=='B_SA':record['limitation']+='; auxiliary8 are reference rows, not training sample; do not generalize to all South America'
            scopes.append(record)
        print('STAGE6_REFERENCE',t['target_id'],len(ref),len(narrow),flush=True)
    membership=[dict(reference_id=rid,match_id=mid,weight_numerator=1,weight_denominator=len(ids)) for rid,ids in sorted(unique.items()) for mid in ids]
    return scopes,mixtures,membership


def registry(contrasts, changes, curve_rows, models, layer_rows, cfg):
    rows=[];change_index={(r['target_id'],r['reference_kind']):r for r in changes}
    template=dict(role='',family='',target_id='',reference_id='',reference_kind='',model_id='',estimand='',null='',estimate=None,unit='',
        effect_size_axis='',main_or_auxiliary='',historical_results_seen=True,inference_status='NOT_ADMITTED',
        error_control='must be fixed before inference; family membership frozen',reference_randomness='conditional empirical reference; further treatment pending',
        paired_models_required=False,independent_confirmation=False)
    def add(**kw):rows.append(dict(template,**kw))
    for r in contrasts:
        if r['model_id']!='M3_nested':continue
        tid=r['target_id'];kind=r['reference_kind']
        family='F_AUX_REFERENCE' if kind!='full' else 'F_PRIMARY_CONDITIONAL' if r['old_target_status']=='supported_point_target' else 'F_EXTRAPOLATION_ONLY'
        for effect in ('level','paired_change'):
            value=float(r['difference_pp']) if effect=='level' else float(change_index[tid,kind]['change_pp'])
            add(registry_id='S6:'+effect+':'+tid+':'+kind,role='conditional_inference_candidate',family=family,target_id=tid,
                reference_id=r['reference_id'],reference_kind=kind,model_id='M3_nested' if effect=='level' else 'M3_nested_minus_M0_nested',
                estimand='delta_M3' if effect=='level' else 'delta_M3 - delta_M0; signed change, not absolute shrinkage or causal explanation',
                null='estimand=0',estimate=value,unit='percentage_points',effect_size_axis=effect,
                main_or_auxiliary=family,paired_models_required=effect=='paired_change')
    result=models[cfg['relation_model']];coef=dict(zip(result['names']+result['slope_names'],result['theta']))
    ref=next(r['reference_id'] for r in curve_rows if r['model_id']==cfg['relation_model'])
    add(registry_id='S6:relation:log_slope',role='post_exploration_hypothesis',family='F_EXPLORATORY_RELATIONS',
        model_id=cfg['relation_model'],estimand='log(b_friendly)-log(b_other)',null='log slope difference=0',
        estimate=coef['log_b_friendly']-coef['log_b_nonfriendly'],unit='log_latent_slope',effect_size_axis='latent_slope_not_probability_interaction',main_or_auxiliary='exploratory')
    index={float(r['strength_mean']):r for r in curve_rows if r['model_id']==cfg['relation_model']}
    for d in cfg['relation_mean_points']:
        add(registry_id='S6:relation:probability_at_'+str(d),role='post_exploration_hypothesis',family='F_EXPLORATORY_RELATIONS',
            reference_id=ref,reference_kind='curve_scenario',model_id=cfg['relation_model'],estimand=f'C({d})=P_H(friendly,{d})-P_H(other,{d})',
            null='probability difference=0',estimate=float(index[d]['friendly_minus_other_pp']),unit='percentage_points',main_or_auxiliary='exploratory',effect_size_axis='probability_difference')
    for d in [x for x in cfg['relation_mean_points'] if x!=0]:
        add(registry_id='S6:relation:probability_change_'+str(d),role='post_exploration_hypothesis',family='F_EXPLORATORY_RELATIONS',
            reference_id=ref,reference_kind='curve_scenario',model_id=cfg['relation_model'],estimand=f'C({d})-C(0); can vary even with common latent slope',
            null='probability difference change=0',estimate=float(index[d]['friendly_minus_other_pp'])-float(index[0]['friendly_minus_other_pp']),
            unit='percentage_points',main_or_auxiliary='exploratory',effect_size_axis='probability_heterogeneity_not_latent_slope_test')
    add(registry_id='S6:relation:25point_grid',role='post_exploration_grid_object',family='F_EXPLORATORY_RELATIONS',reference_id=ref,
        reference_kind='curve_scenario',model_id=cfg['relation_model'],estimand='joint uncertainty for C(d) at25 existing grid points; NOT continuum band or universal crossing threshold',
        unit='percentage_points_grid',main_or_auxiliary='exploratory',effect_size_axis='grid_only',null='grid null/coverage definition to be chosen in inference protocol')
    for r in layer_rows:
        add(registry_id='S6:descriptive:'+r['comparison_id'],role='descriptive_only_not_a_formal_test',family='F_DESCRIPTIVE_FIT',
            model_id=r['after_model']+'_minus_'+r['before_model'],estimand=r['comparison_id'],estimate=float(r['loss_reduction']),
            unit='mean_binary_log_loss_reduction',main_or_auxiliary='descriptive',error_control='not applicable; do not treat training fit gain as future validation')
    if len(rows)!=143 or len({r['registry_id'] for r in rows})!=143:raise ValueError('Registry count/identity failure')
    return rows


def score_inputs(rows, games, joint_cfg):
    study_ids={r['match_id'] for r in rows};base_folder=ROOT/joint_cfg['raw_score'];base_m=verify_manifest(base_folder)
    base_report=json.loads((base_folder/'report.json').read_text());params=base_report['parameters']
    variants=[('baseline',1950,1.,base_folder,'study_prematch_features.csv',False)]
    for directory in joint_cfg['initializations']:
        path=ROOT/directory;manifest=verify_manifest(path);identity=manifest['identity'];report=json.loads((path/'report.json').read_text())
        if identity['adopted_manifest_sha']!=file_hash(base_folder/'manifest.json') or identity['inputs']!=base_m['identity']['inputs']:raise ValueError('Initialization provenance mismatch')
        if identity['start']!=report['start'] or identity['variance']!=report['variance']:raise ValueError('Initialization config mismatch')
        for name in ('src/strength/collapsed_jump.py','src/strength/gaussian.py','src/strength/filter.py'):
            if fingerprint((ROOT/name).read_text(encoding='utf-8').replace('\r\n','\n'))!=manifest['identity']['code'][name]:raise ValueError('Score implementation changed')
        variants.append((path.name,int(report['start']),float(report['variance']),path,'study_differences.csv',True))
    variants.append(('weak_jump',1950,1.,ROOT/joint_cfg['weak_jump_score'],'study_prematch_features.csv',False))
    csvs={};reports=[];inputs={};baseline={r['match_id']:r for r in rows}
    for label,start,variance,folder,filename,is_initial in variants:
        manifest=verify_manifest(folder);source=read_rows(folder/filename);index={r['match_id']:r for r in source}
        if len(source)!=24917 or set(index)!=study_ids:raise ValueError('Score variant population mismatch')
        p=params if is_initial else json.loads((folder/'report.json').read_text())['parameters']
        if not is_initial and manifest['identity']['inputs']!=base_m['identity']['inputs']:raise ValueError('Learning identity mismatch')
        dates=timeline(games,start);out=[];max_base=0.;max_nu=0.;max_mean=0.
        for r in rows:
            mid=r['match_id'];old=index[mid];prior=dates[mid]
            if old['date']!=r['date'] or any(int(old[k])!=prior[k] for k in ('home_history','away_history')):raise ValueError('Prior date/history mismatch')
            if not is_initial and old['prediction_cutoff']!=prior['prediction_cutoff']:raise ValueError('Cutoff mismatch')
            nh=p['jump_rate']*prior['home_elapsed_years'];na=p['jump_rate']*prior['away_elapsed_years'];total=float(old['difference_variance']);sd=p['jump_sd']
            v0=decompose(total,nh,na,sd)
            row=dict(variant_id=label,match_id=mid,date=r['date'],home_entity=prior['home_entity'],away_entity=prior['away_entity'],
                strength_difference=float(old['difference']),strength_difference_variance=total,strength_difference_base_variance=v0,
                home_jump_intensity=nh,away_jump_intensity=na,jump_scale_sd=sd,prediction_cutoff=prior['prediction_cutoff'],
                home_previous_date=prior['home_previous_date'],away_previous_date=prior['away_previous_date'],home_history=prior['home_history'],away_history=prior['away_history'],
                cold_start=min(prior['home_history'],prior['away_history'])<5,start_year=start,initial_team_variance=variance,
                distribution_scope='per_match_marginal_only_not_cross_match_joint_posterior')
            if row['prediction_cutoff']>=row['date']:raise ValueError('Future information')
            if label=='baseline':
                max_base=max(max_base,abs(v0-float(r['strength_difference_base_variance'])))
                max_nu=max(max_nu,abs(nh-float(r['home_jump_intensity'])),abs(na-float(r['away_jump_intensity'])))
                max_mean=max(max_mean,abs(row['strength_difference']-float(r['strength_difference'])))
                if row['home_entity']!=r['home_rating_entity'] or row['away_entity']!=r['away_rating_entity']:raise ValueError('Entity mismatch')
            out.append(row)
        if label=='baseline' and (max_base>2e-8 or max_nu>2e-8 or max_mean>2e-9):raise ValueError('Baseline reconstruction not verified')
        name='score_inputs_'+label+'.csv.gz';csvs[name]=out
        reports.append(dict(variant_id=label,start=start,initial_variance=variance,rows=len(out),source=folder.relative_to(ROOT).as_posix(),
            prepared_file=name,complete_marginal_available=True,cross_match_joint_posterior_recovered=False,new_score_run=False,refit_performed=False,
            baseline_max_base_variance_error=max_base if label=='baseline' else None,baseline_max_jump_intensity_error=max_nu if label=='baseline' else None,
            baseline_max_mean_error=max_mean if label=='baseline' else None,cold_start_rows=sum(x['cold_start'] for x in out),
            minimum_base_variance=min(x['strength_difference_base_variance'] for x in out)))
        inputs[(folder/'manifest.json').relative_to(ROOT).as_posix()]=file_hash(folder/'manifest.json')
        print('STAGE6_SCORE_INPUT',label,len(out),flush=True)
    return csvs,reports,inputs


def run(config_path='config/strength_stage6_preparation.json'):
    cfg=json.loads((ROOT/config_path).read_text());analysis=ROOT/cfg['analysis'];interp=ROOT/cfg['interpretation']
    if file_hash(analysis/'manifest.json')!=cfg['analysis_manifest_sha256'] or file_hash(interp/'manifest.json')!=cfg['interpretation_manifest_sha256']:raise ValueError('Frozen analysis mismatch')
    verify_manifest(analysis);verify_manifest(interp)
    joint_cfg,rows,targets,geography,inputs=load_joint(cfg['joint_config'])
    from src.strength_joint.design import Design
    main=read_rows(analysis/'contrasts.csv');changes=read_rows(analysis/'strength_changes.csv');curve=read_rows(interp/'tournament_curve_differences.csv')
    models=json.loads((analysis/'models.json').read_text())
    reg=registry(main,changes,curve,models,read_rows(interp/'layer_comparisons.csv'),cfg)
    scopes,mixtures,membership=references(rows,targets,geography,Design(rows),joint_cfg,main)
    learning_cfg,games,learning_inputs=load_learning(joint_cfg['learning_config'])
    score_csvs,score_report,score_sources=score_inputs(rows,games,joint_cfg)
    masks=[];mask_counts=Counter()
    for r in rows:
        flags=dict(cold_start=r['cold_start']=='true',weak_connection=r['previously_disconnected']=='true',
            unknown_home=not r['home_region'],unknown_away=not r['away_region'],initialization_mean_sensitive=r['initialization_sensitive']=='true')
        for k,v in flags.items():mask_counts[k]+=v
        mask_counts['any_flag']+=any(flags.values())
        masks.append(dict(match_id=r['match_id'],date=r['date'],**flags,scope='baseline flags; not exclusion decisions'))
    curve_support=[r for r in read_rows(interp/'strength_curves.csv') if r['model_id']==cfg['relation_model']]
    families=Counter(r['family'] for r in reg)
    expected={'F_PRIMARY_CONDITIONAL':54,'F_AUX_REFERENCE':64,'F_EXTRAPOLATION_ONLY':10,'F_EXPLORATORY_RELATIONS':7,'F_DESCRIPTIVE_FIT':8}
    if dict(families)!=expected:raise ValueError('Family count mismatch')
    csvs={'target_registry.csv':reg,'reference_scope.csv':scopes,'scenario_mixtures.csv':mixtures,
        'reference_membership.csv.gz':membership,'baseline_flags.csv.gz':masks,'curve_support.csv':curve_support,**score_csvs}
    notes=dict(steps1_2_complete=True,step3_inputs_prepared=True,step3_sensitivity_refits_performed=False,scoring_run_performed=False,
        intervals_computed=False,formal_error_control_selected=False,stage6_complete=False,family_counts=dict(families),
        registry_rows=len(reg),scope_rows=len(scopes),unique_references=len({r['reference_id'] for r in scopes}),membership_rows=len(membership),
        scenario_mixture_rows=len(mixtures),mask_counts=dict(mask_counts),score_variants=score_report,
        reference_scope='conditional on frozen empirical reference; do not freeze generated training score path in uncertainty experiments',
        sensitivity_rule=cfg['sensitivity_reference_rule'],known_support_limits=['coarse cells omit away-unit and uncertainty dimensions','nonempty cells and min/max not sufficient overlap proof','reference rows not independent training observations','unknown and history masks overlap; do not sum as distinct excluded matches'],
        unresolved=['inference method and joint family error control','nominal confidence level and simulation acceptance thresholds','additional reference-estimation uncertainty','cross-match posterior/feedback propagation','design identifiability after cold/unknown subset restriction'],
        main_hypotheses_are_not_preregistered_blind_confirmation=True,actual_human_review=False)
    inputs.update(learning_inputs);inputs.update(score_sources);inputs.update({config_path:file_hash(ROOT/config_path),cfg['analysis']+'/manifest.json':file_hash(analysis/'manifest.json'),cfg['interpretation']+'/manifest.json':file_hash(interp/'manifest.json')})
    files=[ROOT/'src/strength_stage6_prepare.py',ROOT/'scripts/prepare_strength_stage6.py',ROOT/'scripts/audit_strength_stage6_preparation.py',ROOT/'tests/test_strength_stage6_prepare.py',ROOT/config_path,
           ROOT/'src/data_contract.py',ROOT/'src/strength/io.py',ROOT/'src/strength/global_run.py',*ROOT.glob('src/strength_joint/*.py')]
    source={p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(files)}
    identity=dict(protocol=cfg,inputs=inputs,code=source,environment=environment());ident='stage6-preparation-'+fingerprint(identity)[:20]
    dest=ROOT/'outputs/tables/strength_joint'/ident;content={}
    for name,rr in csvs.items():
        value=csv_bytes(list(rr[0]),rr)
        content[name]=gzip.compress(value,mtime=0) if name.endswith('.gz') else value
    content['readiness.json']=(json.dumps(notes,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')
    content['data_dictionary.md']=('''# 第六环节第一二步与第三步信息准备\n\n登记143项，其中8项拟合改善只描述，不是143次检验已完成。27原可算目标的全参考水平/配对变化54项为主要模型条件族，64窄参考辅助，原缺层10全参考项只外推，另7项关系探索。置信水平/同时误差控制尚未选择，全部NOT_ADMITTED。\nreference_scope保留32x2原参考的覆盖/集中度与支持限制。reference_membership按reference_id去重，权重用精确整数1/N记录，成员不是独立训练样本；scenario_mixtures用有理数记录原合法情景混合质量。下轮不能重新筛交集后冒充原目标。\nscore_inputs包含每场均值、基础方差、双方跳变强度/尺度、总方差与此前日期。由冻结赛程和已保存评分结果重建，无新评分或拟合；仅完整边际，不恢复跨比赛协方差/联合后验。初始化方差列为配置起点，不是当前评分方差。\nbaseline_flags的冷启动/连接/地理/原均值敏感标记可重叠，不是删除决定。curve_support计数是均值附近场数，不是充分支持，25点网格不是连续全域保证。\n所有CSV底层UTF-8 BOM、LF、浮点10位；csv.gz为标准gzip(mtime0)，可由Python gzip读或解压后查看。原评分、数据和结果未覆盖，readiness描述当前真正完成边界。\n''').encode('utf-8')
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
        for name in sorted(source):z.writestr(zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)),(ROOT/name).read_bytes())
    content['source_snapshot.zip']=buf.getvalue()
    for name,value in content.items():
        if (dest/name).exists() and (dest/name).read_bytes()!=value:raise ValueError('Immutable artifact collision')
    for name,value in content.items():atomic_bytes(dest/name,value)
    write_json(dest/'manifest.json',dict(stage_id=ident,identity=identity,outputs={name:file_hash(dest/name) for name in content}))
    write_json(ROOT/'outputs/logs/strength_stage6/current.json',dict(directory=dest.relative_to(ROOT).as_posix(),manifest_sha256=file_hash(dest/'manifest.json')))
    print('STAGE6_PREPARATION_COMPLETE',dest.relative_to(ROOT).as_posix(),flush=True)
    return dest
