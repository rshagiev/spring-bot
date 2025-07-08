import pytest
import pandas as pd
import numpy as np
from backtest_runner import run_backtest, calculate_metrics

def test_backtest_run(monkeypatch): # <-- ADDED monkeypatch
    # Create synthetic data with some volatility to prevent sigma=0
    prices = pd.DataFrame({
        'ts': range(100, 200),
        'close': list(np.linspace(101, 100, 50)) + list(np.linspace(91, 90, 50)),
        'low': list(np.linspace(100, 99, 50)) + list(np.linspace(86, 85, 50)),
        'high': list(np.linspace(102, 101, 50)) + list(np.linspace(96, 95, 50))
    })
    signals = pd.DataFrame({
        'ts': [150],
        'side': ['long'],
        'entry': [90],
        'sl': [88]
    })
    
    # Use monkeypatch to correctly override the function in the target module
    monkeypatch.setattr("backtest_runner.bounce_prob", lambda *args, **kwargs: 1.0)
    
    equity_curve, trades = run_backtest(prices, signals, bb_window=20, bb_std_dev=2.0)
    
    assert len(trades) > 0
    assert equity_curve[-1] != 1000.0

def test_metrics_calculation():
    equity_curve = [1000, 1010, 1005, 1020, 1015]
    total_r, max_dd, sharpe = calculate_metrics(equity_curve, num_days=1)
    
    assert total_r == pytest.approx(0.015)
    # The calculated value is -0.004950495...
    assert max_dd == pytest.approx(-0.00495, abs=1e-5)
    assert sharpe is not None