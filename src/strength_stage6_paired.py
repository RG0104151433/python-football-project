"""Complete paired changes after estimation-row restrictions; no intervals."""
from pathlib import Path
from collections import defaultdict
import csv,gzip,io,json,zipfile
import numpy as np
from scipy.special import ndtr,log_ndtr
from src.data_contract import file_hash,fingerprint,csv_bytes,atomic_bytes,write_json
from src.strength.io import ROOT,environment
from src.strength_joint.contract import load
from src.strength_joint.design import Design
from src.strength_joint.model import fit,Kernel
from src.strength_stage6_sensitivity import read,EstimableDesign,materialize


def full_coefficients(result,names):
    if result['slope_names']:raise ValueError('M0 only')
    lookup=dict(zip(result['names'],result['theta']))
    if set(lookup)-set(names):raise ValueError('Unknown design column')
    return np.array([lookup.get(n,0.) for n in names])


def contexts(prep,sens,rows):
    members=defaultdict(list);new=defaultdict(list);pieces=defaultdict(list)
    for r in read(prep/'reference_membership.csv.gz'):members[r['reference_id']].append(r['match_id'])
    for r in read(sens/'new_estimable_reference_members.csv.gz'):new[r['reference_id']].append(r['match_id'])
    for r in read(prep/'scenario_mixtures.csv'):pieces[r['target_id'],r['reference_kind'],r['arm']].append(r)
    groups=defaultdict(list)
    for r in read(sens/'contrasts.csv'):
        if r['model_id']!='M3_nested':continue
        ids=members[r['baseline_reference_id']] if r['original_reference_all_scenarios_estimable']=='true' else new[r['comparison_reference_id']]
        groups[r['target_id'],r['reference_kind'],tuple(ids)].append(r)
    return members,pieces,groups


