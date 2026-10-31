"""Same-match descriptive metrics and past-only annual policy selection."""
from itertools import combinations
import numpy as np
from .protocol import log_losses,label,select_past
from .contracts import id_digest


def summarize(rows,epsilon):
    p=np.array([float(r['probability']) for r in rows]);y=np.array([int(r['home_win']) for r in rows])
    losses=log_losses(p,y,epsilon);raw=log_losses(p,y,1e-15)
    return dict(matches=len(rows),primary_log_loss=float(losses.mean()),loss_sum=float(f'{float(losses.sum()):.10f}'),
        raw_log_loss=float(raw.mean()),brier=float(np.mean((p-y)**2)),binary_accuracy=float(np.mean((p>=.5)==y)),
        mean_probability=float(p.mean()),observed_home_win_rate=float(y.mean()),calibration_bias_pp=100*float(np.mean(p-y)),
        primary_probability_clips=int(np.sum((p<epsilon)|(p>1-epsilon))),id_set_sha256=id_digest(rows))


def evaluate(predictions,cfg):
    eps=cfg['probability_clip'];annual=[];groups=[];pairs=[];bins=[]
    for w in cfg['windows']:
        rr=[r for r in predictions if r['window']==label(w)]
        if len(rr)!=16599 or len({r['match_id'] for r in rr})!=len(rr):raise ValueError('POLICY_SAMPLE_MISMATCH')
        for year in range(cfg['first_year'],cfg['last_year']+1):
            annual.append(dict(year=year,window=label(w),**summarize([r for r in rr if int(r['year'])==year],eps)))
        for name,start,end in [('all',2000,2024),('development',2000,2009),('adaptive_evaluation',2010,2024)]:
            groups.append(dict(group=name,window=label(w),**summarize([r for r in rr if start<=int(r['year'])<=end],eps)))
        for field in ('tournament_group','era','home_region'):
            for value in sorted({r[field] for r in rr}):
                ss=[r for r in rr if r[field]==value]
                groups.append(dict(group=field+':'+value,window=label(w),**summarize(ss,eps)))
        for b in range(10):
            ss=[r for r in rr if min(int(float(r['probability'])*10),9)==b]
            if ss:bins.append(dict(window=label(w),bin_lower=b/10,bin_upper=(b+1)/10,**summarize(ss,eps)))
    for wa,wb in combinations([label(w) for w in cfg['windows']],2):
        for scope,start,end in [('all',2000,2024),('development',2000,2009),('adaptive_evaluation',2010,2024)]:
            a=sorted((r for r in predictions if r['window']==wa and start<=int(r['year'])<=end),key=lambda r:r['match_id'])
            b=sorted((r for r in predictions if r['window']==wb and start<=int(r['year'])<=end),key=lambda r:r['match_id'])
            if [r['match_id'] for r in a]!=[r['match_id'] for r in b] or [r['home_win'] for r in a]!=[r['home_win'] for r in b]:
                raise ValueError('PAIRED_SAMPLE_MISMATCH')
            d=log_losses([r['probability'] for r in a],[r['home_win'] for r in a],eps)-log_losses([r['probability'] for r in b],[r['home_win'] for r in b],eps)
            pairs.append(dict(group=scope,policy_a=wa,policy_b=wb,matches=len(a),mean_loss_a_minus_b=float(d.mean()),
                              a_better_matches=int(np.sum(d<0)),b_better_matches=int(np.sum(d>0)),equal_matches=int(np.sum(d==0)),
                              interpretation='descriptive paired loss; no confidence interval or significance claim'))
    decisions=[];adaptive=[]
    for year in range(cfg['adaptive_first_year'],cfg['last_year']+1):
        selected=select_past(annual,year,cfg['windows'])
        past=[r for r in annual if r['window']==selected and int(r['year'])<year]
        now=[r for r in predictions if int(r['year'])==year and r['window']==selected]
        decisions.append(dict(year=year,selected_window=selected,selection_last_year=year-1,
            selection_matches=sum(r['matches'] for r in past),selection_loss_sum=sum(r['loss_sum'] for r in past),
            target_matches=len(now),selection_uses_current_year_outcomes=False))
        adaptive.extend(dict(r,policy_id='adaptive-prior-years',selected_window=selected) for r in now)
    metrics=[dict(group='adaptive_evaluation',window='adaptive-prior-years',**summarize(adaptive,eps))]
    metrics.extend(dict(group=f'year:{y}',window='adaptive-prior-years',**summarize([r for r in adaptive if int(r['year'])==y],eps)) for y in range(2010,2025))
    return {'yearly_metrics.csv':annual,'group_metrics.csv':groups,'paired_losses.csv':pairs,'calibration_bins.csv':bins,
            'selection_decisions.csv':decisions,'adaptive_predictions.csv':adaptive,'adaptive_metrics.csv':metrics}
