import pandas as pd
import numpy as np

def bounce_prob(
    bars: pd.DataFrame,
    side: str,
    price: float,
    bb_window: int = 20,
    bb_std_dev: float = 2.0
) -> float:
    """
    Calculates the 'bounce probability' based on a Bollinger Band mean-reversion model.

    Args:
        bars: DataFrame with historical data, must contain a 'close' column.
        side: The trade side, either 'long' or 'short'.
        price: The current price to evaluate.
        bb_window: The moving average window for Bollinger Bands.
        bb_std_dev: The standard deviation multiplier for Bollinger Bands.

    Returns:
        A probability score [0, 1] indicating the likelihood of a bounce.
    """
    if side not in ['long', 'short']:
        raise ValueError("Side must be either 'long' or 'short'.")

    if len(bars) < bb_window:
        # Not enough data to calculate BBs, no basis for a bounce.
        return 0.0

    # Calculate Bollinger Bands from the historical bars
    closes = bars['close']
    mu = closes.rolling(window=bb_window).mean().iloc[-1]
    sigma = closes.rolling(window=bb_window).std().iloc[-1]

    # Handle case of zero volatility to prevent division by zero
    if sigma == 0:
        return 0.0

    lower_bb = mu - bb_std_dev * sigma
    upper_bb = mu + bb_std_dev * sigma
    p_raw = 0.0

    if side == "long":
        # Probability increases as price drops further below the lower band.
        if price < lower_bb:
            p_raw = (lower_bb - price) / (bb_std_dev * sigma)
    else:  # side == "short"
        # Probability increases as price rises further above the upper band.
        if price > upper_bb:
            p_raw = (price - upper_bb) / (bb_std_dev * sigma)
    
    # Clip the result to be within the valid probability range [0, 1]
    return float(np.clip(p_raw, 0, 1))