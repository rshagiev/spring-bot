# file: signal_parser.py
import re
import hashlib
from typing import Optional
from models import TradeInstruction

def parse_pentagon_signal(text: str) -> Optional[TradeInstruction]:
    """Парсит текстовый сигнал и возвращает структурированный объект TradeInstruction."""
    try:
        side_match = re.search(r'(лонг|шорт)', text, re.IGNORECASE)
        side = 'long' if 'лонг' in side_match.group(0).lower() else 'short'

        entry_match = re.search(r'(\d{4,6})-(\d{4,6})', text)
        entry_start, entry_end = sorted([float(entry_match.group(1)), float(entry_match.group(2))])

        sl_match = re.search(r'стоп\s*(?:под|над)?\s*(\d+\.?\d*)', text, re.IGNORECASE)
        stop_loss = float(sl_match.group(1))

        risk_match = re.search(r'риском\s+([\d.]+)\s*%\s*\((\d\/\d)\)', text, re.IGNORECASE)
        risk_pct = float(risk_match.group(1)) / 100
        num, den = map(int, risk_match.group(2).split('/'))
        size_fraction = num / den

        targets_block_match = re.search(r'Цели:([\s\S]*?)(?:\n\n|\Z)', text, re.IGNORECASE)
        targets_block = targets_block_match.group(1)
        take_profits = [float(tp) for tp in re.findall(r'(\d{4,6})', targets_block)]
        if not take_profits:
            raise ValueError("No take profits found in signal")

        signal_id = hashlib.md5(text.encode()).hexdigest()

        return TradeInstruction(
            signal_id=signal_id,
            side=side,
            entry_start=entry_start,
            entry_end=entry_end,
            stop_loss=stop_loss,
            risk_pct=risk_pct,
            size_fraction=size_fraction,
            take_profits=take_profits,
        )
    except (AttributeError, ValueError, IndexError) as e:
        print(f"Signal parsing failed: {e}")
        return None