import math
import numpy as np
import pytest
from src.history_window.reliability import (
    normalize, pair, assert_alias, daily, subset_metric, seed_comparisons, prior_engine)
from src.history_window.protocol import paired_radius


def rows():
    return [dict(match_id='a', date='2010-01-02', home_win='1', probability=.8),
            dict(match_id='b', date='2010-01-02', home_win='0', probability=.4),
            dict(match_id='c', date='2010-01-03', home_win='1', probability=.6)]


def test_pair_sorting_and_hand_calculation():
    a = rows(); b = [dict(r, probability=.5) for r in a]
    ordered, la, lb, d = pair(list(reversed(a)), b, 1e-6)
    assert [r['match_id'] for r in ordered] == ['a', 'b', 'c']
    assert d.mean() == pytest.approx((-math.log(.8)-2*math.log(.6))/3-math.log(2))
    assert np.allclose(d, la-lb)


@pytest.mark.parametrize('field,value', [('home_win','0'), ('date','2010-01-04')])
def test_fact_mismatch_is_rejected(field, value):
    a = rows(); b = [dict(r) for r in a]; b[0][field] = value
    with pytest.raises(ValueError, match='PAIRED_FACTS_DIFFER'):
        pair(a, b, 1e-6)


def test_invalid_values_duplicates_and_aliases_are_rejected():
    for change in (dict(home_win='0.5'), dict(probability=float('nan')), dict(probability=1.01)):
        a = rows(); a[0].update(change)
        with pytest.raises(ValueError): normalize(a)
    with pytest.raises(ValueError, match='DUPLICATE'): normalize(rows()+rows()[:1])
    assert_alias(rows(), list(reversed(rows())))
    changed = rows(); changed[0]['probability'] += .0000000001
    with pytest.raises(ValueError, match='REGISTERED_ALIAS_DIFFER'): assert_alias(rows(), changed)


def test_daily_batch_bound_uses_squared_batch_sizes():
    grouped = daily(rows(), [.2, -.1, .3])
    assert [r['matches'] for r in grouped] == [2, 1]
    assert grouped[0]['loss_difference_sum'] == pytest.approx(.1)
    counts = [2, 1]; powers = [-4, -3]
    b = math.log((1-1e-6)/1e-6); c = math.log(2*60*2/.05)
    expected = min(c/2**p+2**p*b*b*(4+1)/2 for p in powers)/3
    assert paired_radius(counts, powers=powers) == pytest.approx(expected)


def test_subset_uses_one_shared_mask_and_keeps_empty_explicit():
    out = subset_metric(rows(), np.array([1., 2., 4.]), np.array([2., 2., 1.]),
                        [False, True, True], 'shared')
    assert out['matches'] == 2 and out['mean_loss_minus_baseline'] == 1.5
    assert out['refitted'] is False
    empty = subset_metric(rows(), np.ones(3), np.ones(3), [False]*3, 'empty')
    assert empty['matches'] == 0 and empty['mean_loss_minus_baseline'] is None


def test_seed_pairing_mcse_and_missing_cells():
    cfg = dict(simulation_seeds=[1, 2], simulation_paths=['jump'], simulation_links=['probit'], windows=[2],
               simulation_baseline='cumulative')
    rr = []
    for seed, error in [(1, 2.), (2, 4.)]:
        for name, value in [('cumulative', 1.), ('annual_reset_2y', error)]:
            rr.append(dict(seed=seed, path='jump', link='probit', policy_name=name,
                           months=120, gap_mse=value, native_probability_mse=value/10))
    out = seed_comparisons(rr, cfg)[0]
    assert out['gap_mse_difference'] == 2.
    assert out['gap_mse_paired_mcse'] == pytest.approx(1.)
    with pytest.raises(ValueError, match='SEED_CELL'): seed_comparisons(rr[:-1], cfg)


def test_prior_scale_applies_to_both_variances(monkeypatch):
    import src.strength.collapsed_jump as core
    monkeypatch.setattr(core, 'CollapsedJumpFilter', lambda roster, p, n, team, home: (team, home))
    assert prior_engine(['a','b'], {}, {}, .5, 1., .25) == (.5, .125)
