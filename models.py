# file: models.py
from pydantic import BaseModel, Field
from typing import List, Optional

class TradeInstruction(BaseModel):
    """Структурированная инструкция, полученная из парсера."""
    signal_id: str
    symbol: str = "BTCUSDT"
    side: str
    entry_start: float
    entry_end: float
    stop_loss: float
    risk_pct: float = Field(..., gt=0, le=0.1)
    size_fraction: float = Field(default=1.0, ge=0.1, le=1.0)
    take_profits: List[float]
    move_sl_to_be_after_tp_index: int = 1