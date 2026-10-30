"""Step3: marginal-distribution and estimation-population sensitivity, no intervals."""
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import csv,gzip,io,json,math,zipfile
import numpy as np
from scipy.linalg import qr,null_space
from src.data_contract import file_hash,fingerprint,csv_bytes,atomic_bytes,write_json
from src.strength.io import ROOT,read_rows,environment
from src.strength_joint.contract import load as load_joint
from src.strength_joint.design import Design,Support
from src.strength_joint.model import fit,predict,Kernel,slopes


def read(path):
    path=Path(path)
    return list(csv.DictReader(io.StringIO(gzip.decompress(path.read_bytes()).decode('utf-8-sig')))) if path.suffix=='.gz' else read_rows(path)


class EstimableDesign:
    """Fixed original coding, outcome-free independent columns and row-space guard."""
    def __init__(self,base,training,model,tolerance=1e-8):
        self.base=base;self.model=model;self.tolerance=tolerance
        x,self.full_names=base.matrix(training,model)
        _,r,pivot=qr(x,mode='economic',pivoting=True)
        singular=np.linalg.svd(x,compute_uv=False);rank=int(np.sum(singular>singular[0]*1e-10))
        self.kept=sorted(int(i) for i in pivot[:rank]);self.null=null_space(x,rcond=1e-10)
        self.dropped=[name for i,name in enumerate(self.full_names) if i not in self.kept]

    def estimable(self,rows):
        x,_=self.base.matrix(rows,self.model)
        if not self.null.shape[1]:return np.ones(len(rows),bool)
        return np.max(abs(x@self.null),axis=1)<=self.tolerance*(1+np.linalg.norm(x,axis=1))

    def matrix(self,rows,model):
        if model!=self.model:raise ValueError('Wrong restricted design model')
        if not self.estimable(rows).all():raise ValueError('NONESTIMABLE_SCENARIO: no implicit category imputation')
        x,names=self.base.matrix(rows,model)
        return x[:,self.kept],[names[i] for i in self.kept]

    def audit(self,rows,model):
        x,names=self.matrix(rows,model);s=np.linalg.svd(x,compute_uv=False);rank=int(np.sum(s>s[0]*1e-10))
        return dict(model_id=model,rows=len(rows),columns=len(names),rank=rank,full_rank=rank==len(names),condition=float(s[0]/s[-1]),names=names)

    def specification(self):
        return dict(full_names=self.full_names,kept_columns=self.kept,dropped_names=self.dropped,null_space=self.null.tolist(),
                    rowspace_tolerance=self.tolerance,interpretation='individual scenario probabilities must be identifiable; sufficient conservative rule for rate differences')


def altered_rows(rows,prepared):
    index={r['match_id']:r for r in prepared}
    if set(index)!={r['match_id'] for r in rows}:raise ValueError('Variant ID mismatch')
    fields=('strength_difference','strength_difference_variance','strength_difference_base_variance','home_jump_intensity','away_jump_intensity','jump_scale_sd',
            'prediction_cutoff','home_history','away_history','cold_start')
    output=[]
    for r in rows:
        row=dict(r)
        for name in fields:row[name]=index[r['match_id']][name]
        for name in ('home_variance','away_variance','home_away_covariance'):row.pop(name,None)
        output.append(row)
    return output


def materialize(pieces,reference_ids,row_index,subset_ids=None):
    """Condition frozen rational mixture on explicitly retained population IDs."""
    valid=set(reference_ids if subset_ids is None else subset_ids);n0=len(reference_ids);n1=len(valid)
    if not n1:return []
    rows=[row_index[mid] for mid in reference_ids if mid in valid];out=[]
    for p in pieces:
        chosen=rows
        if p['target_id'].startswith('Q3:B_'):
            chosen=[r for r in rows if r['home_unit']==p['home_unit_constant']]
        if not chosen:continue
        old_mass=Fraction(int(p['weight_numerator']),int(p['weight_denominator']))
        mass=old_mass*Fraction(len(chosen),int(p['piece_reference_rows']))/Fraction(n1,n0)
        scenario=[]
        for r in chosen:
            changed=dict(r)
            for name in ('era','tournament_group','home_region','home_unit','away_region','away_unit'):
                v=p[name+'_constant']
                if v!='__varies__':changed[name]=v
            scenario.append(changed)
        out.append((float(mass),scenario))
    if abs(sum(w for w,_ in out)-1)>1e-12:raise ValueError('Conditional mixture mass changed')
    return out


def evaluate(result,design,pieces):
    return sum(w*float(predict(result,rs,design).mean()) for w,rs in pieces)


