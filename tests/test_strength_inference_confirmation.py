import csv,itertools,json,math
import numpy as np
from scripts import confirm_strength_inference as confirmation


def fixture(tmp_path,monkeypatch,failures=0,numerical=False):
    monkeypatch.setattr(confirmation,'ROOT',tmp_path)
    registry=tmp_path/'outputs/tables/strength_joint/stage6-preparation-662dd5a756b8c1bf7688/target_registry.csv'
    registry.parent.mkdir(parents=True)
    with registry.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['registry_id','family']);w.writeheader()
        w.writerows(dict(registry_id=str(i),family='F_PRIMARY_CONDITIONAL') for i in range(54))
    folder=tmp_path/'experiment';folder.mkdir()
    (folder/'scope_calibration.json').write_text(json.dumps(dict(fixed_original_scales_pp=[1.]*54,
        scenarios=dict(test=dict(registry_ids=[str(i) for i in range(30)],methods={'A':{'critical':1.},'B':{'critical':.9}})))))
    config=dict(scenario='test',seeds=[840000,840192],gate_probability=.93,alternative_probability=.99,
        original_gate_error_budget=.0125,first_stage_worlds=64,decision_log_id='test',schema_version='test')
    for i in range(96):
        if numerical and i==0:
            path=folder/'failures/test/confirmation/840000.json';path.parent.mkdir(parents=True);path.write_text('{}');continue
        path=folder/'fits/test/confirmation'/f'{840000+i}.json';path.parent.mkdir(parents=True,exist_ok=True)
        error=np.zeros(54);error[40]=10 # An unadmitted regional change cannot change the30-target test.
        if i<failures:error[0]=2
        # B must be checked against A's ACTUAL estimator error, not its own approximation.
        path.write_text(json.dumps(dict(A_error_pp=error.tolist(),B_linearized_error_pp=[1000.]*54)))
    return folder,config


def test_new_stream_confirmation_uses_only_actual_error_and_frozen_family(tmp_path,monkeypatch):
    folder,config=fixture(tmp_path,monkeypatch);result=confirmation.summarize(folder,config,96)
    assert result['all_routes_passed']
    for row in result['assessments']:
        assert row['successes']==96 and row['fresh_stream_CS_lower']>.93
        assert abs(row['combined_error_bound']-.0125)<1e-14
        assert not row['old_worlds_in_e_process']


def test_new_stream_failure_is_in_the_denominator(tmp_path,monkeypatch):
    folder,config=fixture(tmp_path,monkeypatch,numerical=True);result=confirmation.summarize(folder,config,96)
    assert not result['all_routes_passed']
    assert all(r['successes']==95 and r['numerical_failures']==1 for r in result['assessments'])


def test_one_joint_noncontainment_does_not_get_patched_by_reusing_old_trials(tmp_path,monkeypatch):
    folder,config=fixture(tmp_path,monkeypatch,failures=1);result=confirmation.summarize(folder,config,96)
    assert not result['all_routes_passed']
    assert all(abs(r['log_e_value']-(95*math.log(.99/.93)+math.log(.01/.07)))<1e-12 for r in result['assessments'])


def test_bernoulli_supermartingale_and_finite_path_crossing_bound():
    p0=.5;q=.8;threshold=2.;horizon=12
    assert all(p*q/p0+(1-p)*(1-q)/(1-p0)<=1+1e-14 for p in np.linspace(0,p0,11))
    crossing=0.
    for bits in itertools.product((0,1),repeat=horizon):
        e=1.;hit=False
        for b in bits:
            e*=q/p0 if b else (1-q)/(1-p0);hit|=e>=threshold
        if hit:crossing+=p0**sum(bits)*(1-p0)**(horizon-sum(bits))
    assert 0<crossing<=1/threshold
