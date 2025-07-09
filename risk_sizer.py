# File: risk_sizer.py
import math

RISK_PER_TRADE_PCT = 0.01

def calculate_position_size(
    entry_price: float,
    stop_loss_price: float,
    equity: float,
    amount_precision_step: float,
    risk_pct: float = RISK_PER_TRADE_PCT
) -> float:
    
    price_diff = abs(entry_price - stop_loss_price)
    if equity <= 0 or price_diff == 0:
        return 0.0
        
    risk_per_trade_usd = equity * risk_pct
    position_size = risk_per_trade_usd / price_diff

    # ИЗМЕНЕНО: Используем более надежный метод округления
    if amount_precision_step == 1:
        # Для целых чисел (как SHIB) используем стандартное округление до целого
        return round(position_size)
    else:
        # Для дробных - вычисляем количество знаков из шага
        decimal_places = -int(math.log10(amount_precision_step))
        return round(position_size, decimal_places)