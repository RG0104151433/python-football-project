import copy
import numpy as np
import pytest
from src.data_contract import file_hash,write_json
from src.history_window import joint


def fixture_rows():
    return [dict(match_id=str(y),date=f'{y}-01-01',year=str(y),era='2000s',tournament_group='friendly',
        home_region='150',home_win=str(y%2),prediction_cutoff='initial_prior' if y==1988 else f'{y-1}-12-31')
        for y in [1987,1988,1989,1999,2000,2001]]


def stub_fit(monkeypatch):
    seen=[]
    class Design:
        def __init__(self,rows):self.weights={}
    def fit(rows,*args):
        seen.append(copy.deepcopy(rows))
        return dict(numerical_fit_passed=True,mean=np.mean([int(r['home_win']) for r in rows]))
    monkeypatch.setattr(joint,'Design',Design);monkeypatch.setattr(joint,'fit_past',fit)
    monkeypatch.setattr(joint,'predict',lambda m,rows,d:np.full(len(rows),m['mean']))
    return seen


def config():
    return dict(outcome_start='1980-01-01',model='M3_nested',ridge_precision=1.,probability_storage_decimals=10,
        max_single_job_seconds=600,max_rss_mib=2048)


def test_annual_window_expires_and_real_prior_year_enters(monkeypatch):
    seen=stub_fit(monkeypatch);rows=fixture_rows()
    _,_,a,_=joint.fit_annual(rows,2000,'annual_reset_12y',config(),{})
    _,_,b,_=joint.fit_annual(rows,2001,'annual_reset_12y',config(),{})
    assert [r['match_id'] for r in seen[0]]==['1988','1989','1999']
    assert [r['match_id'] for r in seen[1]]==['1989','1999','2000']
    assert a['left_inclusive']=='1988-01-01' and b['left_inclusive']=='1989-01-01'
    assert a['same_year_training_rows']==b['same_year_training_rows']==0


def test_current_result_changes_label_not_current_forecast(monkeypatch):
    stub_fit(monkeypatch);rows=fixture_rows()
    a,_,_,_=joint.fit_annual(rows,2000,'annual_reset_20y',config(),{})
    changed=[dict(r,home_win=str(1-int(r['home_win']))) if r['year']=='2000' else r for r in rows]
    b,_,_,_=joint.fit_annual(changed,2000,'annual_reset_20y',config(),{})
    assert a[0]['probability']==b[0]['probability'] and a[0]['home_win']!=b[0]['home_win']


def test_corrupt_resume_bundle_is_rejected(tmp_path):
    write_json(tmp_path/'bundle.json',dict(probability=.6))
    write_json(tmp_path/'complete.json',dict(task_sha256='task',bundle_sha256=file_hash(tmp_path/'bundle.json')))
    assert joint.load_job(tmp_path,'task')['probability']==.6
    write_json(tmp_path/'bundle.json',dict(probability=.4))
    with pytest.raises(ValueError,match='JOINT_CHECKPOINT_CHANGED'):joint.load_job(tmp_path,'task')