def comparisons(fit_id,result,design,all_rows,training,base_rows,base_design,base_models,base_contrasts,scopes,members,mixtures):
    index={r['match_id']:r for r in all_rows};baseline={r['match_id']:r for r in base_rows};out=[];new_members=[]
    support=Support(training,[-2,-1,0,1,2],20)
    for n,s in enumerate(scopes):
        ids=members[s['reference_id']];arms=[mixtures[s['target_id'],s['reference_kind'],str(i)] for i in (1,2)]
        full=[materialize(a,ids,index) for a in arms];bad=set()
        for arm in full:
            for _,rs in arm:
                good=design.estimable(rs)
                bad.update(r['match_id'] for r,ok in zip(rs,good) if not ok)
        valid=[mid for mid in ids if mid not in bad]
        all_estimable=not bad
        refid=s['reference_id'] if all_estimable else 'estimable-reference-'+fingerprint(dict(parent=s['reference_id'],fit_id=fit_id,ids=valid))[:20]
        row=dict(fit_id=fit_id,model_id=result['model_id'],target_id=s['target_id'],reference_kind=s['reference_kind'],
            baseline_reference_id=s['reference_id'],comparison_reference_id=refid,original_reference_rows=len(ids),common_estimable_reference_rows=len(valid),
            original_reference_all_scenarios_estimable=all_estimable,original_target_new_estimate_pp=None,
            common_reference_new_estimate_pp=None,common_reference_baseline_estimate_pp=None,change_at_common_reference_pp=None,
            original_target_status=s['original_status'],reference_change='none' if all_estimable else 'NEW narrower estimand, not original target',
            population_weights='frozen registered weights; conditionalize only on named common estimable population',
            score_input_scope='variant-specific marginals; baseline membership held fixed',
            support_population='actual joint estimation rows, not full rating-learning history',
            max_unsupported_scenario_mass=None,lower_pp=None,upper_pp=None,inference_status='NOT_ADMITTED')
        if valid:
            aa=[materialize(a,ids,index,valid) for a in arms];bb=[materialize(a,ids,baseline,valid) for a in arms]
            values=[evaluate(result,design,a) for a in aa]
            baseresult=base_models[result['model_id']]
            current=100*(values[0]-values[1])
            if all_estimable:
                base=float(base_contrasts[s['target_id'],s['reference_kind'],result['model_id']]['difference_pp'])
            else:
                original_values=[evaluate(baseresult,base_design,a) for a in bb]
                base=100*(original_values[0]-original_values[1])
            unsupported=[]
            for arm in aa:
                value=0.
                for w,rs in arm:
                    zero,_,outside=support.flags(rs);value+=w*float(np.mean(zero|outside))
                unsupported.append(value)
            row.update(original_target_new_estimate_pp=current if all_estimable else None,
                common_reference_new_estimate_pp=current,common_reference_baseline_estimate_pp=base,
                change_at_common_reference_pp=current-base,max_unsupported_scenario_mass=max(unsupported))
            if not all_estimable:
                new_members.extend(dict(fit_id=fit_id,reference_id=refid,parent_reference_id=s['reference_id'],match_id=mid,weight_numerator=1,weight_denominator=len(valid)) for mid in valid)
        out.append(row)
        if n%16==0:print('SENSITIVITY_CONTRAST',fit_id,n,s['target_id'],flush=True)
    return out,new_members


def relation_points(result,design,rows,means):
    output=[]
    for d in means:
        ps=[]
        for t in ('friendly','non_friendly'):
            scenario=[dict(r,tournament_group=t,strength_difference=float(d)) for r in rows]
            if not design.estimable(scenario).all():raise ValueError('Curve scenario outside parameter support')
            ps.append(float(predict(result,scenario,design).mean()))
        output.append(dict(strength_mean=d,friendly_probability=ps[0],other_probability=ps[1],difference_pp=100*(ps[0]-ps[1]),
                           inference_status='NOT_ADMITTED',role='model scenario, not empirical stratified win rate'))
    return output