def run():
    cfgpath='config/strength_stage6_paired.json';cfg=json.loads((ROOT/cfgpath).read_text());sens=ROOT/cfg['sensitivity']
    if file_hash(sens/'manifest.json')!=cfg['sensitivity_manifest_sha256']:raise ValueError('Sensitivity version changed')
    sm=json.loads((sens/'manifest.json').read_text());prep=ROOT/sm['identity']['protocol']['preparation'];pm=json.loads((prep/'manifest.json').read_text());analysis=ROOT/pm['identity']['protocol']['analysis']
    jc,rows,_,_,inputs=load();base=Design(rows);index={r['match_id']:r for r in rows};old=json.loads((analysis/'models.json').read_text())['M0_nested']
    flags={r['match_id']:r for r in read(prep/'baseline_flags.csv.gz')};models={};metrics=[];predictions=[]
    source_m3=json.loads((sens/'models.json').read_text())
    for label in sm['identity']['protocol']['subset_variants']:
        original_ids={r['match_id'] for r in read(sens/'fit_predictions.csv.gz') if r['fit_id']==label+':M3_nested'}
        training=[r for r in rows if r['match_id'] in original_ids];design=EstimableDesign(base,training,'M0_nested');result=fit(training,design,'M0_nested',jc['numerics'])
        result['restricted_design']=design.specification();models[label]=result
        x,names=design.matrix(training,'M0_nested');p=ndtr(x@np.array(result['theta']))
        predictions.extend(dict(variant_id=label,match_id=r['match_id'],probability=float(v)) for r,v in zip(training,p))
        metrics.append(dict(variant_id=label,estimation_rows=len(training),log_loss=result['loss'],gradient=result['gradient'],curvature_min=result['curvature_min'],numerical_fit_passed=True))
        print('PAIRED_M0_FIT',label,len(training),flush=True)
    members,pieces,groups=contexts(prep,sens,rows);output=[];armrates=[]
    names=base.matrix(rows[:1],'M0_nested')[1]
    for n,((tid,kind,valid),rr) in enumerate(groups.items()):
        labels=list(dict.fromkeys(r['fit_id'].split(':')[0] for r in rr));keys=['baseline']+[k for k in labels if k in models]
        coeff=np.column_stack([full_coefficients(old if k=='baseline' else models[k],names) for k in keys]);values=[]
        parent=members[rr[0]['baseline_reference_id']]
        for arm in ('1','2'):
            total=np.zeros(len(keys));scenario=materialize(pieces[tid,kind,arm],parent,index,valid)
            for weight,rs in scenario:
                x,_=base.matrix(rs,'M0_nested')
                for key in keys[1:]:
                    null=np.array(models[key]['restricted_design']['null_space'])
                    if null.size and not np.all(np.max(abs(x@null),axis=1)<=1e-8*(1+np.linalg.norm(x,axis=1))):raise ValueError('M0 scenario not estimable')
                total+=weight*ndtr(x@coeff).mean(axis=0)
            values.append(total)
            for k,v in zip(keys,total):armrates.append(dict(target_id=tid,reference_kind=kind,population_fingerprint=fingerprint(valid),arm=arm,variant_id=k,probability=float(v)))
        deltas=dict(zip(keys,100*(values[0]-values[1])));base0=float(deltas['baseline'])
        for r in rr:
            label=r['fit_id'].split(':')[0];new0=float(deltas.get(label,base0));new3=float(r['common_reference_new_estimate_pp']);base3=float(r['common_reference_baseline_estimate_pp'])
            paired=new3-new0;previous=base3-base0
            output.append(dict(fit_id=r['fit_id'],target_id=tid,reference_kind=kind,comparison_reference_id=r['comparison_reference_id'],
                baseline_reference_id=r['baseline_reference_id'],original_reference_all_scenarios_estimable=r['original_reference_all_scenarios_estimable']=='true',
                reference_rows=len(valid),M3_variant_delta_pp=new3,M0_variant_delta_pp=new0,paired_variant_change_pp=paired,
                M3_baseline_delta_same_reference_pp=base3,M0_baseline_delta_same_reference_pp=base0,paired_baseline_change_pp=previous,
                sensitivity_of_paired_change_pp=paired-previous,original_paired_variant_pp=paired if r['original_reference_all_scenarios_estimable']=='true' else None,
                reference_change=r['reference_change'],M0_refitted=label in models,inference_status='NOT_ADMITTED'))
        if n%16==0:print('PAIRED_REFERENCE_GROUP',n,tid,flush=True)
    if len(output)!=576:raise ValueError('Paired target count changed')
    files=[ROOT/cfgpath,ROOT/'src/strength_stage6_paired.py',ROOT/'scripts/analyze_strength_stage6_paired.py',ROOT/'src/strength_stage6_sensitivity.py',*ROOT.glob('src/strength_joint/*.py')]
    inputs.update({cfgpath:file_hash(ROOT/cfgpath),cfg['sensitivity']+'/manifest.json':file_hash(sens/'manifest.json')})
    identity=dict(protocol=cfg,inputs=inputs,code={p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(files)},environment=environment());ident='stage6-paired-'+fingerprint(identity)[:20];dest=ROOT/'outputs/tables/strength_joint'/ident
    content={}
    for name,rr in {'fit_metrics.csv':metrics,'paired_changes.csv':output,'arm_rates.csv':armrates,'fit_predictions.csv.gz':predictions}.items():
        b=csv_bytes(list(rr[0]),rr);content[name]=gzip.compress(b,mtime=0) if name.endswith('.gz') else b
    for name,obj in {'models.json':models,'report.json':dict(additional_models=5,paired_targets=576,original_target_blanks=sum(r['original_paired_variant_pp'] is None for r in output),formal_inference=False,baseline_replaced=False,actual_human_review=False)}.items():content[name]=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    content['data_dictionary.md']=('''# 配对敏感性补齐\n五范围变体重拟合M0；四评分变体M0原样复用，因为其估计人口和背景变量不变。每个M3变体与同估计行M0在同一可估参考计算；paired_variant_change=M3-M0，sensitivity_of_paired_change为这一有符号变化相对同参考基准的变化。原目标不可估仍留空，新参考沿用13拟合包身份，不重新筛选。576记录不是576个检验。无区间/显著性/预测声明。arm_rates为普通probit逐行概率平均，不是先平均解释变量再变换。\n''').encode()
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
        for name in identity['code']:z.writestr(zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)),(ROOT/name).read_bytes())
    content['source_snapshot.zip']=buf.getvalue()
    for name,b in content.items():
        if (dest/name).exists() and (dest/name).read_bytes()!=b:raise ValueError('Immutable paired collision')
        atomic_bytes(dest/name,b)
    write_json(dest/'manifest.json',dict(stage_id=ident,identity=identity,outputs={name:file_hash(dest/name) for name in content}))
    write_json(ROOT/'outputs/logs/strength_stage6/paired_pointer.json',dict(directory=dest.relative_to(ROOT).as_posix(),manifest_sha256=file_hash(dest/'manifest.json')))
    print('PAIRED_COMPLETE',dest.relative_to(ROOT).as_posix(),flush=True)


