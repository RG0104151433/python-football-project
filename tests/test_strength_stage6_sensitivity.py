from fractions import Fraction
import numpy as np
import pytest
from src.strength_stage6_sensitivity import EstimableDesign,materialize,altered_rows


class TinyDesign:
    def matrix(self,rows,model):
        return np.array([[1.,r['unknown']] for r in rows]),['intercept','unknown']


def test_dropped_unknown_parameter_does_not_become_baseline_prediction():
    training=[dict(unknown=0.) for _ in range(8)]
    design=EstimableDesign(TinyDesign(),training,'M3_nested')
    assert design.dropped==['unknown']
    assert design.estimable([dict(unknown=0.),dict(unknown=1.)]).tolist()==[True,False]
    with pytest.raises(ValueError,match='NONESTIMABLE'):
        design.matrix([dict(unknown=1.)],'M3_nested')


def test_conditioning_frozen_mixtures_preserves_equal_reference_population():
    rs={str(i):dict(match_id=str(i),home_unit='a' if i<2 else 'b') for i in range(4)}
    pieces=[]
    for h in ['a','b']:
        for away in ['u','v']:
            pieces.append(dict(target_id='Q3:B_TEST',home_unit_constant=h,away_unit_constant=away,
                era_constant='__varies__',tournament_group_constant='__varies__',home_region_constant='__varies__',away_region_constant='__varies__',
                weight_numerator='1',weight_denominator='4',piece_reference_rows='2'))
    result=materialize(pieces,list(rs),rs,['0','2','3'])
    assert abs(sum(w for w,_ in result)-1)<1e-15
    mass={i:0. for i in ['0','2','3']}
    for w,group in result:
        for r in group:mass[r['match_id']]+=w/len(group)
    assert all(abs(v-1/3)<1e-15 for v in mass.values())


def test_variant_score_replacement_removes_incompatible_covariance_metadata():
    rows=[dict(match_id='1',home_variance=7,away_variance=8,home_away_covariance=2)]
    fields=('strength_difference','strength_difference_variance','strength_difference_base_variance','home_jump_intensity','away_jump_intensity','jump_scale_sd','prediction_cutoff','home_history','away_history','cold_start')
    prepared=[dict(match_id='1',**{k:'value' for k in fields})]
    result=altered_rows(rows,prepared)
    assert 'home_variance' not in result[0] and result[0]['strength_difference']=='value'
    assert rows[0]['home_variance']==7
