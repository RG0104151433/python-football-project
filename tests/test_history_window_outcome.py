import copy,json
from pathlib import Path
import numpy as np
import pytest
from src.strength.io import ROOT,read_rows
from src.strength_joint.design import Design
from src.strength_joint.model import predict
from src.history_window.contracts import load_outcome
from src.history_window.training import fit_year,feedback_rows
from src.history_window.evaluation import summarize
from src.history_window.protocol import training_slice,select_past


def test_annual_feedback_real_labels_and_expired_year():
    _,_,rows,_=load_outcome()
    a,_=training_slice(rows,2005,4);b,_=training_slice(rows,2006,4)
    assert not any(r['date']>='2005-01-01' for r in a)
    assert any(r['date'].startswith('2005') for r in b)
    assert not any(r['date'].startswith('2001') for r in b)
    fake=[dict(policy_id='outcome-4y',match_id='test',date='2005-01-04',year=2005,home_win=0,probability=.7)]
    f=feedback_rows(fake,2024)[0]
    assert f['actual_home_win']==0 and f['predicted_home_probability']==.7
    assert f['result_eligible_from']=='2005-01-05' and f['next_scheduled_model_refit']=='2006-01-01'
    assert f['label_source']=='actual_outcome'


def test_future_labels_never_change_same_year_model_or_predictions():
    cfg,joint,rows,_=load_outcome();rows=[r for r in rows if int(r['year'])<=2000]
    a,model,ledger,_=fit_year(rows,2000,2,cfg,joint['numerics'])
    changed=[dict(r,home_win=str(1-int(r['home_win']))) if r['year']=='2000' else r for r in rows]
    b,other,_,_=fit_year(changed,2000,2,cfg,joint['numerics'])
    assert model['theta']==other['theta']
    assert [r['probability'] for r in a]==[r['probability'] for r in b]
    assert [r['home_win'] for r in a]!=[r['home_win'] for r in b]
    assert ledger['same_year_training_rows']==0


def test_common_sample_proper_metrics_and_probability_rounding():
    r=[dict(match_id='a',probability=.7,home_win=0),dict(match_id='b',probability=.2,home_win=1)]
    m=summarize(r,1e-6)
    assert m['primary_log_loss']==pytest.approx(-np.log(.3*.2)/2)
    assert m['binary_accuracy']==0 and m['matches']==2
    with pytest.raises(ValueError):summarize([dict(match_id='a',probability=1.1,home_win=0)],1e-6)


def test_selection_is_pooled_not_mean_of_annual_means_and_ties_prefer_cumulative():
    annual=[]
    for year,n in [(2000,1000),(2001,1)]:
        for w,loss in [('2y',.6 if n==1000 else 0.),('cumulative',.5 if n==1000 else 1.)]:
            annual.append(dict(year=year,window=w,matches=n,loss_sum=n*loss,id_set_sha256=str(year)))
    assert select_past(annual,2002,[2,None])=='cumulative'
    for r in annual:r['loss_sum']=r['matches']*.5
    assert select_past(annual,2002,[2,None])=='cumulative'
