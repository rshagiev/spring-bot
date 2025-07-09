# file: db_utils.py
import sqlite3
import json
from datetime import datetime, timezone
import os

# Путь к БД теперь берется из env-переменной для гибкости и тестирования
# Фикстура в conftest.py будет подменять эту переменную во время тестов.
# DATABASE_FILE = os.getenv("DATABASE_FILE", "trades.sqlite") # <-- DELETE THIS LINE

def get_db_connection() -> sqlite3.Connection:
    """
    Возвращает НОВОЕ соединение с SQLite с настройками для production.
    """
    # ADD THIS LINE to read the env var on every call
    db_file = os.getenv("DATABASE_FILE", "trades.sqlite")

    # timeout=30 (в секундах) автоматически установит busy_timeout
    # check_same_thread=False важно для FastAPI, но требует аккуратного управления транзакциями.
    # UPDATE THIS LINE to use the local variable
    conn = sqlite3.connect(db_file, timeout=30, check_same_thread=False)
    # WAL-режим для безопасной конкурентной работы
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def create_managed_trade(instruction: dict, total_qty: float) -> int:
    """
    Создает запись о новой сделке в таблице managed_trades.
    Эта функция сама управляет своим соединением с БД, чтобы быть потоко-безопасной.
    """
    conn = get_db_connection()
    try:
        now_utc = datetime.now(timezone.utc).isoformat(timespec='microseconds')
        
        # Используем `with conn:` для автоматического коммита или отката транзакции
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO managed_trades (
                    instruction_id, symbol, side, status, entry_range_start, entry_range_end,
                    total_qty, initial_sl_price, current_sl_price, initial_tps, remaining_tps,
                    move_sl_to_be_after_tp_index, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instruction.get('signal_id', 'unknown'), 
                    instruction.get('symbol', 'BTCUSDT'), 
                    instruction['side'], 
                    'PENDING_ENTRY',
                    instruction['entry_start'], 
                    instruction['entry_end'], 
                    total_qty,
                    instruction['stop_loss'], 
                    instruction['stop_loss'],
                    json.dumps(instruction['take_profits']), 
                    json.dumps(instruction['take_profits']),
                    instruction.get('move_sl_to_be_after_tp_index', 1),
                    now_utc, 
                    now_utc
                )
            )
            trade_id = cursor.lastrowid
    finally:
        # Гарантированно закрываем соединение
        if conn:
            conn.close()
            
    return trade_id