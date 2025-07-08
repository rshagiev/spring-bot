# File: risk_sizer.py
RISK_PER_TRADE_PCT = 0.01

def calculate_position_size(
    entry_price: float,
    stop_loss_price: float,
    equity: float,
    amount_precision: int,
    risk_pct: float = RISK_PER_TRADE_PCT
) -> float:
    price_diff = abs(entry_price - stop_loss_price) # <-- ПЕРЕНЕСЕНО ВВЕРХ

    if equity <= 0 or price_diff == 0:
        return 0.0
        
    risk_per_trade_usd = equity * risk_pct
    position_size = risk_per_trade_usd / price_diff
    
    return round(position_size, amount_precision)