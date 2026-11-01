"""Q7 stages1-3: reuse issued forecasts, preserve uncertainty, describe regions."""
from collections import Counter
from datetime import date
import io
import json
import math
import zipfile
import numpy as np
from src.data_contract import atomic_bytes, csv_bytes, file_hash, fingerprint, write_json
from src.strength.io import ROOT, environment, read_rows
from src.history_window.protocol import log_losses


def unique(rows, name):
    by = {r['match_id']:r for r in rows}
    if len(by) != len(rows): raise ValueError('DUPLICATE_ID:'+name)
    return by


def match_facts(a, b):
    if any(str(a[k]) != str(b[k]) for k in ('match_id','date','home_win','home_region','tournament_group')):
        raise ValueError('PAIRED_FACTS_DIFFER')


def validate_forecast(r):
    if str(r['home_win']) not in ('0','1') or not math.isfinite(float(r['probability'])) or not 0 <= float(r['probability']) <= 1:
        raise ValueError('INVALID_FORECAST')
    if date.fromisoformat(r['date']).isoformat() != r['date']: raise ValueError('INVALID_DATE')


def groups(r):
    region = r['home_region'] or 'UNKNOWN'
    out = ['ALL', region]
    if region == '019': out += ['SOUTH_AMERICA' if r['home_unit']=='005' else 'OTHER_AMERICAS']
    return out


def bin_index(p, edges):
    if not math.isfinite(p) or not 0 <= p <= 1: raise ValueError('INVALID_PROBABILITY')
    return min(int(np.searchsorted(edges, p, side='right'))-1, len(edges)-2)


def describe(rows, field, eps):
    if not rows:
        return dict(matches=0, log_loss=None, brier=None, accuracy=None, mean_probability=None,
                    observed_home_win_rate=None, bias_pp=None, clips=0, status='empty')
    p=np.array([float(r[field]) for r in rows]);y=np.array([int(r['home_win']) for r in rows])
    return dict(matches=len(rows),log_loss=float(log_losses(p,y,eps).mean()),
                brier=float(np.mean((p-y)**2)),accuracy=float(np.mean((p>=.5)==y)),
                mean_probability=float(p.mean()),observed_home_win_rate=float(y.mean()),
                bias_pp=100*float(np.mean(p-y)),clips=int(np.sum((p<eps)|(p>1-eps))),status='descriptive')


def past_frequencies(facts, years, start):
    result={}
    for year in years:
        past=[r for r in facts if start<=r['date']<f'{year}-01-01']
        if not past: raise ValueError('NO_PAST_FREQUENCY')
        result[year]=dict(probability=sum(int(r['home_win']) for r in past)/len(past),
                          rows=len(past),max_date=max(r['date'] for r in past))
    return result


def source_bundle(cfg, config_path):
    inputs={config_path:file_hash(ROOT/config_path)}
    olog=f"outputs/logs/history_window/{cfg['outcome_run']}"
    otab=f"outputs/tables/history_window/{cfg['outcome_run']}"
    stab=f"outputs/tables/strength_joint/{cfg['strength_prediction_run']}"
    manifests={}
    for key,path in [('outcome',olog+'/manifest.json'),('strength',stab+'/manifest.json')]:
        manifests[key]=json.loads((ROOT/path).read_text(encoding='utf-8-sig'));inputs[path]=file_hash(ROOT/path)
    def take(key,path):
        expected=manifests[key]['outputs'][path if key=='outcome' else path.split('/')[-1]]
        if file_hash(ROOT/path)!=expected: raise ValueError('SOURCE_CHANGED:'+path)
        inputs[path]=expected
        return path
    paths={k:take(parent,path) for k,parent,path in [
        ('outcome','outcome',otab+'/predictions.csv'),('outcome_models','outcome',olog+'/models.json'),
        ('strength','strength',stab+'/predictions.csv'),('strength_models','strength',stab+'/models.json')]}
    old,new=manifests['strength']['identity'],manifests['outcome']['identity']
    for p in old['inputs']:
        if p not in new['inputs'] or old['inputs'][p]!=new['inputs'][p]:raise ValueError('INCOMPATIBLE_STUDY_INPUT:'+p)
        if file_hash(ROOT/p)!=old['inputs'][p]:raise ValueError('CURRENT_INPUT_CHANGED:'+p)
        inputs[p]=old['inputs'][p]
    for p in ['src/strength_predictive_validation.py','src/strength_joint/model.py','src/strength_joint/design.py']:
        if old['code'][p]!=new['code'][p]:raise ValueError('INCOMPATIBLE_MODEL_MATH:'+p)
    if (old['protocol']['training_start']!=1980 or old['protocol']['ridge_precision']!=1 or
        new['protocol']['outcome_start']!=cfg['training_start'] or new['protocol']['ridge_precision']!=1):
        raise ValueError('INCOMPATIBLE_TRAINING_PROTOCOL')
    study=json.loads((ROOT/cfg['joint_config']).read_text(encoding='utf-8-sig'))
    mpath=study['input']+'/manifest.json';manifest=json.loads((ROOT/mpath).read_text(encoding='utf-8-sig'))
    if file_hash(ROOT/mpath)!=study['input_manifest_sha256']:raise ValueError('STUDY_MANIFEST_CHANGED')
    path=study['input']+'/analysis_matches.csv'
    if file_hash(ROOT/path)!=manifest['outputs']['analysis_matches.csv']:raise ValueError('STUDY_ROWS_CHANGED')
    paths['facts']=path;inputs[path]=file_hash(ROOT/path)
    return paths,inputs


