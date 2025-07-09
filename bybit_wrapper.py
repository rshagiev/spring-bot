import ccxt.async_support as ccxt
import os
from trade_logger import log_trade_execution, log_event

class AsyncBybitWrapper:
    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        if not api_key or not secret_key:
            raise ValueError("API key and secret must be provided.")
        
        self.testnet = testnet
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': secret_key,
            'options': {'defaultType': 'swap'},
        })
        if self.testnet:
            self.exchange.set_sandbox_mode(True)

    async def init(self):
        try:
            await self.exchange.load_markets()
            print(f"Successfully connected to Bybit. Sandbox mode: {self.testnet}")
        except Exception as e:
            await self.close()
            raise

    async def close(self):
        if self.exchange:
            await self.exchange.close()

    # --- ДОБАВЬТЕ ЭТИ ДВА МЕТОДА ---
    async def set_leverage(self, symbol: str, leverage: int):
        """Устанавливает кредитное плечо для указанного символа."""
        try:
            await self.exchange.set_leverage(leverage, symbol)
            log_event("LEVERAGE_SET", {"symbol": symbol, "leverage": leverage})
        except Exception as e:
            log_event("LEVERAGE_ERROR", {"symbol": symbol, "error": str(e)})
            # Можно не кидать исключение, если биржа позволяет торговать и так
            print(f"Warning: Failed to set leverage for {symbol}: {e}")

    async def set_margin_mode(self, symbol: str, margin_mode: str):
        """Устанавливает режим маржи ('cross' или 'isolated')."""
        try:
            unified_symbol = symbol.split(':')[0]
            await self.exchange.set_margin_mode(margin_mode, unified_symbol, params={'settleCoin': 'USDT'})
            log_event("MARGIN_MODE_SET", {"symbol": symbol, "mode": margin_mode})
        except Exception as e:
            log_event("MARGIN_MODE_ERROR", {"symbol": symbol, "error": str(e)})
            print(f"Warning: Failed to set margin mode for {symbol}: {e}")
    # ------------------------------------

    def get_market_precision(self, symbol: str) -> dict:
        try:
            market = self.exchange.market(symbol)
            return {'price': market['precision']['price'], 'amount': market['precision']['amount']}
        except (ccxt.BadSymbol, KeyError):
            return None

    async def get_usdt_balance(self) -> float:
        try:
            balance = await self.exchange.fetch_balance()
            return float(balance.get('USDT', {}).get('total', 0.0))
        except Exception as e:
            return 0.0

    async def fetch_open_positions(self) -> dict:
        try:
            positions = await self.exchange.fetch_positions()
            return {p['info']['symbol']: p for p in positions if float(p.get('contracts', 0)) != 0}
        except Exception:
            return {}
    
    # --- ДОБАВЬТЕ ЭТОТ МЕТОД ---
    async def fetch_ticker_price(self, symbol: str) -> float:
        """Получает последнюю цену для тикера."""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            print(f"Error fetching ticker for {symbol}: {e}")
            return 0.0
    # ---------------------------

    async def create_market_order_with_sl(self, symbol: str, side: str, amount: float, stop_loss_price: float) -> dict:
        params = {'stopLoss': stop_loss_price}
        try:
            order = await self.exchange.create_order(symbol, 'market', side, amount, params=params)
            log_trade_execution(order)
            return order
        except Exception as e:
            error_payload = {'symbol': symbol, 'error': str(e)}
            log_trade_execution(error_payload)
            return error_payload
    
    async def create_order(self, symbol: str, type: str, side: str, amount: float, price: float = None, params={}) -> dict:
        """Универсальный метод для создания ордеров."""
        try:
            order = await self.exchange.create_order(symbol, type, side, amount, price, params)
            log_trade_execution(order)
            return order
        except Exception as e:
            error_payload = {'symbol': symbol, 'type': type, 'side': side, 'error': str(e)}
            log_trade_execution(error_payload)
            raise e
        
    async def create_limit_order(self, symbol: str, side: str, amount: float, price: float, params={}) -> dict:
        """Создает лимитный ордер."""
        try:
            order = await self.exchange.create_limit_order(symbol, side, amount, price, params=params)
            log_trade_execution(order)
            return order
        except Exception as e:
            error_payload = {'symbol': symbol, 'side': side, 'amount': amount, 'price': price, 'error': str(e)}
            log_trade_execution(error_payload)
            raise  # Перебрасываем исключение, чтобы вызывающий код мог его обработать

    async def edit_order(self, order_id: str, symbol: str, new_price: float) -> dict:
        """Редактирует цену существующего ордера (обычно для SL/TP)."""
        try:
            order = await self.exchange.edit_order(order_id, symbol, params={'triggerPrice': new_price})
            log_event("ORDER_EDITED", order)
            return order
        except Exception as e:
            error_payload = {'order_id': order_id, 'symbol': symbol, 'new_price': new_price, 'error': str(e)}
            log_event("ORDER_EDIT_FAILED", error_payload)
            raise
    
    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Отменяет ордер."""
        try:
            response = await self.exchange.cancel_order(order_id, symbol)
            log_event("ORDER_CANCELLED", response)
            return response
        except Exception as e:
            error_payload = {'order_id': order_id, 'symbol': symbol, 'error': str(e)}
            log_event("ORDER_CANCEL_FAILED", error_payload)
            # Не перебрасываем исключение, т.к. ордер мог уже быть исполнен/отменен
            return error_payload

    async def fetch_my_trades(self, symbol: str, limit: int = 20) -> list:
        """Получает историю последних сделок пользователя."""
        if self.exchange.has['fetchMyTrades']:
            return await self.exchange.fetch_my_trades(symbol, limit=limit)
        return []