def audit():
    log=ROOT/'outputs/logs/strength_stage6';dest=ROOT/json.loads((log/'paired_pointer.json').read_text())['directory'];manifest=json.loads((dest/'manifest.json').read_text());cfg=manifest['identity']['protocol'];sens=ROOT/cfg['sensitivity']
    sm=json.loads((sens/'manifest.json').read_text());prep=ROOT/sm['identity']['protocol']['preparation'];pm=json.loads((prep/'manifest.json').read_text());analysis=ROOT/pm['identity']['protocol']['analysis']
    _,rows,_,_,_=load();base=Design(rows);index={r['match_id']:r for r in rows};old=json.loads((analysis/'models.json').read_text())['M0_nested'];models=json.loads((dest/'models.json').read_text());checks=0;failed=[]
    def check(name,ok):
        nonlocal checks
        checks+=1
        if not ok:failed.append(name)
    for name,digest in manifest['outputs'].items():check('output:'+name,file_hash(dest/name)==digest)
    for group in ('code','inputs'):
        for name,digest in manifest['identity'][group].items():check(group+':'+name,file_hash(ROOT/name)==digest)
    source_predictions=defaultdict(set)
    for r in read(sens/'fit_predictions.csv.gz'):source_predictions[r['fit_id']].add(r['match_id'])
    saved=defaultdict(list)
    for r in read(dest/'fit_predictions.csv.gz'):saved[r['variant_id']].append(r)
    for label,result in models.items():
        rr=saved[label];check('exact_estimation_ids:'+label,{r['match_id'] for r in rr}==source_predictions[label+':M3_nested'])
        rs=[index[r['match_id']] for r in rr];x,names=base.matrix(rs,'M0_nested');eta=x@full_coefficients(result,names)
        # Independent full-mixture kernel at b=0 must reduce to ordinary probit.
        prob=Kernel(rs).evaluate(eta,np.zeros(len(rs)));y=np.array([int(r['home_win']) for r in rs]);loss=-np.mean(np.where(y,np.log(prob),np.log1p(-prob)))
        check('independent_loss:'+label,abs(loss-result['loss'])<2e-8)
        for r,p in zip(rr,prob):check('probit_identity:'+label+':'+r['match_id'],abs(float(r['probability'])-p)<2e-8)
        check('numeric_fit:'+label,result['numerical_fit_passed'] and result['curvature_min']>0 and not result['boundary_parameters'])
    expected={}
    for r in read(dest/'arm_rates.csv'):expected[r['target_id'],r['reference_kind'],r['population_fingerprint'],r['arm'],r['variant_id']]=float(r['probability'])
    members,pieces,groups=contexts(prep,sens,rows);population_keys={}
    for (tid,kind,valid),rr in groups.items():
        for r in rr:population_keys[r['fit_id'],tid,kind]=fingerprint(valid)
        keys=['baseline']+list(dict.fromkeys(r['fit_id'].split(':')[0] for r in rr if r['fit_id'].split(':')[0] in models));parent=members[rr[0]['baseline_reference_id']]
        for arm in ('1','2'):
            for key in keys:
                result=old if key=='baseline' else models[key];value=0.
                for weight,rs in materialize(pieces[tid,kind,arm],parent,index,valid):
                    x,names=base.matrix(rs,'M0_nested');eta=x@full_coefficients(result,names)
                    # Symmetric complementary probit identity, independent of ndtr branch.
                    probability=-np.expm1(log_ndtr(-eta))
                    value+=weight*float(probability.mean())
                check('scenario_average:'+tid+':'+key,abs(value-expected[tid,kind,fingerprint(valid),arm,key])<2e-8)
    m3={(r['fit_id'],r['target_id'],r['reference_kind']):r for r in read(sens/'contrasts.csv')};pairs=read(dest/'paired_changes.csv');check('576pairs',len(pairs)==576)
    for r in pairs:
        s=m3[r['fit_id'],r['target_id'],r['reference_kind']];v=float(r['M3_variant_delta_pp'])-float(r['M0_variant_delta_pp']);b=float(r['M3_baseline_delta_same_reference_pp'])-float(r['M0_baseline_delta_same_reference_pp'])
        pop=population_keys[r['fit_id'],r['target_id'],r['reference_kind']];label=r['fit_id'].split(':')[0];label=label if label in models else 'baseline'
        def arm_delta(key):return 100*(expected[r['target_id'],r['reference_kind'],pop,'1',key]-expected[r['target_id'],r['reference_kind'],pop,'2',key])
        check('M0_arm_connection',abs(arm_delta(label)-float(r['M0_variant_delta_pp']))<2e-8 and abs(arm_delta('baseline')-float(r['M0_baseline_delta_same_reference_pp']))<2e-8)
        check('paired_arithmetic',abs(v-float(r['paired_variant_change_pp']))<2e-9 and abs(b-float(r['paired_baseline_change_pp']))<2e-9 and abs(v-b-float(r['sensitivity_of_paired_change_pp']))<2e-9)
        check('same_reference',r['comparison_reference_id']==s['comparison_reference_id'] and r['M3_variant_delta_pp']==s['common_reference_new_estimate_pp'])
        check('original_blank_preserved',bool(r['original_paired_variant_pp'])==(r['original_reference_all_scenarios_estimable']=='true'))
    report=dict(passed=not failed,checks=checks,failed=failed,additional_fits=5,paired_rows=576,full_mixture_reduces_to_probit=True,formal_inference_validated=False,human_review=False)
    write_json(log/'paired_audit.json',report);print(json.dumps(report),flush=True)
    if failed:raise SystemExit(1)
