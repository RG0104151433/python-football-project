import numpy as np
import pytest
from src.regional_stability import Cohort,concentration,targets,stories


def row(i,home='a',away='b',cell='x',p=.8,y=1,region='150',year=2010):
    return dict(match_id=str(i),home_team_id=home,away_team_id=away,joint_cell=cell,
                p_joint=p,p_strength=.5,home_win=y,home_region=region,home_unit='',
                year=year,uncertainty='low')


def target(weighted=False,kind='paired'):
    return dict(target_id='test',group_a='150',group_b='',weighted=weighted,
                kind=kind,metric='loss_difference')


def test_team_deletion_includes_away_and_removes_each_match_once():
    d=Cohort([row(1),row(2,home='c',away='a'),row(3,home='c',away='d')],1e-6)
    keep=d.keep('team','a')
    assert keep.tolist()==[False,False,True]
    assert d.evaluate(target(),keep)['removed_matches']==2


def test_missing_positive_weight_cell_is_blank_not_renormalized():
    d=Cohort([row(1,cell='x'),row(2,cell='y',year=2011)],1e-6)
    out=d.evaluate(target(True),d.keep('year','2011'),{'x':.25,'y':.75})
    assert out['value'] is None and out['status']=='unsupported' and 'y' in out['reason']


def test_fixed_weights_and_delete_mean_identity():
    d=Cohort([row(1,cell='x'),row(2,cell='x',p=.2),row(3,cell='y',p=.3,year=2011)],1e-6)
    original=d.evaluate(target())['value']
    after=d.evaluate(target(),np.array([True,False,True]))['value']
    assert after==pytest.approx((3*original-d.values['loss_difference'][1])/2)
    weighted=d.evaluate(target(True),weights={'x':.1,'y':.9})['value']
    assert weighted==pytest.approx(.1*d.values['loss_difference'][:2].mean()+.9*d.values['loss_difference'][2])


def test_same_global_deletion_for_both_regional_arms():
    d=Cohort([row(1,p=.9),row(2,p=.4,year=2011),row(3,region='002',p=.6),
              row(4,region='002',p=.3,year=2011)],1e-6)
    t=dict(target_id='between',group_a='002',group_b='150',weighted=False,kind='between',metric='joint_loss')
    out=d.evaluate(t,d.keep('year',2010))
    assert out['remaining_by_group']=={'002':1,'150':1}
    assert out['value']==pytest.approx(d.values['joint_loss'][3]-d.values['joint_loss'][1])


def test_reference_no_common_support_empty_and_equal_region_differs():
    cells=['away_advantage|low','away_advantage|middle']
    rr=[row(i,cell=cells[0]) for i in range(9)]+[row(9,cell=cells[1])]
    rr += [row(10,region='002',cell=cells[0]),row(11,region='002',cell=cells[1])]
    # Other primary regions have no rows; no fabricated shared support.
    d=Cohort(rr,1e-6)
    assert d.reference('primary5')[0]=={}
    out=d.evaluate(target(True),weights={})
    assert out['value'] is None and out['remaining_matches']==0
    amer=[dict(r,home_region='019',home_unit='005') for r in rr[:10]]
    amer += [dict(r,home_region='019',home_unit='013') for r in rr[10:]]
    a=Cohort(amer,1e-6)
    pooled,_=a.reference('americas2')
    equal,_=a.reference('americas2','equal_region')
    assert pooled[cells[0]]==pytest.approx(10/12)
    assert equal[cells[0]]==pytest.approx(.7)
    assert a.reference('americas2',minimum=10)[0]=={}


def test_concentration_is_weight_only_and_rejects_invalid_weights():
    assert concentration([.5,.5])['weight_concentration_equivalent_matches']==2
    assert concentration([.9,.1])['weight_concentration_equivalent_matches']==pytest.approx(1/.82)
    with pytest.raises(ValueError,match='INVALID_NORMALIZED'):
        concentration([.2,.2])


def test_target_registry_and_joint_stories_do_not_select_different_deletions():
    assert [t['target_id'] for t in targets()]==[f'T{i:02d}' for i in range(1,14)]
    assert all('probability_bin' in t for t in targets())
    rr=[dict(target_id=f'T{i:02d}',value=.1,affected=True) for i in range(1,14)]
    next(r for r in rr if r['target_id']=='T11')['value']=-.2
    result=stories(rr,'year','2011')
    assert next(r for r in result if r['story']=='south_america_order_reverses')['story_preserved']
    next(r for r in rr if r['target_id']=='T11')['value']=None
    assert next(r for r in stories(rr,'year','2011') if r['story']=='south_america_order_reverses')['status']=='unsupported'
