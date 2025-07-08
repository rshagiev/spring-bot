# File: tests/test_trade_logger.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)
import pytest
import os
from datetime import datetime
import trade_logger

TEST_DB = "test_log_final.sqlite"

@pytest.fixture(autouse=True)
def setup_teardown_db(monkeypatch):
    monkeypatch.setattr(trade_logger, "DATABASE_FILE", TEST_DB)
    monkeypatch.setattr(trade_logger, "_db_instance", None)
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_log_signal():
    signal_data = {
        'pair': 'BTC/USDT:USDT',
        'side': 'long',
    }
    trade_logger.log_signal(signal_data)
    db = trade_logger.get_db()
    log_entry = list(db["trade_log"].rows)[0]
    assert log_entry["event_type"] == "SIGNAL_RECEIVED"
    assert log_entry["pair"] == "BTC/USDT:USDT"

def test_log_successful_execution():
    order_data = {
        'id': '123456789', 'cid': 'my_client_id_001', 'symbol': 'BTC/USDT:USDT',
        'side': 'buy', 'amount': 0.001, 'price': 60100.0,
        'status': 'open', 'error': None
    }
    trade_logger.log_trade_execution(order_data)

    db = trade_logger.get_db()
    log_entry = list(db["trade_log"].rows)[0]

    assert log_entry["event_type"] == "ORDER_PLACED"
    # ИЗМЕНЕНО: Проверяем ключ 'id', который приходит от CCXT и записывается в лог
    assert log_entry["id"] == '123456789' 
    assert log_entry["error"] is None