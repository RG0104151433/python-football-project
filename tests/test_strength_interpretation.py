import numpy as np
import pytest
from src.strength_interpretation import paired_metrics, losses, target_ledger, curves


def test_paired_loss_sign_and_weighted_group_reconstruction():
    y=np.array([0.,1.,1.,0.,1.]);a=np.full(5,.5);b=np.array([.2,.8,.7,.3,.9])
    whole=paired_metrics(y,a,b)
    groups=[paired_metrics(y[:2],a[:2],b[:2]),paired_metrics(y[2:],a[2:],b[2:])]
    assert whole['loss_reduction']>0
    assert abs(sum(r['matches']*r['loss_reduction'] for r in groups)/5-whole['loss_reduction'])<1e-15
    assert whole['accuracy_change_pp']==40.


def test_probability_boundary_is_an_error_not_silent_clipping():
    with pytest.raises(ValueError,match='probability'):
        losses(np.array([1.]),np.array([0.]))


def test_model_range_keeps_original_missing_support_and_is_not_ci():
    rows=[]
    for kind,n in [('full',100),('cell_range_overlap',8)]:
        for model,v in [('M3_nested',1.),('M4_type_slope',2.),('M5_relation',-.5)]:
            rows.append(dict(target_id='T',reference_kind=kind,reference_id='r'+kind,model_id=model,difference_pp=str(v),
                reference_rows=str(n),label='label',old_target_status='unsupported_positive_reference_layer'))
    result=target_ledger(rows,[],dict(target_model_comparison=['M3_nested','M4_type_slope','M5_relation']))
    assert all(r['original_target_status']=='unsupported_positive_reference_layer' for r in result)
    assert result[0]['specified_model_min_pp']==-.5
    assert result[0]['specified_model_max_pp']==2
    assert not result[0]['same_direction_in_these_models']
    assert result[0]['retained_reference_fraction']==.08
    assert not result[0]['model_range_is_confidence_interval']


def test_curve_counts_can_be_saved_to_json():
    import json
    from src.strength_joint.design import Design
    rows=[dict(match_id=str(i),era='1980s',tournament_group='friendly' if i%2 else 'non_friendly',
        home_region='150',away_region='150',home_unit='154',away_unit='154',strength_difference=.1*i,
        strength_difference_base_variance=.3,home_jump_intensity=.01,away_jump_intensity=.02,jump_scale_sd=1.2) for i in range(6)]
    models={'M1_strength':dict(model_id='M1_strength',names=['intercept'],slope_names=['log_b'],theta=[0.,0.],mode='mixture')}
    cfg=dict(curve_models=['M1_strength'],curve_mean_min=0,curve_mean_max=0,curve_mean_step=.25,analysis='fixture',curve_reference='fixture')
    result,_=curves(rows,Design(rows),models,cfg,dict(support_bins=[-1,0,1],sparse_cell_warning=20))
    assert json.loads(json.dumps(result))[0]['observed_nearby_matches']==1
