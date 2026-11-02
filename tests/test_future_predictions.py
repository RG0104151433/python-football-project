import numpy as np
import pytest
from scipy.special import ndtr
from scipy.stats import norm
from src.future_predictions import latent_probability_range
from src.strength_joint.design import Design

def test_latent_quantile_normal_limit_and_not_forced_to_straddle_marginal_mean():
    lo,hi=latent_probability_range(.4,.25,0,1.2,-.2,1.5)
    assert lo==pytest.approx(ndtr(-.2+1.5*(.4+.5*norm.ppf(.05))))
    assert hi==pytest.approx(ndtr(-.2+1.5*(.4+.5*norm.ppf(.95))))

def test_latent_range_jump_symmetry_and_variance_validation():
    lo,hi=latent_probability_range(0,.2,.1,1.2,0,1)
    assert lo+hi==pytest.approx(1.) and 0<lo<hi<1
    with pytest.raises(ValueError):latent_probability_range(0,0,.1,1.2,0,1)

def test_future_era_explicit_latest_column_instead_of_baseline():
    rows=[dict(era='2020_2024',tournament_group='non_friendly',home_region='150',away_region='150',home_unit='154',away_unit='155')]
    x,n=Design(rows).matrix(rows,'M3_nested')
    assert x[0,n.index('era:2020_2024')]==1 and np.isfinite(x).all()
