from collections import Counter
import pytest
from src.strength_stage6_prepare import timeline,decompose,registry


def game(mid,day,h,a):return dict(match_id=mid,date=day,home=h,away=a)


def test_same_day_prior_counts_and_dates_are_shared_not_sequential():
    gs=[game('a','1960-01-01','x','y'),game('b','1960-01-01','x','z'),game('c','1960-01-03','x','y')]
    out=timeline(gs,1960)
    assert out['a']['home_history']==out['b']['home_history']==0
    assert out['a']['home_elapsed_years']==out['b']['home_elapsed_years']==0
    assert out['c']['home_history']==2
    assert out['c']['prediction_cutoff']=='1960-01-01'
    assert abs(out['c']['home_elapsed_years']-2/365.2425)<1e-15


def test_start_boundary_and_first_appearance_do_not_invent_prior_inactivity():
    gs=[game('old','1959-12-31','x','y'),game('first','1960-01-02','z','y'),game('next','1961-01-02','x','z')]
    out=timeline(gs,1960)
    assert 'old' not in out
    assert out['next']['home_history']==0 and out['next']['home_elapsed_years']==0
    assert out['next']['prediction_cutoff']=='1960-01-02'


def test_variance_decomposition_and_invalid_inputs():
    assert abs(decompose(.8,.1,.2,1.2)-.368)<1e-14
    with pytest.raises(ValueError):decompose(.1,.1,.2,1.2)
    with pytest.raises(ValueError):decompose(.8,-.1,.2,1.2)


def test_registry_preserves_missing_support_and_separates_relation_objects():
    data=[];changes=[]
    for i in range(32):
        for kind in ['full','cell_range_overlap']:
            data.append(dict(model_id='M3_nested',target_id=str(i),reference_kind=kind,reference_id='r'+kind,
                old_target_status='supported_point_target' if i<27 else 'unsupported_positive_reference_layer',difference_pp='1'))
            changes.append(dict(target_id=str(i),reference_kind=kind,change_pp='-.5'))
    curve=[dict(model_id='M4_type_slope',reference_id='curve',strength_mean=str(d),friendly_minus_other_pp=str(d+1)) for d in [-2,0,2]]
    models={'M4_type_slope':dict(names=[],slope_names=['log_b_nonfriendly','log_b_friendly'],theta=[-.4,-.7])}
    layers=[dict(comparison_id=str(i),after_model='B',before_model='A',loss_reduction='.1') for i in range(8)]
    out=registry(data,changes,curve,models,layers,dict(relation_model='M4_type_slope',relation_mean_points=[-2,0,2]))
    assert len(out)==len({r['registry_id'] for r in out})==143
    assert Counter(r['family'] for r in out)==dict(F_PRIMARY_CONDITIONAL=54,F_AUX_REFERENCE=64,F_EXTRAPOLATION_ONLY=10,F_EXPLORATORY_RELATIONS=7,F_DESCRIPTIVE_FIT=8)
    slope=next(r for r in out if r['registry_id']=='S6:relation:log_slope')
    change=next(r for r in out if r['registry_id']=='S6:relation:probability_change_2')
    assert abs(slope['estimate']+.3)<1e-15
    assert change['estimate']==2 and change['effect_size_axis']!=slope['effect_size_axis']
    assert all(r['inference_status']=='NOT_ADMITTED' for r in out)
