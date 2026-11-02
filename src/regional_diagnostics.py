"""Q7 step4: label-free past thresholds and descriptive common-mix comparisons."""
from itertools import product
import io
import json
import math
import zipfile
import numpy as np
from src.data_contract import atomic_bytes,csv_bytes,file_hash,fingerprint,write_json
from src.strength.io import ROOT,read_rows,environment
from src.regional_effectiveness import groups,describe,bin_index,unique

LEVELS=dict(signed_gap=['away_advantage','relatively_close','home_advantage'],
            absolute_gap=['low','middle','high'],uncertainty=['low','middle','high'],
            history=['limited','established'],tournament_group=['friendly','non_friendly'],
            relation=['same_unit','same_region_diff_unit','cross_region','unknown'])
LABELS={'ALL':'全体','150':'欧洲','142':'亚洲','002':'非洲','019':'美洲','009':'大洋洲',
        'UNKNOWN':'地区未知','SOUTH_AMERICA':'南美（补充）','OTHER_AMERICAS':'其余美洲（补充）'}


def thresholds(rows,start,end):
    past=[r for r in rows if start<=r['date']<end]
    if not past:raise ValueError('NO_THRESHOLD_TRAINING_ROWS')
    gap=np.array([abs(float(r['strength_difference'])) for r in past])
    var=np.array([float(r['strength_difference_variance']) for r in past])
    if not np.isfinite(gap).all() or not np.isfinite(var).all() or np.any(var<=0):raise ValueError('INVALID_THRESHOLD_FEATURE')
    return dict(training_rows=len(past),training_min=min(r['date'] for r in past),training_max=max(r['date'] for r in past),
                training_id_sha256=fingerprint(sorted(r['match_id'] for r in past)),
                signed_gap_magnitude=float(np.median(gap)),absolute_gap_cuts=np.quantile(gap,[1/3,2/3],method='linear').tolist(),
                uncertainty_sd_cuts=np.quantile(np.sqrt(var),[1/3,2/3],method='linear').tolist(),
                uses_target_outcomes=False,uses_training_outcomes=False)


def classify(r,cut,history_min):
    d=float(r['strength_difference']);v=float(r['strength_difference_variance'])
    if not math.isfinite(d) or not math.isfinite(v) or v<=0:raise ValueError('INVALID_ROW_FEATURE')
    t=cut['signed_gap_magnitude']
    sg='away_advantage' if d < -t else 'home_advantage' if d > t else 'relatively_close'
    r=dict(r,signed_gap=sg,absolute_gap=LEVELS['absolute_gap'][int(np.searchsorted(cut['absolute_gap_cuts'],abs(d),side='right'))],
           uncertainty=LEVELS['uncertainty'][int(np.searchsorted(cut['uncertainty_sd_cuts'],math.sqrt(v),side='right'))],
           history='limited' if min(int(r['home_history']),int(r['away_history']))<history_min else 'established',
           strength_sd=math.sqrt(v))
    if r['relation'] not in LEVELS['relation'] or r['tournament_group'] not in LEVELS['tournament_group']:
        raise ValueError('UNREGISTERED_FACTOR_VALUE')
    r['joint_cell']=r['signed_gap']+'|'+r['uncertainty']
    return r


def common_weights(by_group,cells):
    counts={g:{c:sum(r['joint_cell']==c for r in rr) for c in cells} for g,rr in by_group.items()}
    common=[c for c in cells if all(counts[g][c]>0 for g in counts)]
    pooled={c:sum(counts[g][c] for g in counts) for c in common}
    n=sum(pooled.values())
    return common,{c:v/n for c,v in pooled.items()} if n else {},counts


def standardized(rows,weights,field,eps):
    if not weights:return dict(status='no_common_support',log_loss=None,brier=None,bias_pp=None,accuracy=None)
    result=dict(status='descriptive_common_mix',log_loss=0.,brier=0.,bias_pp=0.,accuracy=0.)
    for cell,w in weights.items():
        rr=[r for r in rows if r['joint_cell']==cell]
        if not rr:raise ValueError('MISSING_POSITIVE_WEIGHT_CELL')
        m=describe(rr,field,eps)
        for k in ['log_loss','brier','bias_pp','accuracy']:result[k]+=w*m[k]
    return result