def prepare(cfg, paths):
    facts=read_rows(ROOT/paths['facts']);factby=unique(facts,'facts')
    o=[r for r in read_rows(ROOT/paths['outcome']) if r['window']=='cumulative']
    s=read_rows(ROOT/paths['strength']);m1=unique([r for r in s if r['model_id']=='M1_strength'],'M1')
    m3=unique([r for r in s if r['model_id']=='M3_nested'],'M3')
    om=json.loads((ROOT/paths['outcome_models']).read_text(encoding='utf-8-sig'))
    sm=json.loads((ROOT/paths['strength_models']).read_text(encoding='utf-8-sig'))
    unique(o,'joint');years=range(2000,2025);pf=past_frequencies(facts,years,cfg['training_start'])
    compat=[]
    for year in years:
        a,b,c=om[f'{year}:cumulative'],sm[f'{year}:M1_strength'],sm[f'{year}:M3_nested']
        train=[r for r in facts if cfg['training_start']<=r['date']<f'{year}-01-01']
        digest=fingerprint(sorted(r['match_id'] for r in train));maximum=max(r['date'] for r in train)
        if (any(int(x['rows'])!=len(train) or x['past_date_max']!=maximum or x['ridge_precision']!=1 or
                x['mode']!='mixture' or not x['numerical_fit_passed'] for x in (a,b,c)) or
            a['training_id_set_sha256']!=digest or b['names']!=['intercept']):
            raise ValueError('ANNUAL_MODEL_INCOMPATIBLE:'+str(year))
        compat.append(dict(year=year,training_rows=len(train),training_max=maximum,
                           training_id_sha256=digest,M1_reused=True,M3_bridge_verified=True))
    output=[];max_error=0.
    fields=['match_id','date','year','era','tournament_group','home_team_id','away_team_id','home_team','away_team',
            'home_region','away_region','home_unit','away_unit','relation','home_win','strength_difference',
            'strength_difference_variance','strength_difference_base_variance','home_variance','away_variance',
            'home_away_covariance','home_jump_intensity','away_jump_intensity','jump_scale_sd','home_history',
            'away_history','cold_start','previously_disconnected','prediction_cutoff','rating_run_id','rating_rules_version']
    for r in sorted(o,key=lambda r:(r['date'],r['match_id'])):
        f=factby[r['match_id']];b=m1[r['match_id']];bridge=m3[r['match_id']]
        for x in (r,b,bridge):validate_forecast(x);match_facts(x,f)
        year=int(r['year']);maximum=pf[year]['max_date']
        if (r['training_max']!=maximum or b['training_date_max']!=maximum or bridge['training_date_max']!=maximum or
            r['rating_cutoff']!=f['prediction_cutoff'] or b['strength_prediction_cutoff']!=f['prediction_cutoff'] or
            bridge['strength_prediction_cutoff']!=f['prediction_cutoff'] or f['prediction_cutoff']>=f['date']):
            raise ValueError('INVALID_TIME_BOUNDARY:'+r['match_id'])
        max_error=max(max_error,abs(float(r['probability'])-float(bridge['probability'])))
        var,base,nh,na,sd=[float(f[k]) for k in ['strength_difference_variance','strength_difference_base_variance',
                                                  'home_jump_intensity','away_jump_intensity','jump_scale_sd']]
        if (not all(math.isfinite(float(f[k])) for k in ['strength_difference','home_variance','away_variance','home_away_covariance'])
            or not all(math.isfinite(x) for x in [var,base,nh,na,sd]) or base<=0 or min(nh,na,sd)<0
            or abs(var-base-(nh+na)*sd*sd)>3e-8 or abs(var-float(f['home_variance'])-float(f['away_variance'])+2*float(f['home_away_covariance']))>3e-8):
            raise ValueError('UNCERTAINTY_DISTRIBUTION_INVALID')
        out={k:f[k] for k in fields};p=float(r['probability'])
        out.update(p_joint=p,p_strength=float(b['probability']),p_past_frequency=float(f"{pf[year]['probability']:.10f}"),
                   training_max=maximum,frequency_training_rows=pf[year]['rows'],
                   outcome_variance_joint=p*(1-p),main_evaluation=2010<=year<=2024)
        output.append(out)
    if max_error>cfg['bridge_probability_tolerance']:raise ValueError('M3_BRIDGE_PROBABILITY_FAILED')
    if len(output)!=16599 or sum(r['main_evaluation'] for r in output)!=9727:raise ValueError('COHORT_CHANGED')
    return output,compat,dict(maximum_M3_bridge_probability_error=max_error,annual_models_checked=75,
                              unique_target_matches=16599,main_matches=9727,
                              only_strength_intercept_and_positive_strength_slope=True,new_fits=0)


