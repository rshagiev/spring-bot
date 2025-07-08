import pytest
import pandas as pd
import numpy as np
from spring_model import bounce_prob

@pytest.fixture
def synthetic_bars():
    # Synthetic data where mu=100, sigma=5
    # Lower BB = 100 - 2*5 = 90
    # Upper BB = 100 + 2*5 = 110
    np.random.seed(42)
    data = np.concatenate([np.random.normal(100, 5, 19), [100]])
    return pd.DataFrame({'close': data})

def test_long_bounce_strong(synthetic_bars):
    # Price is far below the lower BB, expecting high probability
    prob = bounce_prob(synthetic_bars, 'long', price=80, bb_std_dev=2.0)
    assert prob > 0.5
    assert prob <= 1.0

def test_long_bounce_zero(synthetic_bars):
    # Price is inside the bands, expecting zero probability
    prob = bounce_prob(synthetic_bars, 'long', price=95, bb_std_dev=2.0)
    assert prob == 0.0

def test_short_bounce_strong(synthetic_bars):
    # Price is far above the upper BB, expecting high probability
    prob = bounce_prob(synthetic_bars, 'short', price=120, bb_std_dev=2.0)
    assert prob > 0.5
    assert prob <= 1.0

def test_short_bounce_zero(synthetic_bars):
    # Price is inside the bands, expecting zero probability
    prob = bounce_prob(synthetic_bars, 'short', price=105, bb_std_dev=2.0)
    assert prob == 0.0

def test_edge_case_not_enough_data():
    bars = pd.DataFrame({'close': [100, 101]})
    prob = bounce_prob(bars, 'long', price=95, bb_window=20)
    assert prob == 0.0

def test_edge_case_zero_volatility():
    bars = pd.DataFrame({'close': [100] * 20})
    prob = bounce_prob(bars, 'long', price=95, bb_window=20)
    assert prob == 0.0

def test_invalid_side(synthetic_bars):
    with pytest.raises(ValueError):
        bounce_prob(synthetic_bars, 'sideways', price=100)