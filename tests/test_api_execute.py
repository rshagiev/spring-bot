# File: tests/test_api_execute.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
import os

from bybit_wrapper import AsyncBybitWrapper
import main
import risk_controls
import trade_logger

# --- Mocks ---
mock_bybit_wrapper = AsyncMock(spec=AsyncBybitWrapper)
mock_bybit_wrapper.get_usdt_balance.return_value = 1000.0
mock_bybit_wrapper.create_market_order_with_sl.return_value = {"id": "12345"}
mock_bybit_wrapper.get_market_precision.return_value = {"amount": 3, "price": 2}
main.bybit_client = mock_bybit_wrapper

client = TestClient(main.app)

# --- Fixtures ---
TEST_DB = "test_api.sqlite"

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, mocker):
    monkeypatch.setattr(risk_controls, "DATABASE_FILE", TEST_DB)
    monkeypatch.setattr(trade_logger, "DATABASE_FILE", TEST_DB)
    monkeypatch.setattr(trade_logger, "_db_instance", None)
    if os.path.exists(TEST_DB): os.remove(TEST_DB)
    risk_controls.initialize_pnl_table()

    with open('btc_1m.csv', 'w') as f:
        f.write("1,100,105,95,101,1000\n" * 25)

    mocker.patch('main.log_signal')
    mocker.patch('main.log_event')
    
    yield
    
    if os.path.exists(TEST_DB): os.remove(TEST_DB)

# --- Tests ---
def test_execute_trade_success(mocker): # <-- Добавляем mocker в аргументы
    # ИЗМЕНЕНО: Патчим bounce_prob там, где он используется
    mocker.patch('main.bounce_prob', return_value=0.7)

    signal = {"symbol": "BTCUSDT", "side": "long", "entry": 101.0, "sl": 100.0, "tp": 103.0}
    response = client.post("/execute", json=signal)
    
    assert response.status_code == 200, response.json()
    data = response.json()
    assert data['qty'] == 10.0

def test_execute_trade_rejected_by_spring_filter(mocker): # <-- Добавляем mocker в аргументы
    # ИЗМЕНЕНО: Патчим bounce_prob там, где он используется
    mocker.patch('main.bounce_prob', return_value=0.3)

    signal = {"symbol": "BTCUSDT", "side": "long", "entry": 101.0, "sl": 100.0, "tp": 103.0}
    response = client.post("/execute", json=signal)
    
    assert response.status_code == 403, response.json()
    data = response.json()['detail']
    assert data['reason'] == "spring_filter_rejected"