def evaluate(rows,cfg):
    labels={'ALL':'全体',**cfg['primary_regions'],'UNKNOWN':'地区未知',
            'SOUTH_AMERICA':'南美（补充）','OTHER_AMERICAS':'其余美洲（补充）'}
    metrics=[];pairs=[];bins=[];coverage=[];teams=[]
    for scope,yr in [('main',cfg['main_years']),('background',cfg['background_years'])]:
        rr=[r for r in rows if yr[0]<=int(r['year'])<=yr[1]]
        for group,label in labels.items():
            ss=[r for r in rr if group in groups(r)]
            counts=Counter(r['home_team_id'] for r in ss);years=Counter(r['year'] for r in ss)
            coverage.append(dict(scope=scope,group=group,label=label,matches=len(ss),
                distinct_home_teams=len(counts),distinct_away_teams=len({r['away_team_id'] for r in ss}),
                years_observed=len(years),dates_observed=len({r['date'] for r in ss}),
                max_home_team_share=max(counts.values())/len(ss) if ss else None,
                max_year_share=max(years.values())/len(ss) if ss else None,
                low_count_warning=0<len(ss)<cfg['coverage_warning_matches'],
                friendly_matches=sum(r['tournament_group']=='friendly' for r in ss),
                cold_start_matches=sum(r['cold_start']=='true' for r in ss),
                disconnected_matches=sum(r['previously_disconnected']=='true' for r in ss),
                status='descriptive_only' if ss else 'empty',supplemental=group in ['SOUTH_AMERICA','OTHER_AMERICAS']))
            for team,n in sorted(counts.items()):teams.append(dict(scope=scope,group=group,home_team_id=team,matches=n))
            for model in cfg['models']:
                metrics.append(dict(scope=scope,group=group,label=label,model=model,**describe(ss,'p_'+model,cfg['probability_clip'])))
                for i,(lo,hi) in enumerate(zip(cfg['probability_bins'][:-1],cfg['probability_bins'][1:])):
                    bb=[r for r in ss if bin_index(float(r['p_'+model]),cfg['probability_bins'])==i]
                    bins.append(dict(scope=scope,group=group,label=label,model=model,bin_index=i,
                        left_inclusive=lo,right=hi,right_inclusive=i==4,**describe(bb,'p_'+model,cfg['probability_clip'])))
            for ref in ['strength','past_frequency']:
                a=describe(ss,'p_joint',cfg['probability_clip']);b=describe(ss,'p_'+ref,cfg['probability_clip'])
                pairs.append(dict(scope=scope,group=group,label=label,reference=ref,matches=len(ss),
                    joint_minus_reference_loss=a['log_loss']-b['log_loss'] if ss else None,
                    relative_loss_reduction=(b['log_loss']-a['log_loss'])/b['log_loss'] if ss and b['log_loss'] else None,
                    inference='descriptive_paired_difference_not_significance',status='descriptive' if ss else 'empty'))
    return {'regional_metrics.csv':metrics,'paired_differences.csv':pairs,'calibration.csv':bins,
            'coverage.csv':coverage,'home_team_counts.csv':teams}


