import sqlite3
import os
from datetime import date
from functools import wraps
from fastapi import HTTPException

DATABASE_FILE = os.getenv("TRADE_DB", "trades.sqlite")
INITIAL_EQUITY = 1000.0

def get_db_connection():
    # This now uses the (potentially monkeypatched) module-level constant
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_pnl_table():
    """Creates the daily_pnl table if it doesn't exist."""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS daily_pnl (
            trade_date DATE PRIMARY KEY,
            realised_pnl REAL NOT NULL DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# REMOVED: The top-level call to initialize_pnl_table() was removed.

def check_daily_drawdown(max_loss_pct: float = 0.03):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            today = date.today()
            conn = get_db_connection()
            cursor = conn.cursor()
            
            current_equity = INITIAL_EQUITY
            max_loss_usd = current_equity * max_loss_pct

            cursor.execute("SELECT realised_pnl FROM daily_pnl WHERE trade_date = ?", (today,))
            result = cursor.fetchone()
            conn.close()

            realised_pnl = result['realised_pnl'] if result else 0.0

            if realised_pnl <= -max_loss_usd:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily loss limit of ${max_loss_usd:.2f} reached. Realised PnL: ${realised_pnl:.2f}. No new trades allowed."
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def update_pnl(pnl: float):
    """Updates the PnL for the current day."""
    today = date.today()
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO daily_pnl (trade_date, realised_pnl)
        VALUES (?, ?)
        ON CONFLICT(trade_date) DO UPDATE SET
        realised_pnl = realised_pnl + excluded.realised_pnl;
    ''', (today, pnl))
    conn.commit()
    conn.close()