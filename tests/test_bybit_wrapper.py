import pytest
from unittest.mock import AsyncMock, MagicMock
import ccxt.async_support as ccxt
from bybit_wrapper import AsyncBybitWrapper

@pytest.fixture
def mock_exchange():
    """Фикстура, создающая мок-объект для ccxt.exchange."""
    exchange = AsyncMock()
    exchange.load_markets.return_value = None
    exchange.set_sandbox_mode = MagicMock(return_value=None) # <-- MODIFY THIS LINE
    exchange.fetch_balance.return_value = {
        'USDT': {'free': 1000.0, 'used': 0.0, 'total': 1000.0}
    }
    exchange.create_order.return_value = {'id': '12345', 'status': 'open'}
    exchange.market.return_value = {
        'precision': {'amount': 3, 'price': 2}
    }
    return exchange


@pytest.mark.asyncio
async def test_init_and_get_balance(mock_exchange, mocker):
    """Тестирует успешную инициализацию и получение баланса."""
    # Подменяем реальный ccxt.bybit на наш мок
    mocker.patch('ccxt.async_support.bybit', return_value=mock_exchange)
    
    # Создаем экземпляр с фиктивными ключами
    wrapper = AsyncBybitWrapper(api_key="dummy", secret_key="dummy", testnet=True)
    await wrapper.init()
    balance = await wrapper.get_usdt_balance()
    await wrapper.close()

    assert balance == 1000.0
    mock_exchange.load_markets.assert_called_once()
    mock_exchange.fetch_balance.assert_called_once()


@pytest.mark.asyncio
async def test_create_order_success(mock_exchange, mocker):
    """Тестирует успешное создание ордера."""
    mocker.patch('ccxt.async_support.bybit', return_value=mock_exchange)
    mock_log = mocker.patch('bybit_wrapper.log_trade_execution')
    
    wrapper = AsyncBybitWrapper(api_key="dummy", secret_key="dummy", testnet=True)
    await wrapper.init()
    result = await wrapper.create_market_order_with_sl('BTC/USDT:USDT', 'buy', 0.01, 59000.0)
    await wrapper.close()

    assert result['id'] == '12345'
    mock_log.assert_called_once()


@pytest.mark.asyncio
async def test_create_order_insufficient_funds(mock_exchange, mocker):
    """Тестирует обработку ошибки нехватки средств."""
    error_message = "bybit-insufficient-balance-for-order-cost"
    mock_exchange.create_order.side_effect = ccxt.InsufficientFunds(error_message)
    mocker.patch('ccxt.async_support.bybit', return_value=mock_exchange)
    mock_log = mocker.patch('bybit_wrapper.log_trade_execution')

    wrapper = AsyncBybitWrapper(api_key="dummy", secret_key="dummy", testnet=True)
    await wrapper.init()
    result = await wrapper.create_market_order_with_sl('BTC/USDT:USDT', 'buy', 1.0, 59000.0)
    await wrapper.close()

    assert 'error' in result
    assert error_message in result['error']
    mock_log.assert_called_once()