def evaluate(rows,cut,cfg):
    rr=[classify(r,cut,cfg['history_minimum']) for r in rows]
    by={g:[r for r in rr if g in groups(r)] for g in LABELS}
    cells=['|'.join(p) for p in product(LEVELS['signed_gap'],LEVELS['uncertainty'])]
    composition=[];metrics=[]
    dims={**LEVELS,'joint_cell':cells}
    for g,ss in by.items():
        for dimension,levels in dims.items():
            for level in levels:
                sub=[r for r in ss if r[dimension]==level]
                composition.append(dict(group=g,label=LABELS[g],dimension=dimension,level=level,matches=len(sub),
                    share=len(sub)/len(ss) if ss else None,sparse=0<len(sub)<cfg['sparse_warning_count'],
                    mean_abs_strength_gap=float(np.mean([abs(float(r['strength_difference'])) for r in sub])) if sub else None,
                    mean_strength_sd=float(np.mean([r['strength_sd'] for r in sub])) if sub else None,
                    home_mean_strength_positive_share=sum(float(r['strength_difference'])>0 for r in sub)/len(sub) if sub else None))
                for model in ['joint','strength']:
                    metrics.append(dict(group=g,label=LABELS[g],dimension=dimension,level=level,model=model,
                                        **describe(sub,'p_'+model,cfg['probability_clip'])))
    standard=[];support=[];weight_rows=[]
    for set_name,set_groups in [('primary5',cfg['standardization']['primary_set']),('americas2',cfg['standardization']['americas_set'])]:
        members={g:by[g] for g in set_groups};common,weights,counts=common_weights(members,cells)
        pooled=[r for g in members for r in members[g]]
        for c in cells:
            weight_rows.append(dict(comparison_set=set_name,joint_cell=c,in_common_support=c in common,
                                    pooled_matches=sum(counts[g][c] for g in counts),weight=weights.get(c,0.)))
        for g in set_groups+['ALL']:
            ss=pooled if g=='ALL' else by[g];keep=[r for r in ss if r['joint_cell'] in weights]
            support.append(dict(comparison_set=set_name,group=g,label=LABELS[g],full_matches=len(ss),
                                retained_matches=len(keep),excluded_matches=len(ss)-len(keep),common_cells=len(common),
                                minimum_nonempty_cell=min([sum(r['joint_cell']==c for r in ss) for c in common],default=0)))
            for model in ['joint','strength']:
                full=describe(ss,'p_'+model,cfg['probability_clip']);raw=describe(keep,'p_'+model,cfg['probability_clip'])
                std=standardized(ss,weights,'p_'+model,cfg['probability_clip'])
                standard.append(dict(comparison_set=set_name,group=g,label=LABELS[g],model=model,
                    full_matches=len(ss),retained_matches=len(keep),common_cells=len(common),
                    full_loss=full['log_loss'],common_subset_raw_loss=raw['log_loss'],
                    standardized_loss=std['log_loss'],full_bias_pp=full['bias_pp'],
                    common_subset_raw_bias_pp=raw['bias_pp'],standardized_bias_pp=std['bias_pp'],
                    standardized_brier=std['brier'],standardized_accuracy=std['accuracy'],status=std['status']))
    africa=[]
    edges=[0,.2,.4,.6,.8,1]
    for dim in ['signed_gap','uncertainty']:
        for lev in LEVELS[dim]:
            for b in range(5):
                sub=[r for r in by['002'] if r[dim]==lev and bin_index(float(r['p_joint']),edges)==b]
                africa.append(dict(dimension=dim,level=lev,probability_bin=b,bin_left=edges[b],bin_right=edges[b+1],
                                   **describe(sub,'p_joint',cfg['probability_clip'])))
    return rr,dict(composition=composition,stratum_metrics=metrics,standardized_metrics=standard,
                   standardization_support=support,reference_weights=weight_rows,africa_calibration=africa)


