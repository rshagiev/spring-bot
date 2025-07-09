import pytest
from fastapi.testclient import TestClient
import os

# Импортируем app, моки будут применены через conftest
from main import app
client = TestClient(app)

# Эта фикстура теперь только мокирует логирование
@pytest.fixture(autouse=True)
def setup_common_mocks(mocker):
    """Общие моки для всех тестов в этом файле."""
    mocker.patch('main.log_signal')
    mocker.patch('main.log_event')
    yield

def test_execute_trade_calls_all_methods_correctly(mock_bybit_client_main):
    """
    Тестирует, что эндпоинт /execute корректно вызывает всю цепочку методов:
    1. get_market_precision
    2. get_usdt_balance
    3. set_margin_mode
    4. set_leverage
    5. create_market_order_with_sl
    """
    signal = {"symbol": "BTCUSDT", "side": "long", "entry": 53000, "sl": 52500, "tp": 54000}
    
    # Сбрасываем счетчики вызовов мока перед тестом
    mock_bybit_client_main.reset_mock()
    
    response = client.post("/execute", json=signal)
    
    # 1. Проверяем, что ответ успешный
    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["accepted"] is True
    assert data["order"]["id"] == "12345"

    # 2. Проверяем, что все нужные методы wrapper'а были вызваны, и именно в этом порядке
    call_order = [call[0] for call in mock_bybit_client_main.method_calls]
    expected_order = [
        'get_market_precision',
        'get_usdt_balance',
        'set_margin_mode',
        'set_leverage',
        'create_market_order_with_sl'
    ]
    assert call_order == expected_order

    # 3. Проверяем аргументы ключевых вызовов
    mock_bybit_client_main.get_market_precision.assert_called_once_with("BTC/USDT:USDT")
    mock_bybit_client_main.set_margin_mode.assert_called_once_with("BTC/USDT:USDT", "isolated")
    mock_bybit_client_main.set_leverage.assert_called_once_with("BTC/USDT:USDT", 10)
    mock_bybit_client_main.create_market_order_with_sl.assert_called_once()