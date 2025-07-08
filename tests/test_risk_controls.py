import pytest
import sqlite3
import os
import numpy as np
from datetime import date
from fastapi import HTTPException

# Import the module itself to allow monkeypatching
import risk_controls
# Import the functions we need to call
from risk_controls import check_daily_drawdown, update_pnl, get_db_connection

TEST_DB = "test_trades_isolated.sqlite"

@pytest.fixture(autouse=True)
def setup_teardown_db(monkeypatch):
    """
    This fixture is now robust and guarantees test isolation.
    """
    # 1. Use monkeypatch to temporarily change the DATABASE_FILE constant
    #    within the risk_controls module for the duration of one test.
    monkeypatch.setattr(risk_controls, "DATABASE_FILE", TEST_DB)

    # 2. Clean up any previous test database file before the test starts.
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    # 3. Initialize a fresh table for this specific test.
    risk_controls.initialize_pnl_table()
    
    yield  # Run the test

    # 4. Clean up the database file after the test is done.
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# A dummy async function to be decorated
@check_daily_drawdown(max_loss_pct=0.03)
async def dummy_trade_route():
    return {"status": "trade allowed"}

@pytest.mark.asyncio
async def test_dd_within_limit():
    update_pnl(-10.0) # Loss is < 3% of 1000
    response = await dummy_trade_route()
    assert response == {"status": "trade allowed"}

@pytest.mark.asyncio
async def test_dd_at_limit():
    update_pnl(-30.0)
    with pytest.raises(HTTPException) as excinfo:
        await dummy_trade_route()
    assert excinfo.value.status_code == 429

@pytest.mark.asyncio
async def test_dd_exceeds_limit():
    update_pnl(-35.0)
    with pytest.raises(HTTPException) as excinfo:
        await dummy_trade_route()
    assert excinfo.value.status_code == 429
    # This assertion will now pass because the PnL is isolated.
    assert "-35.00" in excinfo.value.detail

@pytest.mark.asyncio
async def test_no_pnl_for_today():
    # PnL starts at 0 for this test, so it is allowed.
    response = await dummy_trade_route()
    assert response == {"status": "trade allowed"}

def test_update_pnl_idempotency():
    update_pnl(10.5)
    update_pnl(-5.5)
    
    conn = get_db_connection()
    pnl = conn.execute("SELECT realised_pnl FROM daily_pnl WHERE trade_date = ?", (date.today(),)).fetchone()['realised_pnl']
    conn.close()
    # This will now correctly be 5.0, not an accumulated value.
    assert np.isclose(pnl, 5.0)