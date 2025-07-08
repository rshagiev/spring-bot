import sqlite_utils
import os
from datetime import datetime, timezone

DATABASE_FILE = os.getenv("TRADE_DB", "trades.sqlite")

# Глобальный объект для хранения единственного экземпляра подключения
_db_instance = None

def get_db():
    """
    Возвращает единственный экземпляр подключения к базе данных (синглтон).
    Это повышает производительность и безопасность в многопоточной среде.
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = sqlite_utils.Database(DATABASE_FILE)
    return _db_instance

def log_event(event_type: str, payload: dict):
    """
    Записывает событие в таблицу 'trade_log'.
    """
    db = get_db()
    # pk="id" убран. sqlite-utils будет использовать стандартный rowid.
    log_table = db.table("trade_log")
    
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
    }
    record.update(payload)
    
    log_table.insert(record, alter=True)
    print(f"[LOG] Event '{event_type}': {payload}")

def log_signal(signal: dict):
    """Логирует входящий торговый сигнал."""
    log_event("SIGNAL_RECEIVED", payload=signal)

def log_trade_execution(order_result: dict):
    """Логирует результат размещения ордера на бирже."""
    payload = {
        "client_order_id": order_result.get('cid'),
        "exchange_order_id": order_result.get('id'),
        "symbol": order_result.get('symbol'),
        "side": order_result.get('side'),
        "amount": order_result.get('amount'),
        "price": order_result.get('price'),
        "status": order_result.get('status'),
        "error": order_result.get('error')
    }
    event_type = "ORDER_FAILED" if payload['error'] else "ORDER_PLACED"
    log_event(event_type, payload=payload)

def log_trade_execution(order_result: dict):
    """Логирует результат размещения ордера на бирже."""
    # Создаем копию, чтобы не изменять оригинальный объект от ccxt
    payload = order_result.copy()
    event_type = "ORDER_FAILED" if payload.get('error') else "ORDER_PLACED"
    log_event(event_type, payload=payload)

def log_signal(signal: dict):
    """Логирует входящий торговый сигнал."""
    log_event("SIGNAL_RECEIVED", payload=signal)