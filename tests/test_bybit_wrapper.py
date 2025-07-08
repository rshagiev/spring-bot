# File: tests/test_bybit_wrapper.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)
import pytest
from unittest.mock import AsyncMock, MagicMock  # <-- ИЗМЕНЕНИЕ ЗДЕСЬ
import ccxt.async_support as ccxt
from bybit_wrapper import AsyncBybitWrapper

@pytest.fixture
def mock_bybit_client(mocker):
    mock_exchange = AsyncMock()
    mock_exchange.load_markets.return_value = None
    mock_exchange.fetch_balance.return_value = {
        'USDT': {'free': 1000.0}
    }
    mock_exchange.create_order.return_value = {'id': '123'}
    # set_sandbox_mode не является async, мокируем его как обычный метод
    mock_exchange.set_sandbox_mode = MagicMock()
    mocker.patch('ccxt.async_support.bybit', return_value=mock_exchange)
    return mock_exchange

@pytest.fixture(autouse=True)
def mock_keys(monkeypatch):
    monkeypatch.setenv("BYBIT_KEY", "dummy_key")
    monkeypatch.setenv("BYBIT_SECRET", "dummy_secret")

@pytest.mark.asyncio
async def test_init_and_get_balance(mock_bybit_client):
    wrapper = AsyncBybitWrapper(testnet=True)
    await wrapper.init()
    balance = await wrapper.get_usdt_balance()
    await wrapper.close()

    assert balance == 1000.0
    mock_bybit_client.load_markets.assert_called_once()
    mock_bybit_client.fetch_balance.assert_called_once()

@pytest.mark.asyncio
async def test_create_order_success(mock_bybit_client, mocker):
    mock_log = mocker.patch('bybit_wrapper.log_trade_execution')
    wrapper = AsyncBybitWrapper(testnet=True)
    await wrapper.init()
    result = await wrapper.create_market_order_with_sl('BTC/USDT:USDT', 'buy', 0.01, 59000.0)
    await wrapper.close()

    assert result['id'] == '123'
    mock_log.assert_called_once_with({'id': '123'})