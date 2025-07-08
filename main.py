from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import aiofiles

from spring_model import bounce_prob
from bybit_wrapper import AsyncBybitWrapper
from risk_sizer import calculate_position_size
from risk_controls import check_daily_drawdown
from trade_logger import log_signal, log_event

# --- Pydantic Models for API validation ---
class Signal(BaseModel):
    symbol: str
    side: str
    entry: float
    sl: float
    tp: float

# --- FastAPI App Initialization ---
app = FastAPI(title="LLM-Driven Trading Bot")
bybit_client = AsyncBybitWrapper(testnet=True)

@app.on_event("startup")
async def startup_event():
    """Initializes the Bybit client when the application starts."""
    await bybit_client.init()

@app.on_event("shutdown")
async def shutdown_event():
    """Closes the Bybit client connection when the application shuts down."""
    await bybit_client.close()

# --- API Endpoints ---
@app.post("/execute")
@check_daily_drawdown(max_loss_pct=0.03)
async def execute_trade(signal: Signal):
    """
    Main endpoint for receiving and processing a trading signal.
    """
    log_signal(signal.model_dump()) # <-- ИЗМЕНЕНО: .dict() -> .model_dump()

    # 1. Load data (placeholder)
    # TODO: ⚠ This CSV loading is temporary and will be replaced by a real-time data source (e.g., WebSocket).
    try:
        async with aiofiles.open('btc_1m.csv', mode='r') as f:
            content = await f.read()
        bars_df = pd.read_csv(pd.io.common.StringIO(content), names=['ts', 'open', 'high', 'low', 'close', 'volume']).tail(20)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Historical data file 'btc_1m.csv' not found.")

    # 2. Apply Spring Model Filter
    prob = bounce_prob(bars=bars_df, side=signal.side, price=signal.entry)

    # 3. Check probability threshold
    if prob < 0.5:
        reason = {"reason": "spring_filter_rejected", "prob": prob}
        log_event("TRADE_REJECTED", reason)
        raise HTTPException(status_code=403, detail=reason)
    
    # Convert symbol for ccxt, e.g., 'BTCUSDT' -> 'BTC/USDT:USDT'
    ccxt_symbol = f"{signal.symbol.replace('USDT', '')}/USDT:USDT"

    # 4. Get market precision for the symbol
    try:
        precision = bybit_client.get_market_precision(ccxt_symbol)
        amount_precision = int(precision['amount'])
    except Exception:
        raise HTTPException(status_code=404, detail=f"Market symbol '{ccxt_symbol}' not found or precision not available.")

    # 5. Calculate position size with correct precision
    equity = await bybit_client.get_usdt_balance()
    qty = calculate_position_size(
        entry_price=signal.entry,
        stop_loss_price=signal.sl,
        equity=equity,
        amount_precision=amount_precision  # Pass the required precision
    )
    
    if qty <= 0:
        reason = {"reason": "risk_sizer_returned_zero_qty", "calculated_qty": qty}
        log_event("TRADE_REJECTED", reason)
        raise HTTPException(status_code=400, detail=reason)

    # 6. Execute the order
    order = await bybit_client.create_market_order_with_sl(
        symbol=ccxt_symbol, 
        side='buy' if signal.side == 'long' else 'sell',
        amount=qty,
        stop_loss_price=signal.sl
    )

    if 'error' in order:
        raise HTTPException(status_code=500, detail={"reason": "order_placement_failed", "details": order})

    # 7. Success response
    return {"accepted": True, "qty": qty, "prob": prob, "order": order}