# File: bybit_wrapper.py
import ccxt.async_support as ccxt
import os
from trade_logger import log_trade_execution

class AsyncBybitWrapper:
    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.exchange = None

    async def init(self):
        api_key = os.getenv("BYBIT_KEY")
        secret = os.getenv("BYBIT_SECRET")
        if not api_key or not secret:
            raise ValueError("BYBIT_KEY and BYBIT_SECRET must be set.")
        self.exchange = ccxt.bybit({'apiKey': api_key, 'secret': secret, 'options': {'defaultType': 'swap'}})
        if self.testnet:
            self.exchange.set_sandbox_mode(True)
        try:
            await self.exchange.load_markets()
            print(f"Successfully connected to Bybit. Sandbox: {self.testnet}")
        except Exception as e:
            await self.close()
            raise

    async def close(self):
        if self.exchange:
            await self.exchange.close()

    def get_market_precision(self, symbol: str) -> dict:
        market = self.exchange.market(symbol)
        return {
            'price': market['precision']['price'],
            'amount': market['precision']['amount']
        }

    async def get_usdt_balance(self) -> float:
        try:
            balance = await self.exchange.fetch_balance()
            return float(balance.get('USDT', {}).get('free', 0.0))
        except Exception as e:
            return 0.0

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