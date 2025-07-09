# file: main.py
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from dotenv import load_dotenv
import sqlite3

load_dotenv()

from bybit_wrapper import AsyncBybitWrapper
from risk_sizer import calculate_position_size
from risk_controls import check_daily_drawdown
from trade_logger import log_event
from signal_parser import parse_pentagon_signal
from db_utils import get_db_connection, create_managed_trade 
from position_manager import position_manager_loop, place_entry_grid
from models import TradeInstruction

API_KEY = os.getenv("BYBIT_KEY")
API_SECRET = os.getenv("BYBIT_SECRET")
if not API_KEY or not API_SECRET:
    raise RuntimeError("BYBIT_KEY and BYBIT_SECRET must be set in .env file")

bybit_client = AsyncBybitWrapper(api_key=API_KEY, secret_key=API_SECRET, testnet=True)
background_tasks = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bybit_client.init()
    manager_task = asyncio.create_task(position_manager_loop(bybit_client))
    background_tasks.add(manager_task)
    manager_task.add_done_callback(background_tasks.discard)
    log_event("APP_STARTUP", {"message": "Position manager started."})
    
    yield
    
    log_event("APP_SHUTDOWN", {"message": "Cancelling background tasks."})
    for task in list(background_tasks): # Iterate over a copy
        task.cancel()
    await bybit_client.close()
    log_event("APP_SHUTDOWN_COMPLETE", {"message": "Bybit client closed."})

app = FastAPI(title="Stateful Trading Bot", version="1.0.0", lifespan=lifespan)

def get_db():
    db = get_db_connection()
    try:
        yield db
    finally:
        db.close()

@app.post("/process_signal", status_code=202)
@check_daily_drawdown(max_loss_pct=0.03) 
async def process_signal(raw_text: str, db: sqlite3.Connection = Depends(get_db)): 
    instruction = parse_pentagon_signal(raw_text)
    if not instruction:
        raise HTTPException(status_code=400, detail="Signal parsing failed.")
    
    log_event("INSTRUCTION_PARSED", instruction.model_dump())

    equity = await bybit_client.get_usdt_balance()
    precision = bybit_client.get_market_precision(instruction.symbol)
    if not precision or 'amount' not in precision:
        raise HTTPException(status_code=500, detail="Could not get precision for symbol {instruction.symbol}")

    risk_entry_price = instruction.entry_end if instruction.side == 'short' else instruction.entry_start
    total_qty = calculate_position_size(
        entry_price=risk_entry_price, stop_loss_price=instruction.stop_loss,
        equity=equity, amount_precision_step=precision['amount'],
        risk_pct=instruction.risk_pct
    )
    final_qty = total_qty * instruction.size_fraction
    if final_qty <= 0:
        raise HTTPException(status_code=400, detail="Calculated position size is zero.")

    trade_id = create_managed_trade(instruction.model_dump(), final_qty) 
    log_event("TRADE_CREATED_IN_DB", {"trade_id": trade_id, "qty": final_qty})

    task = asyncio.create_task(
        place_entry_grid(trade_id, final_qty, instruction.model_dump(), bybit_client)
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

    return {"status": "accepted", "trade_id": trade_id}