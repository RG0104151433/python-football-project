import pytest
from src.regional_diagnostics import thresholds,classify,common_weights,standardized


def example(date,gap,var,y='1'):
    return dict(match_id=date,date=date,strength_difference=gap,strength_difference_variance=var,home_win=y,
                home_history='10',away_history='10',tournament_group='friendly',relation='same_region_diff_unit')


def test_cutpoints_ignore_target_year_features_and_all_outcomes():
    rows=[example('2008-01-01',1.,1.),example('2009-01-01',3.,9.),example('2010-01-01',100.,10000.)]
    old=thresholds(rows,'1980-01-01','2010-01-01')
    rows[-1]['strength_difference']=-1000
    for r in rows:r['home_win']='0'
    assert thresholds(rows,'1980-01-01','2010-01-01')==old
    assert old['signed_gap_magnitude']==2. and old['training_rows']==2


def test_signed_inclusive_boundary_and_uncertainty_ties():
    cut=dict(signed_gap_magnitude=2.,absolute_gap_cuts=[1.,3.],uncertainty_sd_cuts=[1.,3.])
    out=classify(example('2010-01-01',-2.,1.),cut,5)
    assert out['signed_gap']=='relatively_close' and out['uncertainty']=='middle'
    assert classify(example('2010-01-01',2.01,16.),cut,5)['signed_gap']=='home_advantage'


def test_common_weights_exclude_absent_cell_without_imputation():
    by={'a':[{'joint_cell':'x'},{'joint_cell':'y'}],'b':[{'joint_cell':'y'}]}
    cells,weights,counts=common_weights(by,['x','y'])
    assert cells==['y'] and weights=={'y':1.} and counts['b']['x']==0


def test_no_shared_support_is_explicitly_blank():
    _,w,_=common_weights({'a':[{'joint_cell':'x'}],'b':[{'joint_cell':'y'}]},['x','y'])
    out=standardized([],w,'p_joint',1e-6)
    assert out['status']=='no_common_support' and out['log_loss'] is None


def test_standardized_mean_uses_reference_weights_not_own_counts():
    a=[dict(joint_cell='x',p_joint=.9,home_win='1')]*9+[dict(joint_cell='y',p_joint=.1,home_win='1')]
    b=[dict(joint_cell='x',p_joint=.9,home_win='1')]+[dict(joint_cell='y',p_joint=.1,home_win='1')]*9
    _,w,_=common_weights({'a':a,'b':b},['x','y'])
    assert standardized(a,w,'p_joint',1e-6)['log_loss']==pytest.approx(standardized(b,w,'p_joint',1e-6)['log_loss'])
    assert w=={'x':.5,'y':.5}


def test_missing_positive_weight_cell_rejected():
    with pytest.raises(ValueError,match='MISSING_POSITIVE'):
        standardized([dict(joint_cell='x')],{'y':1.},'p_joint',1e-6)
