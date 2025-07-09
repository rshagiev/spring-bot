# file: tests/test_position_manager.py
import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

# Импортируем тестируемую функцию
from position_manager import reconcile_and_manage
# Импортируем утилиту для получения соединения
from db_utils import get_db_connection

# --- Вспомогательная функция для создания тестовых сделок в БД ---

def create_test_trade_in_db(status='PENDING_ENTRY', avg_price=None, sl_price=85.0, sl_order_id=None, remaining_tps='[110, 120]', move_sl_idx=1, total_qty=1.0):
    """
    Создает запись о сделке в БД и возвращает ее ID.
    Эта функция сама управляет своим соединением с БД.
    """
    conn = get_db_connection()
    try:
        now_utc_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        # Добавляем все необходимые поля, чтобы избежать ошибок
        initial_tps_json = json.dumps([110, 120])
        remaining_tps_json = remaining_tps if isinstance(remaining_tps, str) else json.dumps(remaining_tps)
        
        cursor.execute("""
            INSERT INTO managed_trades (
                instruction_id, symbol, side, status, entry_range_start, entry_range_end,
                total_qty, avg_entry_price, initial_sl_price, current_sl_price, exchange_sl_order_id,
                initial_tps, remaining_tps, move_sl_to_be_after_tp_index, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'sig1', 'BTCUSDT', 'long', status, 90.0, 100.0, total_qty, avg_price, 85.0, sl_price,
            sl_order_id, initial_tps_json, remaining_tps_json, move_sl_idx, now_utc_iso, now_utc_iso
        ))
        trade_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return trade_id

# === Группа тестов для функции reconcile_and_manage ===

@pytest.mark.asyncio
async def test_reconcile_pending_to_active(mock_bybit_client):
    """
    Тестирует переход сделки из PENDING_ENTRY в ACTIVE.
    """
    # 1. Подготовка: создаем сделку и ордер в чистой БД.
    # Фикстура `setup_for_every_test` гарантирует, что БД чиста.
    trade_id = create_test_trade_in_db(status='PENDING_ENTRY')
    
    conn = get_db_connection()
    try:
        # Используем уникальный ID для ордера, который не будет конфликтовать
        conn.execute("INSERT INTO entry_orders (trade_id, exchange_order_id, status) VALUES (?, ?, 'open')", (trade_id, f"entry_order_{trade_id}"))
        conn.commit()
        trade_before = dict(conn.execute("SELECT * FROM managed_trades WHERE id = ?", (trade_id,)).fetchone())
    finally:
        conn.close()

    # 2. Симуляция: "на бирже" появилась открытая позиция
    live_position_mock = {
        'symbol': 'BTCUSDT',
        'entryPrice': '95.5',
        'contracts': '0.5',
        'markPrice': '96.0'
    }
    
    # 3. Действие: вызываем тестируемую функцию
    await reconcile_and_manage(trade_before, live_position_mock, mock_bybit_client)

    # 4. Проверка результата
    conn = get_db_connection()
    try:
        trade_after = dict(conn.execute("SELECT * FROM managed_trades WHERE id = ?", (trade_id,)).fetchone())
    finally:
        conn.close()
    
    assert trade_after['status'] == 'ACTIVE'
    assert trade_after['avg_entry_price'] == 95.5
    assert trade_after['executed_qty'] == 0.5
    # mock_bybit_client из conftest.py возвращает 'stop_loss_order_1'
    assert trade_after['exchange_sl_order_id'] == 'stop_loss_order_1' 
    mock_bybit_client.cancel_order.assert_called_once_with(f"entry_order_{trade_id}", 'BTCUSDT')

@pytest.mark.asyncio
async def test_reconcile_active_to_closed(mock_bybit_client):
    """
    Тестирует переход сделки из ACTIVE в CLOSED.
    """
    trade_id = create_test_trade_in_db(status='ACTIVE', avg_price=95.0)
    
    conn = get_db_connection()
    trade_before = dict(conn.execute("SELECT * FROM managed_trades WHERE id = ?", (trade_id,)).fetchone())
    conn.close()

    live_position_mock = None
    
    await reconcile_and_manage(trade_before, live_position_mock, mock_bybit_client)

    conn = get_db_connection()
    trade_after = dict(conn.execute("SELECT * FROM managed_trades WHERE id = ?", (trade_id,)).fetchone())
    conn.close()

    # Теперь эта проверка должна пройти, так как get_realized_pnl не вызовет ошибку
    assert trade_after['status'] == 'CLOSED'
    assert trade_after['close_reason'] is not None

@pytest.mark.asyncio
async def test_reconcile_moves_sl_to_breakeven(mock_bybit_client):
    """
    Тестирует перемещение стоп-лосса в безубыток.
    """
    # --- ИСПРАВЛЕНИЕ ОШИБКИ ---
    # Заменяем pytest.AsyncMock на AsyncMock из unittest.mock
    mock_bybit_client.edit_order = AsyncMock(return_value={"id": "sl_edited_456"})
    # ---------------------------
    
    trade_id = create_test_trade_in_db(
        status='ACTIVE', avg_price=95.0, sl_price=85.0,
        sl_order_id='sl_initial_123', remaining_tps='[120]', move_sl_idx=1
    )
    
    conn = get_db_connection()
    trade_before = dict(conn.execute("SELECT * FROM managed_trades WHERE id = ?", (trade_id,)).fetchone())
    conn.close()

    live_position_mock = {
        'symbol': 'BTCUSDT', 'entryPrice': '95.0',
        'contracts': '0.5', 'markPrice': '115.0'
    }
    
    await reconcile_and_manage(trade_before, live_position_mock, mock_bybit_client)

    conn = get_db_connection()
    trade_after = dict(conn.execute("SELECT * FROM managed_trades WHERE id = ?", (trade_id,)).fetchone())
    conn.close()

    assert trade_after['current_sl_price'] == trade_after['avg_entry_price']
    
    mock_bybit_client.edit_order.assert_called_once_with(
        'sl_initial_123', 'BTCUSDT', 95.0
    )