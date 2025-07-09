# file: tests/test_api_process_signal.py
import pytest
from unittest.mock import AsyncMock
from db_utils import get_db_connection


VALID_SIGNAL_TEXT = "🔴пробую шорт 109200-110500 и риском 0.5% (1/2) стоп над 111500\nЦели: 109000"

def test_api_db_is_clean_before_run(test_app_client):
    """
    Verifies that the database is clean at the start of an API test.
    The app factory pattern ensures no state leaks from previous tests.
    """
    conn = get_db_connection()
    try:
        pnl_record = conn.execute("SELECT * FROM daily_pnl").fetchone()
    finally:
        conn.close()
    
    assert pnl_record is None, "The daily_pnl table should be empty."

def test_process_signal_creates_trade_in_db(test_app_client, mock_place_entry_grid):
    """
    Tests the full API endpoint flow from signal to DB record.
    """
    response = test_app_client.post("/process_signal", params={"raw_text": VALID_SIGNAL_TEXT})

    assert response.status_code == 202, f"API returned an unexpected status. Body: {response.text}"
    data = response.json()
    assert data['status'] == 'accepted'
    trade_id = data['trade_id']

    conn = get_db_connection()
    try:
        trade_in_db = conn.execute("SELECT * FROM managed_trades WHERE id = ?", (trade_id,)).fetchone()
    finally:
        conn.close()
    
    assert trade_in_db is not None
    assert trade_in_db['status'] == 'PENDING_ENTRY'
    assert trade_in_db['side'] == 'short'

    mock_place_entry_grid.assert_called_once()
    args, _ = mock_place_entry_grid.call_args
    assert args[0] == trade_id