# File: tests/test_risk_sizer.py
import pytest
from risk_sizer import calculate_position_size

def test_calculate_position_size_btc():
    # 1% риск от 1000 USDT = 10 USDT
    # Разница в цене = 60000 - 59000 = 1000
    # Ожидаемый размер = 10 / 1000 = 0.01
    # Точность для BTC - 3 знака
    size = calculate_position_size(60000.0, 59000.0, 1000.0, amount_precision=3)
    assert size == 0.01

def test_calculate_position_size_altcoin():
    # 1% риск от 1000 USDT = 10 USDT
    # Разница в цене = 1.5 - 1.45 = 0.05
    # Ожидаемый размер = 10 / 0.05 = 200
    # Точность для альта (SOL, ADA) - 1 или 2 знака
    size = calculate_position_size(1.5, 1.45, 1000.0, amount_precision=2)
    assert size == 200.0

def test_calculate_position_size_shibcoin():
    # 1% риск от 1000 USDT = 10 USDT
    # Разница в цене = 0.000025 - 0.000024 = 0.000001
    # Ожидаемый размер = 10 / 0.000001 = 10,000,000
    # Точность для "щиткоинов" - 0 (целое число)
    size = calculate_position_size(0.000025, 0.000024, 1000.0, amount_precision=0)
    assert size == 10000000.0

def test_calculate_position_size_zero_balance():
    size = calculate_position_size(60000.0, 59000.0, 0.0, amount_precision=3)
    assert size == 0.0

def test_calculate_position_size_zero_price_diff():
    size = calculate_position_size(60000.0, 60000.0, 1000.0, amount_precision=3)
    assert size == 0.0