# File: tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_bybit_client_main(monkeypatch):
    mock_client = AsyncMock()
    mock_client.get_usdt_balance.return_value = 1000.0
    mock_client.create_market_order_with_sl.return_value = {"id": "12345"}
    
    # Явно указываем, что этот метод не async
    mock_client.set_sandbox_mode = MagicMock()
    
    # ИЗМЕНЕНО: get_market_precision теперь синхронный мок
    mock_client.get_market_precision = MagicMock(
        return_value={"amount": 0.001, "price": 0.01}
    )
    
    mock_client.fetch_open_positions.return_value = {
        'BTCUSDT': {'symbol': 'BTCUSDT', 'contracts': 1.0}
    }
    
    monkeypatch.setattr('main.bybit_client', mock_client)
    
    return mock_client