# file: risk_controls.py
import sqlite3
import os
from datetime import date, datetime 
from functools import wraps
from fastapi import HTTPException

# --- CHANGE 1: Import the central DB connection utility ---
from db_utils import get_db_connection

# --- CHANGE 2: Remove the local get_db_connection() and initialize_pnl_table() functions ---
# They are no longer needed here.

INITIAL_EQUITY = 1000.0

def check_daily_drawdown(max_loss_pct: float = 0.03):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from db_utils import get_db_connection
            today = date.today()
            # This call now correctly uses the function from db_utils,
            # which is properly patched by your tests.
            conn = get_db_connection()
            cursor = conn.cursor()
            
            current_equity = INITIAL_EQUITY
            max_loss_usd = current_equity * max_loss_pct

            try:
                cursor.execute("SELECT realised_pnl FROM daily_pnl WHERE trade_date = ?", (today,))
                result = cursor.fetchone()
                realised_pnl = result['realised_pnl'] if result else 0.0
            except sqlite3.OperationalError as e:
                # Handle case where table might not exist in a faulty setup, but log it.
                print(f"Database error in check_daily_drawdown: {e}")
                realised_pnl = 0.0
            finally:
                conn.close()

            if realised_pnl <= -max_loss_usd:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily loss limit of ${max_loss_usd:.2f} reached. Realised PnL: ${realised_pnl:.2f}. No new trades allowed."
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# --- CHANGE 3: Modify update_pnl to accept a connection object ---
def update_pnl(conn: sqlite3.Connection, pnl: float):
    """Updates the PnL for the current day using the provided connection."""
    
    # --- НАША ОТЛАДОЧНАЯ ЛОВУШКА ---
    now = datetime.now().strftime("%H:%M:%S.%f")
    print(f"\nDEBUG_TRAP [{now}]: update_pnl CALLED! PNL = {pnl}\n")
    # ---------------------------------
    
    today = date.today()
    try:
        with conn:
            conn.execute('''
                INSERT INTO daily_pnl (trade_date, realised_pnl)
                VALUES (?, ?)
                ON CONFLICT(trade_date) DO UPDATE SET
                realised_pnl = realised_pnl + excluded.realised_pnl;
            ''', (today, pnl))
    except Exception as e:
        print(f"ERROR in update_pnl: {e}")