def run(config_path='config/strength_stage6_sensitivity.json'):
    cfg=json.loads((ROOT/config_path).read_text());prep=ROOT/cfg['preparation']
    if file_hash(prep/'manifest.json')!=cfg['preparation_manifest_sha256']:raise ValueError('Preparation version mismatch')
    pm=json.loads((prep/'manifest.json').read_text())
    for name,h in pm['outputs'].items():
        if file_hash(prep/name)!=h:raise ValueError('Preparation output changed')
    joint_cfg,base_rows,_,_,inputs=load_joint();analysis=ROOT/pm['identity']['protocol']['analysis']
    base_models=json.loads((analysis/'models.json').read_text());base_design=Design(base_rows)
    readiness=json.loads((prep/'readiness.json').read_text());scorefiles={r['variant_id']:r['prepared_file'] for r in readiness['score_variants']}
    base_input=altered_rows(base_rows,read(prep/scorefiles['baseline']))
    p0=predict(base_models['M3_nested'],base_input,base_design)
    published=read(analysis/'joint_predictions.csv');error=float(max(abs(p0-np.array([float(r['M3_nested']) for r in published]))))
    if error>cfg['baseline_probability_gate']:raise ValueError('Prepared baseline interface not reproduced')
    members=defaultdict(list)
    for r in read(prep/'reference_membership.csv.gz'):members[r['reference_id']].append(r['match_id'])
    mixtures=defaultdict(list)
    for r in read(prep/'scenario_mixtures.csv'):mixtures[r['target_id'],r['reference_kind'],r['arm']].append(r)
    scopes=read(prep/'reference_scope.csv');flag={r['match_id']:r for r in read(prep/'baseline_flags.csv.gz')}
    base_contrasts={(r['target_id'],r['reference_kind'],r['model_id']):r for r in read(analysis/'contrasts.csv')}
    specifications=[]
    for label in cfg['score_variants']:
        rs=altered_rows(base_rows,read(prep/scorefiles[label]))
        for model in cfg['score_models']:specifications.append((label,model,rs,rs,'changed score marginals + joint refit; same estimation IDs'))
    for label in cfg['subset_variants']:
        def remove(r):
            f=flag[r['match_id']]
            if label=='exclude_cold_start':return f['cold_start']=='true'
            if label=='exclude_previously_disconnected':return f['weak_connection']=='true'
            if label=='exclude_unknown_geography':return f['unknown_home']=='true' or f['unknown_away']=='true'
            if label=='exclude_initialization_mean_sensitive':return f['initialization_mean_sensitive']=='true'
            return any(f[k]=='true' for k in ('cold_start','weak_connection','unknown_home','unknown_away'))
        training=[r for r in base_input if not remove(r)]
        for model in cfg['subset_models']:specifications.append((label,model,base_input,training,'joint estimation rows only; rating histories unchanged'))
    models={};metrics=[];contrast=[];predictions=[];slopes_rows=[];relations=[];new_members=[]
    for label,model,allrows,training,scope in specifications:
        fit_id=label+':'+model;print('SENSITIVITY_FIT',fit_id,len(training),flush=True)
        design=EstimableDesign(base_design,training,model,cfg['rowspace_tolerance'])
        result=fit(training,design,model,joint_cfg['numerics']);result['restricted_design']=design.specification()
        result['variant_id']=label;result['scope']=scope;models[fit_id]=result
        probability=predict(result,training,design)
        metrics.append(dict(fit_id=fit_id,variant_id=label,model_id=model,estimation_rows=len(training),excluded_estimation_rows=24917-len(training),
            log_loss=result['loss'],gradient=result['gradient'],multistart_loss_spread=result['multistart_loss_spread'],
            removed_parameter_names=';'.join(design.dropped),numerical_fit_passed=result['numerical_fit_passed'],
            scope=scope,confidence_interval_admitted=False))
        predictions.extend(dict(fit_id=fit_id,match_id=r['match_id'],home_win=int(r['home_win']),fitted_home_probability=float(p),role='retrospective fit') for r,p in zip(training,probability))
        c,mm=comparisons(fit_id,result,design,allrows,training,base_input,base_design,base_models,base_contrasts,scopes,members,mixtures)
        contrast.extend(c);new_members.extend(mm)
        parameters=dict(zip(result['names']+result['slope_names'],result['theta']))
        slopes_rows.append(dict(fit_id=fit_id,model_id=model,slope_other=math.exp(parameters.get('log_b_nonfriendly',parameters.get('log_b',0))),
            slope_friendly=math.exp(parameters['log_b_friendly']) if 'log_b_friendly' in parameters else None,
            log_slope_difference=parameters['log_b_friendly']-parameters['log_b_nonfriendly'] if 'log_b_friendly' in parameters else None,
            formal_test_performed=False))
        if model=='M4_type_slope':
            relations.extend(dict(fit_id=fit_id,**r) for r in relation_points(result,design,allrows,cfg['relation_mean_points']))
    previous=read(analysis/'sensitivity.csv');comparison=[]
    for r in contrast:
        if r['model_id']!='M3_nested' or r['reference_kind']!='full' or not r['fit_id'].startswith('repaired-initialization'):continue
        label=r['fit_id'].split(':')[0]
        old=next(x for x in previous if x['variant']==label and x['target_id']==r['target_id'])
        comparison.append(dict(fit_id=r['fit_id'],target_id=r['target_id'],old_mean_only_estimate_pp=float(old['variant_difference_pp']),
            full_marginal_estimate_pp=r['original_target_new_estimate_pp'],difference_from_mean_only_pp=r['original_target_new_estimate_pp']-float(old['variant_difference_pp']),
            meaning='variance/jump distribution plus refit, not a confidence interval'))
    csvs={'fit_metrics.csv':metrics,'contrasts.csv':contrast,'fit_predictions.csv.gz':predictions,'strength_slopes.csv':slopes_rows,
          'relation_points.csv':relations,'mean_only_vs_full.csv':comparison}
    if new_members:
        unique={(r['fit_id'],r['reference_id'],r['match_id']):r for r in new_members}
        csvs['new_estimable_reference_members.csv.gz']=list(unique.values())
    files=[ROOT/'src/strength_stage6_sensitivity.py',ROOT/'scripts/analyze_strength_stage6_sensitivity.py',ROOT/'scripts/audit_strength_stage6_sensitivity.py',
        ROOT/'tests/test_strength_stage6_sensitivity.py',ROOT/config_path,ROOT/'src/data_contract.py',ROOT/'src/strength/io.py',*ROOT.glob('src/strength_joint/*.py')]
    inputs.update({config_path:file_hash(ROOT/config_path),cfg['preparation']+'/manifest.json':file_hash(prep/'manifest.json')})
    identity=dict(protocol=cfg,inputs=inputs,code={p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(files)},environment=environment())
    ident='stage6-sensitivity-'+fingerprint(identity)[:20];dest=ROOT/'outputs/tables/strength_joint'/ident;content={}
    for name,rr in csvs.items():
        b=csv_bytes(list(rr[0]),rr);content[name]=gzip.compress(b,mtime=0) if name.endswith('.gz') else b
    report=dict(step3_analysis_completed=True,models=len(models),contrast_rows=len(contrast),baseline_probability_interface_max_error=error,
        preparation=cfg['preparation'],marginal_score_variants=len(cfg['score_variants']),subset_variants=len(cfg['subset_variants']),
        original_scope_scenarios_not_estimable=sum(not r['original_reference_all_scenarios_estimable'] for r in contrast),
        stage6_complete=False,intervals_computed=False,formal_inference_selected=False,score_replay_performed=False,
        scope='predeclared marginal and estimation-row sensitivities, not exhaustive model misspecification or full posterior propagation',actual_human_review=False)
    for name,obj in {'models.json':models,'report.json':report}.items():content[name]=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')
    content['data_dictionary.md']=('''# 第六环节第三步评分/估计样本敏感性\n\n四评分变体×M3/M4，五范围变体×M3。只重拟合共同模型，评分来自已验证边际准备表；不重写学习历史，不做区间或显著性。\ncontrasts保持原参考成员/原有理混合，未重筛评分重叠。若剔除估计行使某类参数不可估，原目标估计留空；另给共同可估参考新ID，在同一新参考计算基准和变体差。逐情景概率的列空间可估是保守充分准则，不声称穷尽率差函数的识别性。\n评分变体保留相同人口权重但改变评分协变量与重新拟合系数，两者合并诊断，不作因果分解。范围剔除不重评分，不把诊断标记判为无效数据。此前连接标记只是历史图不连通，尚非连续连接强度。\nfit_predictions为回顾性拟合概率，只含实际估计行；不能当独立未来预测。mean_only_vs_full只比较已保存的均值替换与本次完整边际，不是范围。所有区间空NOT_ADMITTED；跨场协方差/误差传播与统计方法选型仍未完成。\n''').encode('utf-8')
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
        for name in sorted(identity['code']):z.writestr(zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)),(ROOT/name).read_bytes())
    content['source_snapshot.zip']=buf.getvalue()
    for name,b in content.items():
        if (dest/name).exists() and (dest/name).read_bytes()!=b:raise ValueError('Immutable sensitivity collision')
    for name,b in content.items():atomic_bytes(dest/name,b)
    write_json(dest/'manifest.json',dict(stage_id=ident,identity=identity,outputs={name:file_hash(dest/name) for name in content}))
    write_json(ROOT/'outputs/logs/strength_stage6/sensitivity_pointer.json',dict(directory=dest.relative_to(ROOT).as_posix(),manifest_sha256=file_hash(dest/'manifest.json')))
    print('STAGE6_SENSITIVITY_COMPLETE',dest.relative_to(ROOT).as_posix(),flush=True)
    return dest
