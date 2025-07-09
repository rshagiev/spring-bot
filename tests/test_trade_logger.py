# file: tests/test_trade_logger.py
import pytest
import json

# Импортируем тестируемые функции
from trade_logger import log_signal, log_trade_execution, log_event
from db_utils import get_db_connection

# Эта строка применит фикстуру clean_db ко всем тестам в файле
pytestmark = pytest.mark.usefixtures("setup_for_every_test")

# Добавляем фикстуру db_conn в аргументы теста
def test_log_signal_creates_correct_record(): # REMOVE db_conn
    """
    Tests that log_signal correctly creates a record in the DB.
    """
    signal_data = {'symbol': 'BTCUSDT', 'side': 'long'}
    log_signal(signal_data)

    conn = get_db_connection()
    try:
        log_entry = conn.execute("SELECT * FROM trade_log WHERE event_type = 'SIGNAL_RECEIVED'").fetchone()
    finally:
        conn.close()

    assert log_entry is not None
    assert log_entry['event_type'] == 'SIGNAL_RECEIVED'
    payload = json.loads(log_entry['payload_json'])
    assert payload['symbol'] == 'BTCUSDT'


def test_log_successful_trade_execution(): # REMOVE db_conn
    """
    Tests logging of a successful order placement.
    """
    order_data = {'id': '123', 'error': None}
    log_trade_execution(order_data)

    conn = get_db_connection()
    try:
        log_entry = conn.execute("SELECT * FROM trade_log WHERE event_type = 'ORDER_PLACED'").fetchone()
    finally:
        conn.close()

    assert log_entry is not None
    assert log_entry['event_type'] == 'ORDER_PLACED'


def test_log_failed_trade_execution(): # REMOVE db_conn
    """
    Tests logging of a failed order placement.
    """
    order_data = {'error': 'InsufficientFunds'}
    log_trade_execution(order_data)

    conn = get_db_connection()
    try:
        log_entry = conn.execute("SELECT * FROM trade_log WHERE event_type = 'ORDER_FAILED'").fetchone()
    finally:
        conn.close()

    assert log_entry is not None
    assert log_entry['event_type'] == 'ORDER_FAILED'


def test_log_event_generic(): # REMOVE db_conn
    """Tests the generic log_event function."""
    event_type = "CUSTOM_TEST_EVENT"
    payload_data = {"key": "value"}
    log_event(event_type, payload_data)

    conn = get_db_connection()
    try:
        log_entry = conn.execute("SELECT * FROM trade_log WHERE event_type = ?", (event_type,)).fetchone()
    finally:
        conn.close()

    assert log_entry is not None
    payload = json.loads(log_entry['payload_json'])
    assert payload['key'] == "value"