def figures(folder,tables,font):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    fp=FontProperties(fname=font)
    plt.rcParams.update({'svg.hashsalt':'q7-regional-v1','axes.unicode_minus':False,'font.family':fp.get_name()})
    groups_=['150','142','002','019','009','SOUTH_AMERICA','OTHER_AMERICAS']
    labels=[next(r['label'] for r in tables['coverage.csv'] if r['scope']=='main' and r['group']==g) for g in groups_]
    fig,axes=plt.subplots(1,2,figsize=(14,5))
    colors=['#147d92','#b5693b','#7b8585']
    for model,color,label in zip(['joint','strength','past_frequency'],colors,['实力＋背景','仅实力','过去整体主胜比例']):
        rr=[next(r for r in tables['regional_metrics.csv'] if r['scope']=='main' and r['group']==g and r['model']==model) for g in groups_]
        axes[0].plot(range(7),[r['log_loss'] for r in rr],'o-',color=color,label=label)
        axes[1].plot(range(7),[r['bias_pp'] for r in rr],'o-',color=color,label=label)
    for ax,title,ylabel in zip(axes,['概率损失：越低越好','平均预测减实际：正为高估'],['主胜/非主胜对数损失','主胜概率偏差（百分点）']):
        ax.set_xticks(range(7),labels,rotation=25,ha='right');ax.set_title(title);ax.set_ylabel(ylabel);ax.grid(alpha=.2)
    axes[1].axhline(0,color='gray',ls='--',lw=1);axes[0].legend(fontsize=9)
    fig.suptitle('第七问前三步 · 2010—2024同9,727场 · 南美对照与美洲总体重叠，非独立重复',fontsize=12)
    fig.tight_layout();out=[]
    def save(fig,name):
        for ext in ['png','svg']:
            buf=io.BytesIO();fig.savefig(buf,format=ext,dpi=160,bbox_inches='tight',metadata={'Date':None} if ext=='svg' else {})
            path=folder/(name+'.'+ext);atomic_bytes(path,buf.getvalue());out.append(path)
        plt.close(fig)
    save(fig,'regional_performance')
    fig,axes=plt.subplots(2,3,figsize=(13,8))
    for ax,g in zip(axes.flat,['ALL','150','142','002','019','009']):
        for model,color,label in zip(['joint','strength'],colors,['实力＋背景','仅实力']):
            rr=[r for r in tables['calibration.csv'] if r['scope']=='main' and r['group']==g and r['model']==model and r['matches']]
            ax.plot([r['mean_probability'] for r in rr],[r['observed_home_win_rate'] for r in rr],'o-',color=color,label=label)
            for r in rr:
                if model=='joint':ax.annotate(str(r['matches']),(r['mean_probability'],r['observed_home_win_rate']),xytext=(3,5),textcoords='offset points',fontsize=8)
        cover=next(r for r in tables['coverage.csv'] if r['scope']=='main' and r['group']==g)
        ax.plot([0,1],[0,1],'--',color='gray',lw=1);ax.set(xlim=(0,1),ylim=(0,1),title=f"{cover['label']} · {cover['matches']}场",xlabel='平均预测主胜概率',ylabel='实际主胜比例');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=9);fig.suptitle('五个预定概率档 · 数字为联合模型档内场数 · 无置信区间，不代表单场概率已验证',fontsize=12)
    fig.tight_layout();save(fig,'regional_calibration');return out


