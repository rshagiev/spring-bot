# File: tests/test_risk_sizer.py
import pytest
from risk_sizer import calculate_position_size

def test_calculate_position_size_btc():
    # step для BTC = 0.001
    size = calculate_position_size(60000.0, 59000.0, 1000.0, amount_precision_step=0.001)
    assert size == 0.01

def test_calculate_position_size_altcoin():
    # step для SOL = 0.01
    size = calculate_position_size(150.0, 145.0, 1000.0, amount_precision_step=0.01)
    assert size == 2.0

def test_calculate_position_size_shibcoin():
    # step для SHIB = 1 (целое число)
    size = calculate_position_size(0.000025, 0.000024, 1000.0, amount_precision_step=1)
    # ИЗМЕНЕНО: round(10000000.0) == 10000000
    assert size == 10000000

def test_calculate_position_size_zero_balance():
    size = calculate_position_size(60000.0, 59000.0, 0.0, amount_precision_step=0.001)
    assert size == 0.0

def test_calculate_position_size_zero_price_diff():
    size = calculate_position_size(60000.0, 60000.0, 1000.0, amount_precision_step=0.001)
    assert size == 0.0
