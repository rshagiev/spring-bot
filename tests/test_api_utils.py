# File: tests/test_api_utils.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_ping():
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_open_positions_returns_dict(mock_bybit_client_main): # Используем фикстуру
    response = client.get('/open_positions')
    assert response.status_code == 200
    data = response.json()
    assert "BTCUSDT" in data
    assert data['BTCUSDT']['contracts'] == 1.0