def run(config_path='config/regional_effectiveness.json'):
    cfg=json.loads((ROOT/config_path).read_text(encoding='utf-8-sig'))
    if cfg['schema_version']!='regional-effectiveness-v1' or cfg['models']!=['joint','strength','past_frequency']:
        raise ValueError('UNKNOWN_PROTOCOL')
    paths,inputs=source_bundle(cfg,config_path)
    import matplotlib
    from matplotlib.font_manager import findfont,FontProperties
    font=findfont(FontProperties(family=['Microsoft YaHei','SimHei','Noto Sans CJK SC']),fallback_to_default=False)
    code=[ROOT/'src/regional_effectiveness.py',ROOT/'scripts/analyze_regional_effectiveness.py',
          ROOT/'tests/test_regional_effectiveness.py',ROOT/'src/data_contract.py',ROOT/'src/strength/io.py',ROOT/'src/history_window/protocol.py']
    identity=dict(protocol=cfg,inputs=inputs,code={p.relative_to(ROOT).as_posix():file_hash(p) for p in code},
                  plotting=dict(font_path=font,font_sha256=file_hash(__import__('pathlib').Path(font)),matplotlib=matplotlib.__version__),environment=environment())
    rid='regional-evaluation-'+fingerprint(identity)[:20]
    log=ROOT/'outputs/logs/regional_effectiveness'/rid;table=ROOT/'outputs/tables/regional_effectiveness'/rid;figure=ROOT/'outputs/figures/regional_effectiveness'/rid
    if (log/'manifest.json').exists():
        for p,h in json.loads((log/'manifest.json').read_text(encoding='utf-8-sig'))['outputs'].items():
            if file_hash(ROOT/p)!=h:raise ValueError('OUTPUT_CHANGED:'+p)
        print('REGIONAL_VERIFIED_COMPLETE',rid,flush=True);return log,table
    for p in (log,table,figure):p.mkdir(parents=True,exist_ok=True)
    write_json(log/'started.json',dict(identity=identity,steps=[1,2,3]));write_json(log/'protocol.json',cfg)
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
        for p in code+[ROOT/config_path]:z.writestr(zipfile.ZipInfo(p.relative_to(ROOT).as_posix(),(1980,1,1,0,0,0)),p.read_bytes())
    atomic_bytes(log/'source_snapshot.zip',archive.getvalue())
    try:
        rows,compat,bridge=prepare(cfg,paths);tables=evaluate(rows,cfg)
        for name,rr in {'evaluation_matches.csv':rows,**tables}.items():atomic_bytes(table/name,csv_bytes(list(rr[0]),rr))
        atomic_bytes(table/'annual_source_compatibility.csv',csv_bytes(list(compat[0]),compat))
        write_json(table/'data_dictionary.json',dict(target='home_win 1 versus draw/away 0',probabilities=['p_joint','p_strength','p_past_frequency'],
            score='natural-log clipped loss; not percent accuracy',bias='probability percentage points',
            outcome_variance_joint='p*(1-p), not CI or strength uncertainty',
            strength_uncertainty='base variance plus (home_jump_intensity+away_jump_intensity)*jump_scale_sd^2; includes covariance',
            old_initialization_diagnostics='deliberately not copied as new-policy validation',
            groups='ALL and primary mutually-exclusive parents plus UNKNOWN; SOUTH_AMERICA/OTHER_AMERICAS overlap Americas parent',
            calibration='five fixed bins, final includes1; empty metrics blank; no uncertainty interval',
            stage4='fields prepared only; no strata analysis, cause or statistical admission'))
        figpaths=figures(figure,tables,identity['plotting']['font_path'])
        review=dict(passed=True,steps_completed=[1,2,3],steps4_6_completed=False,**bridge,
                    table_rows={n:len(rr) for n,rr in tables.items()},new_ratings=0,new_simulations=0,
                    formal_inference=False,human_review=False,checks='sealed sources, compatible mathematics/training/input, paired facts, pre-date cutoffs, uncertainty identities and exact M3 bridge')
        write_json(log/'compatibility.json',bridge);write_json(log/'review.json',review)
        write_json(table/'display_data.json',dict(run_id=rid,main_period=[2010,2024],metrics=tables['regional_metrics.csv'],
            paired_differences=tables['paired_differences.csv'],coverage=tables['coverage.csv'],figures=[p.relative_to(ROOT).as_posix() for p in figpaths],
            interpretation='historical descriptive; fourth-step explanations and fifth-step reliability not run',formal_intervals=False))
        outputs={p.relative_to(ROOT).as_posix():file_hash(p) for folder in (log,table,figure) for p in folder.iterdir() if p.is_file() and p.name not in ['manifest.json','failure.json']}
        write_json(log/'manifest.json',dict(identity=identity,outputs=outputs))
        write_json(log/'adoption.json',dict(run_id=rid,manifest_sha256=file_hash(log/'manifest.json'),steps_completed=[1,2,3],full_question_closed=False,human_review=False))
        write_json(ROOT/'outputs/logs/regional_effectiveness/current.json',dict(run_id=rid,log_directory=log.relative_to(ROOT).as_posix(),
            table_directory=table.relative_to(ROOT).as_posix(),figure_directory=figure.relative_to(ROOT).as_posix(),steps_completed=[1,2,3],formal_inference=False))
        print('REGIONAL_COMPLETE',rid,review,flush=True);return log,table
    except Exception as exc:
        write_json(log/'failure.json',dict(type=type(exc).__name__,message=str(exc)));raise
