# file: tests/conftest.py
import pytest
import os
import sqlite3
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone

TEST_DB_FILE = "test_app_db.sqlite"

@pytest.fixture(scope="function", autouse=True)
def setup_for_every_test(monkeypatch, mocker):
    # 1. Isolate the database by deleting files
    monkeypatch.setenv("DATABASE_FILE", TEST_DB_FILE)
    if os.path.exists(TEST_DB_FILE): os.remove(TEST_DB_FILE)
    if os.path.exists(f"{TEST_DB_FILE}-shm"): os.remove(f"{TEST_DB_FILE}-shm")
    if os.path.exists(f"{TEST_DB_FILE}-wal"): os.remove(f"{TEST_DB_FILE}-wal")
    
    # 2. Setup schema in the new, clean file
    from db_setup import setup_database
    setup_database()

    # 3. Mock external services
    mock_main_bybit_client = AsyncMock(name="main_bybit_client_mock")
    mock_main_bybit_client.set_sandbox_mode = MagicMock()
    mock_main_bybit_client.init.return_value = None
    mock_main_bybit_client.get_usdt_balance.return_value = 1000.0
    
    # --- FIX ---
    # `get_market_precision` is a sync method on an async class. We must replace it
    # with a synchronous MagicMock that returns a value directly.
    mock_main_bybit_client.get_market_precision = MagicMock(return_value={'amount': 0.001, 'price': 0.01})
    
    mock_main_bybit_client.fetch_open_positions.return_value = {}
    mock_main_bybit_client.fetch_my_trades.return_value = []
    mocker.patch('main.bybit_client', new=mock_main_bybit_client)

    mocker.patch('main.position_manager_loop', new_callable=AsyncMock)
    
    yield

@pytest.fixture
def test_app_client():
    """Provides a TestClient to the app. The app is now safe to use
    because the autouse fixture has already cleaned and mocked everything."""
    from main import app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def mock_place_entry_grid(mocker):
    """Mocks the main.place_entry_grid function and returns the mock object."""
    return mocker.patch('main.place_entry_grid', new_callable=AsyncMock)

# This fixture is for non-API tests that need a standalone mock client.
# It's different from the one used by the app, ensuring no cross-contamination.
@pytest.fixture
def mock_bybit_client():
    """
    Provides a standalone mock client for non-API unit tests.
    """
    client = AsyncMock(name="standalone_mock_bybit_client")

    # --- FIX ---
    # Apply the same fix here for consistency across all tests.
    client.get_market_precision = MagicMock(return_value={'amount': 0.001, 'price': 0.01})

    client.create_order.return_value = {"id": "stop_loss_order_1"}
    
    # --- ИСПРАВЛЕНИЕ ДЛЯ PNL ---
    # Симулируем, что fetch_my_trades возвращает одну сделку с нулевой комиссией.
    # Это позволит get_realized_pnl вернуть 0.0, а не ошибку.
    client.fetch_my_trades.return_value = [
        {'timestamp': datetime.now(timezone.utc).timestamp() * 1000, 'fee': {'cost': 0.0}}
    ]
    # ---------------------------

    return client