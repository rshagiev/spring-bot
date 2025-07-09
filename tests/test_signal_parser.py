# file: tests/test_signal_parser.py
import pytest
from signal_parser import parse_pentagon_signal

# Пример успешного сигнала
VALID_SIGNAL_TEXT = """
🔴пробую шорт 109200-110500 и риском 0.5% (1/2) стоп над 111500, после 2ого тейка в бу
Цели: 
109000-108800-108600
"""

# Пример сигнала с ошибкой (нет тейков)
INVALID_SIGNAL_TEXT = "🔴пробую шорт 109200-110500 и риском 0.5% (1/2) стоп над 111500"

def test_parse_valid_signal_success():
    """Тестирует успешный парсинг корректного сигнала."""
    instruction = parse_pentagon_signal(VALID_SIGNAL_TEXT)
    
    assert instruction is not None
    assert instruction.side == 'short'
    assert instruction.entry_start == 109200.0
    assert instruction.entry_end == 110500.0
    assert instruction.stop_loss == 111500.0
    assert instruction.risk_pct == pytest.approx(0.005)
    assert instruction.size_fraction == pytest.approx(0.5)
    assert instruction.take_profits == [109000.0, 108800.0, 108600.0]

def test_parse_invalid_signal_returns_none():
    """Тестирует, что парсер возвращает None для некорректного сигнала."""
    instruction = parse_pentagon_signal(INVALID_SIGNAL_TEXT)
    assert instruction is None

def test_parse_empty_string_returns_none():
    """Тестирует обработку пустой строки."""
    instruction = parse_pentagon_signal("")
    assert instruction is None