# file: trade_logger.py
import json
from datetime import datetime, timezone

# Импортируем наш унифицированный коннектор к БД
from db_utils import get_db_connection

def log_event(event_type: str, payload: dict):
    """
    Универсальная функция для логирования любого события в системе.
    Записывает событие в таблицу 'trade_log'.

    Args:
        event_type (str): Тип события (например, 'SIGNAL_RECEIVED', 'ORDER_PLACED').
        payload (dict): Словарь с дополнительными данными о событии.
    """
    try:
        conn = get_db_connection()
        
        # Преобразуем все значения в payload в строки, чтобы избежать ошибок сериализации
        # сложных объектов (например, Decimal) и обеспечить консистентность.
        serializable_payload = {k: str(v) for k, v in payload.items()}
        payload_str = json.dumps(serializable_payload)

        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec='microseconds'),
            "event_type": event_type,
            "payload_json": payload_str
        }
        
        # Используем `with conn:` для автоматического коммита или отката транзакции
        with conn:
            conn.execute(
                "INSERT INTO trade_log (timestamp_utc, event_type, payload_json) VALUES (:timestamp_utc, :event_type, :payload_json)",
                record
            )
        
        print(f"[LOG] Event: {event_type} | Payload: {payload}")

    except Exception as e:
        # Критично важно не "уронить" приложение, если логирование не удалось.
        # Просто выводим ошибку в консоль.
        print(f"[LOGGING_ERROR] Failed to log event '{event_type}'. Error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()


def log_signal(signal: dict):
    """
    Специализированная функция-хелпер для логирования входящего торгового сигнала.
    """
    log_event("SIGNAL_RECEIVED", payload=signal)


def log_trade_execution(order_result: dict):
    """
    Специализированная функция-хелпер для логирования результата размещения ордера.
    Автоматически определяет тип события (успех/неудача) по наличию ключа 'error'.
    """
    # Создаем копию, чтобы не изменять оригинальный объект, который может еще использоваться
    payload = order_result.copy()
    
    # Определяем тип события
    # Если в результате есть ключ 'error' и он не None/пустой, считаем это ошибкой
    if payload.get('error'):
        event_type = "ORDER_FAILED"
    else:
        event_type = "ORDER_PLACED"
        
    log_event(event_type, payload=payload)