# file: tests/test_risk_controls.py
import pytest
import numpy as np
from datetime import date
from fastapi import HTTPException

# Импортируем тестируемые функции
from risk_controls import check_daily_drawdown, update_pnl
# Импортируем утилиту для получения соединения
from db_utils import get_db_connection

# Вспомогательная функция для тестирования декоратора
@check_daily_drawdown(max_loss_pct=0.03)
async def dummy_protected_function():
    return {"status": "allowed"}

# ==================== ДИАГНОСТИЧЕСКИЕ ТЕСТЫ ====================
def test_initial_state_is_clean():
    """
    Этот тест должен выполняться ПЕРВЫМ.
    Он проверяет, что таблица daily_pnl пуста в начале.
    """
    print("\n[DIAGNOSTIC] Running test_initial_state_is_clean...")
    conn = get_db_connection()
    try:
        pnl_record = conn.execute("SELECT * FROM daily_pnl").fetchone()
    finally:
        conn.close()
    
    assert pnl_record is None, "ДИАГНОСТИКА: Таблица daily_pnl НЕ пуста в начале!"

# === Группа тестов для декоратора check_daily_drawdown ===

@pytest.mark.asyncio
async def test_dd_allows_when_no_pnl():
    """Проверяет: разрешает вход, если PnL за сегодня еще нет."""
    # БД чистая благодаря фикстуре, поэтому PnL = 0
    response = await dummy_protected_function()
    assert response == {"status": "allowed"}

@pytest.mark.asyncio
async def test_dd_allows_when_within_limit():
    """Проверяет: разрешает вход, если убыток в пределах лимита."""
    conn = get_db_connection()
    try:
        update_pnl(conn, -10.0) # Записываем PnL = -10
    finally:
        conn.close()
    
    # dummy_protected_function увидит PnL = -10.0, что меньше лимита
    response = await dummy_protected_function()
    assert response == {"status": "allowed"}

@pytest.mark.asyncio
async def test_dd_rejects_when_at_limit():
    """Проверяет: блокирует вход, если убыток равен лимиту."""
    conn = get_db_connection()
    try:
        update_pnl(conn, -30.0) # Записываем PnL = -30 (равен лимиту)
    finally:
        conn.close()
        
    with pytest.raises(HTTPException) as exc_info:
        await dummy_protected_function()
    assert exc_info.value.status_code == 429

@pytest.mark.asyncio
async def test_dd_rejects_when_exceeds_limit():
    """Проверяет: блокирует вход, если убыток превышает лимит."""
    conn = get_db_connection()
    try:
        update_pnl(conn, -35.0) # Записываем PnL = -35
    finally:
        conn.close()
        
    with pytest.raises(HTTPException) as exc_info:
        await dummy_protected_function()
        
    assert exc_info.value.status_code == 429
    # Проверяем, что в сообщении об ошибке указан правильный PnL
    assert "-35.00" in exc_info.value.detail


# === Группа тестов для функции update_pnl ===

def test_update_pnl_accumulates_correctly():
    """Проверяет, что update_pnl корректно суммирует PnL за день."""
    conn = get_db_connection()
    try:
        # Эти операции происходят в чистой базе данных
        update_pnl(conn, 10.5)
        update_pnl(conn, -5.5)
        update_pnl(conn, 2.0)
        row = conn.execute("SELECT realised_pnl FROM daily_pnl WHERE trade_date = ?", (date.today(),)).fetchone()
    finally:
        conn.close()

    assert row is not None
    pnl = row['realised_pnl']
    # Значение будет ровно 7.0, так как нет "грязных" данных из других тестов
    assert np.isclose(pnl, 7.0)

def test_final_state_is_also_clean():
    """
    Этот тест должен выполняться ПОСЛЕДНИМ в этом файле.
    Он проверяет, осталось ли что-то в таблице после других тестов.
    """
    print("\n[DIAGNOSTIC] Running test_final_state_is_also_clean...")
    conn = get_db_connection()
    try:
        pnl_record = conn.execute("SELECT * FROM daily_pnl").fetchone()
    finally:
        conn.close()
    
    assert pnl_record is None, "ДИАГНОСТИКА: Таблица daily_pnl НЕ пуста в конце!"
# =================================================================