# file: db_setup.py
import sqlite3
from db_utils import get_db_connection

def setup_database():
    """
    Creates or updates all necessary tables and indexes in the DB.
    This script is idempotent and safe to run multiple times.
    """
    print("--- Starting Database Setup ---")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Table 1: Managed Trades (the heart of the system)
        print("1. Creating 'managed_trades' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS managed_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instruction_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('long', 'short')),
            status TEXT NOT NULL CHECK(status IN ('PENDING_ENTRY', 'ACTIVE', 'CLOSING', 'CLOSED')),
            
            entry_range_start REAL NOT NULL,
            entry_range_end REAL NOT NULL,
            initial_tps TEXT NOT NULL,
            
            avg_entry_price REAL,
            total_qty REAL NOT NULL,
            executed_qty REAL NOT NULL DEFAULT 0,
            
            initial_sl_price REAL NOT NULL,
            current_sl_price REAL NOT NULL,
            exchange_sl_order_id TEXT,
            
            -- CORRECTED COLUMN DEFINITION --
            move_sl_to_be_after_tp_index INTEGER, 
            
            remaining_tps TEXT NOT NULL,
            close_reason TEXT,
            realized_pnl REAL,
            
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)
        print("   ... 'managed_trades' table is ready.")

        # Table 2: Entry Orders
        print("2. Creating 'entry_orders' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS entry_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            exchange_order_id TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            FOREIGN KEY (trade_id) REFERENCES managed_trades (id)
        );
        """)
        print("   ... 'entry_orders' table is ready.")

        # Table 3: Live Prices
        print("3. Creating 'live_prices' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS live_prices (
            symbol TEXT PRIMARY KEY,
            mark_price REAL NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)
        print("   ... 'live_prices' table is ready.")

        # Table 4: Daily PnL for Risk Controls
        print("4. Creating 'daily_pnl' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_pnl (
            trade_date DATE PRIMARY KEY,
            realised_pnl REAL NOT NULL DEFAULT 0
        );
        """)
        print("   ... 'daily_pnl' table is ready.")
        
        # Table 5: General Event Log
        print("5. Creating 'trade_log' table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_log (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           timestamp_utc TEXT NOT NULL,
           event_type TEXT NOT NULL,
           -- CORRECTED COLUMN DEFINITION (NULLABLE) --
           payload_json TEXT 
        );
        """)
        print("   ... 'trade_log' table is ready.")

        # Indexes for performance
        print("6. Creating indexes for performance...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_managed_trades_status ON managed_trades(status);")
        # ... other indexes ...
        print("   ... Indexes are ready.")
        
        # Schema versioning
        print("7. Setting up schema version...")
        cursor.execute("CREATE TABLE IF NOT EXISTS db_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
        cursor.execute("INSERT OR IGNORE INTO db_meta (key, value) VALUES ('schema_version', '3');")
        print("   ... Schema version is set.")

        conn.commit()
        print("\n--- Database setup successfully completed! ---")

    except Exception as e:
        print(f"\n--- An error occurred during database setup: {e} ---")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()