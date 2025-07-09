from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import time
import os
from dotenv import load_dotenv

# --- Шаг 1: Явно загружаем переменные из .env файла ---
load_dotenv()
MAX_ENTRY_DEVIATION_PCT = 0.005  # Максимальное отклонение цены входа в процентах (0.5%)

# --- Шаг 2: Импортируем наши модули ПОСЛЕ загрузки .env ---
from bybit_wrapper import AsyncBybitWrapper
from risk_sizer import calculate_position_size
from risk_controls import check_daily_drawdown, initialize_pnl_table
from trade_logger import log_signal, log_event

# --- Pydantic Models for API validation ---
class Signal(BaseModel):
    symbol: str
    side: str
    entry: float
    sl: float
    tp: float

# --- FastAPI App Initialization ---
API_KEY = os.getenv("BYBIT_KEY")
API_SECRET = os.getenv("BYBIT_SECRET")

if not API_KEY or not API_SECRET:
    print("FATAL ERROR: BYBIT_KEY and/or BYBIT_SECRET not found. Please check your .env file.")
    exit()

app = FastAPI(title="LLM-Driven Trading Bot", version="0.2.0")
bybit_client = AsyncBybitWrapper(api_key=API_KEY, secret_key=API_SECRET, testnet=True)


@app.on_event("startup")
async def startup_event():
    """Initializes services when the application starts."""
    initialize_pnl_table()
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
    Spring Model filter is DISABLED for this version.
    """
    log_signal(signal.model_dump())
    
    # Конвертируем символ для ccxt, e.g., 'BTCUSDT' -> 'BTC/USDT:USDT'
    ccxt_symbol = f"{signal.symbol.replace('USDT', '')}/USDT:USDT"

    # --- НОВЫЙ ШАГ: ПРОВЕРКА ЦЕНЫ ВХОДА ---
    current_price = await bybit_client.fetch_ticker_price(ccxt_symbol)
    if current_price == 0:
        reason = {"reason": "failed_to_fetch_current_price"}
        log_event("TRADE_REJECTED", reason)
        raise HTTPException(status_code=503, detail=reason)

    deviation = abs(current_price - signal.entry) / signal.entry
    if deviation > MAX_ENTRY_DEVIATION_PCT:
        reason = {
            "reason": "price_deviation_too_high",
            "current_price": current_price,
            "signal_entry": signal.entry,
            "deviation_pct": deviation * 100
        }
        log_event("TRADE_REJECTED", reason)
        raise HTTPException(status_code=400, detail=reason)
    # ------------------------------------

    # Шаг 1: Получаем точность для символа
    try:
        precision = bybit_client.get_market_precision(ccxt_symbol)
        if precision is None:
            raise ValueError(f"Precision info not found for {ccxt_symbol}")
        amount_precision_step = float(precision['amount'])
    except Exception as e:
        log_event("TRADE_REJECTED", {"reason": "precision_error", "details": str(e)})
        raise HTTPException(status_code=404, detail=f"Market symbol '{ccxt_symbol}' not found or precision not available: {e}")

    # Шаг 2: Расчет размера позиции
    equity = await bybit_client.get_usdt_balance()
    qty = calculate_position_size(
        entry_price=signal.entry,
        stop_loss_price=signal.sl,
        equity=equity,
        amount_precision_step=amount_precision_step
    )
    
    if qty <= 0:
        reason = {"reason": "risk_sizer_returned_zero_qty", "calculated_qty": qty, "equity": equity}
        log_event("TRADE_REJECTED", reason)
        raise HTTPException(status_code=400, detail=reason)

    # Шаг 3: Установка параметров риска
    await bybit_client.set_margin_mode(ccxt_symbol, 'isolated')
    await bybit_client.set_leverage(ccxt_symbol, 10)

    # Шаг 4: Исполнение ордера
    order = await bybit_client.create_market_order_with_sl(
        symbol=ccxt_symbol, 
        side='buy' if signal.side == 'long' else 'sell',
        amount=qty,
        stop_loss_price=signal.sl
    )

    if 'error' in order:
        # Ошибка уже залогирована внутри wrapper'а
        raise HTTPException(status_code=500, detail={"reason": "order_placement_failed", "details": order})

    # Шаг 5: Успешный ответ
    # `prob` возвращаем как -1, чтобы обозначить, что фильтр был отключен
    return {"accepted": True, "qty": qty, "prob": -1, "order": order}

# --- Utility Endpoints ---
@app.get("/ping")
async def ping():
    return {"status": "ok", "timestamp": time.time()}

@app.get("/open_positions", response_model=Dict[str, Any])
async def get_open_positions():
    try:
        return await bybit_client.fetch_open_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': 'bybit-fetch_failed', 'details': str(e)})