def plot(folder,tables,font):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    plt.rcParams.update({'font.family':FontProperties(fname=font).get_name(),'axes.unicode_minus':False,'svg.hashsalt':'q7diagnostics-v1'})
    out=[]
    def save(fig,name):
        for ext in ['png','svg']:
            b=io.BytesIO();fig.savefig(b,format=ext,dpi=160,bbox_inches='tight',metadata={'Date':None} if ext=='svg' else {})
            p=folder/(name+'.'+ext);atomic_bytes(p,b.getvalue());out.append(p)
        plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    primary=['150','142','002','019','009']
    for ax,dim,title in zip(axes,['signed_gap','uncertainty'],['双方实力差构成','实力差评估不确定性构成']):
        bottom=np.zeros(5)
        for level,color,name in zip(LEVELS[dim],['#276e87','#99bcc0','#bd794e'],
            ['客队较强','差距相对较近','主队较强'] if dim=='signed_gap' else ['较低','中间','较高']):
            vals=[next(r['share'] for r in tables['composition'] if r['group']==g and r['dimension']==dim and r['level']==level)*100 for g in primary]
            ax.bar([LABELS[g] for g in primary],vals,bottom=bottom,color=color,label=name);bottom+=vals
        ax.set(title=title,ylabel='地区比赛所占比例（%）',ylim=(0,100));ax.legend(fontsize=9)
    fig.suptitle('2010—2024 · 分组切点只用1980—2009特征确定 · 评分不确定性不是已知真实误差',fontsize=11)
    fig.tight_layout();save(fig,'regional_match_composition')
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    data=[next(r for r in tables['standardized_metrics'] if r['comparison_set']=='primary5' and r['group']==g and r['model']=='joint') for g in primary]
    for ax,raw,adj,title,ylabel in zip(axes,['common_subset_raw_loss','common_subset_raw_bias_pp'],['standardized_loss','standardized_bias_pp'],['同一共同支持样本：统一两项构成前后','平均偏差：统一构成后也未必更小'],['主胜/非主胜概率损失','预测减实际（百分点）']):
        ax.plot([LABELS[g] for g in primary],[r[raw] for r in data],'o-',label='各地区原构成',color='#267d91')
        ax.plot([LABELS[g] for g in primary],[r[adj] for r in data],'o-',label='统一实力差与不确定性构成',color='#b66a3d')
        ax.set(title=title,ylabel=ylabel);ax.legend(fontsize=8);ax.grid(alpha=.2)
    axes[1].axhline(0,color='gray',ls='--',lw=1)
    fig.suptitle('九格共同参考 · 描述性比较，无置信区间/因果分解 · 稀疏格需第五步检查',fontsize=11)
    fig.tight_layout();save(fig,'regional_common_mix');return out


