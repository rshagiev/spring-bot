# Новая модель для сигнала
class PentagonSignal(BaseModel):
    symbol: str
    side: str
    entry_start: float
    entry_end: float
    stop_loss: float
    risk_pct: float
    size_fraction: float = 1.0 # По умолчанию 1, если не указано
    take_profits: List[float]
    move_sl_to_be_after_tp_index: int = 1 # Индекс тейка (0-based) для переноса в БУ