def run(config_path='config/regional_effectiveness_diagnostics.json'):
    cfg=json.loads((ROOT/config_path).read_text(encoding='utf-8-sig'))
    if cfg['schema_version']!='regional-diagnostics-v1' or cfg['main_years']!=[2010,2024]:raise ValueError('DIAGNOSTIC_PROTOCOL_CHANGED')
    src=ROOT/'outputs/logs/regional_effectiveness'/cfg['source_run'];man=json.loads((src/'manifest.json').read_text(encoding='utf-8-sig'))
    inputs={config_path:file_hash(ROOT/config_path),(src/'manifest.json').relative_to(ROOT).as_posix():file_hash(src/'manifest.json')}
    def take(path,expected):
        if file_hash(ROOT/path)!=expected:raise ValueError('INPUT_CHANGED:'+path)
        inputs[path]=expected
    path=f"outputs/tables/regional_effectiveness/{cfg['source_run']}/evaluation_matches.csv";take(path,man['outputs'][path])
    study=json.loads((ROOT/'config/strength_joint.json').read_text(encoding='utf-8-sig'))
    take('config/strength_joint.json',man['identity']['inputs']['config/strength_joint.json'])
    facts_path=study['input']+'/analysis_matches.csv';take(facts_path,man['identity']['inputs'][facts_path])
    for p in ['src/regional_effectiveness.py','src/history_window/protocol.py']:
        if file_hash(ROOT/p)!=man['identity']['code'][p]:raise ValueError('SOURCE_METRIC_CODE_CHANGED:'+p)
    import matplotlib
    font=man['identity']['plotting']['font_path']
    from pathlib import Path
    if file_hash(Path(font))!=man['identity']['plotting']['font_sha256']:raise ValueError('FONT_CHANGED')
    code=[ROOT/'src/regional_diagnostics.py',ROOT/'src/regional_effectiveness.py',ROOT/'scripts/analyze_regional_diagnostics.py',
          ROOT/'tests/test_regional_diagnostics.py',ROOT/'src/data_contract.py',ROOT/'src/strength/io.py',ROOT/'src/history_window/protocol.py']
    identity=dict(protocol=cfg,inputs=inputs,code={p.relative_to(ROOT).as_posix():file_hash(p) for p in code},
                  plotting=dict(font_path=font,font_sha256=file_hash(Path(font)),matplotlib=matplotlib.__version__),environment=environment())
    rid='regional-diagnostics-'+fingerprint(identity)[:20];log=ROOT/'outputs/logs/regional_effectiveness'/rid
    table=ROOT/'outputs/tables/regional_effectiveness'/rid;fig=ROOT/'outputs/figures/regional_effectiveness'/rid
    if (log/'manifest.json').exists():
        for p,h in json.loads((log/'manifest.json').read_text(encoding='utf-8-sig'))['outputs'].items():
            if file_hash(ROOT/p)!=h:raise ValueError('OUTPUT_CHANGED:'+p)
        print('DIAGNOSTICS_VERIFIED',rid);return log,table
    for p in (log,table,fig):p.mkdir(parents=True,exist_ok=True)
    write_json(log/'started.json',dict(identity=identity,steps_completed_by_run=[4]));write_json(log/'protocol.json',cfg)
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
        for p in code+[ROOT/config_path]:z.writestr(zipfile.ZipInfo(p.relative_to(ROOT).as_posix(),(1980,1,1,0,0,0)),p.read_bytes())
    atomic_bytes(log/'source_snapshot.zip',archive.getvalue())
    try:
        allrows=read_rows(ROOT/path);unique(allrows,'source')
        rows=[r for r in allrows if 2010<=int(r['year'])<=2024]
        if len(rows)!=9727:raise ValueError('MAIN_COHORT_CHANGED')
        cut=thresholds(read_rows(ROOT/facts_path),cfg['threshold_training_start'],cfg['threshold_training_end_exclusive'])
        write_json(log/'thresholds.json',cut)
        classified,tables=evaluate(rows,cut,cfg)
        cols=['match_id','date','home_region','home_unit','signed_gap','absolute_gap','uncertainty','history','joint_cell','strength_sd']
        atomic_bytes(table/'strata_membership.csv',csv_bytes(cols,classified))
        for name,rr in tables.items():atomic_bytes(table/(name+'.csv'),csv_bytes(list(rr[0]),rr))
        figure_paths=plot(fig,tables,font)
        write_json(table/'display_data.json',dict(run_id=rid,source_run=cfg['source_run'],thresholds=cut,
            standardized_metrics=tables['standardized_metrics'],reference_weights=tables['reference_weights'],
            support=tables['standardization_support'],composition=tables['composition'],
            figures=[p.relative_to(ROOT).as_posix() for p in figure_paths],formal_inference=False,
            interpretation='coarse conditional composition diagnostics, not causal attribution; no model changes or proof of low-information causation'))
        review=dict(passed=True,step4_complete=True,step5_complete=False,main_matches=len(rows),training_rows=cut['training_rows'],
                    table_rows={k:len(v) for k,v in tables.items()},new_fits=0,new_ratings=0,new_simulations=0,human_review=False,
                    formal_inference=False,scope='source and membership checks; independent arithmetic audit to be attached separately')
        write_json(log/'review.json',review)
        outputs={p.relative_to(ROOT).as_posix():file_hash(p) for d in [log,table,fig] for p in d.iterdir() if p.is_file() and p.name not in ['manifest.json','failure.json']}
        write_json(log/'manifest.json',dict(identity=identity,outputs=outputs))
        write_json(log/'adoption.json',dict(run_id=rid,manifest_sha256=file_hash(log/'manifest.json'),step4_complete=True,step5_complete=False,human_review=False))
        write_json(ROOT/'outputs/logs/regional_effectiveness/diagnostics_pointer.json',dict(run_id=rid,source_run=cfg['source_run'],
            log_directory=log.relative_to(ROOT).as_posix(),table_directory=table.relative_to(ROOT).as_posix(),figure_directory=fig.relative_to(ROOT).as_posix(),steps_completed=[1,2,3,4],formal_inference=False))
        print('DIAGNOSTICS_COMPLETE',rid,review,flush=True);return log,table
    except Exception as exc:
        write_json(log/'failure.json',dict(type=type(exc).__name__,message=str(exc)));raise
