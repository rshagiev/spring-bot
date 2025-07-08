import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from itertools import product
from spring_model import bounce_prob

# --- Constants ---
INITIAL_EQUITY = 1000.0
RISK_PER_TRADE_PCT = 0.01
FIXED_RR_RATIO = 1.5
PROB_THRESHOLD = 0.5

def run_backtest(price_df, signals_df, bb_window, bb_std_dev):
    equity = INITIAL_EQUITY
    equity_curve = [INITIAL_EQUITY]
    trades = []

    for _, signal in signals_df.iterrows():
        # Find the price data available right before the signal
        bars = price_df[price_df['ts'] < signal['ts']].tail(bb_window)
        if len(bars) < bb_window:
            continue

        # 1. Filter signal through the spring model
        prob = bounce_prob(bars, signal['side'], signal['entry'], bb_window, bb_std_dev)
        if prob < PROB_THRESHOLD:
            continue

        # 2. Size the trade
        risk_per_trade_usd = equity * RISK_PER_TRADE_PCT
        stop_loss_dist = abs(signal['entry'] - signal['sl'])
        if stop_loss_dist == 0: continue
        position_size = risk_per_trade_usd / stop_loss_dist

        # 3. Determine TP based on fixed R:R
        take_profit_dist = stop_loss_dist * FIXED_RR_RATIO
        if signal['side'] == 'long':
            tp_price = signal['entry'] + take_profit_dist
            sl_price = signal['sl']
        else:
            tp_price = signal['entry'] - take_profit_dist
            sl_price = signal['sl']

        # 4. Simulate trade execution
        trade_data = price_df[price_df['ts'] >= signal['ts']]
        pnl = 0
        outcome = 'No fill'
        for _, row in trade_data.iterrows():
            if signal['side'] == 'long':
                if row['high'] >= tp_price:
                    pnl = (tp_price - signal['entry']) * position_size
                    outcome = 'TP'
                    break
                if row['low'] <= sl_price:
                    pnl = (sl_price - signal['entry']) * position_size
                    outcome = 'SL'
                    break
            else: # short
                if row['low'] <= tp_price:
                    pnl = (signal['entry'] - tp_price) * position_size
                    outcome = 'TP'
                    break
                if row['high'] >= sl_price:
                    pnl = (signal['entry'] - sl_price) * position_size
                    outcome = 'SL'
                    break

        if outcome in ['TP', 'SL']:
            equity += pnl
            equity_curve.append(equity)
            trades.append({'pnl': pnl, 'outcome': outcome})
    
    return equity_curve, trades

def calculate_metrics(equity_curve, num_days):
    returns = pd.Series(equity_curve).pct_change().dropna()
    total_return = (equity_curve[-1] / INITIAL_EQUITY) - 1
    
    # Max Drawdown
    rolling_max = pd.Series(equity_curve).cummax()
    drawdown = (pd.Series(equity_curve) - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    
    # Sharpe Ratio (annualized)
    daily_returns = returns[returns != 0]
    if len(daily_returns) > 1 and daily_returns.std() != 0:
        # NOTE: This is an approximate annualization, assuming trades are somewhat evenly distributed.
        # It's suitable for comparing parameters but is not a perfectly rigorous Sharpe calculation.
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(365 * 24 * 60 / (num_days * 24 * 60 / len(daily_returns)) )
    else:
        sharpe_ratio = 0

    return total_return, max_drawdown, sharpe_ratio

if __name__ == '__main__':
    # 1. Load data
    try:
        price_df = pd.read_csv('btc_1m.csv', names=['ts', 'open', 'high', 'low', 'close', 'volume'])
        signals_df = pd.read_csv('signals.csv') # ts, side, entry, sl, tp
    except FileNotFoundError as e:
        print(f"Error: {e}. Make sure 'btc_1m.csv' (no header) and 'signals.csv' are present.")
        exit()

    # Ensure timestamps are numeric for comparison (OS-agnostic method)
    price_df['ts'] = pd.to_datetime(price_df['ts']).view('int64') // 10**9
    signals_df['ts'] = pd.to_datetime(signals_df['ts']).view('int64') // 10**9
    num_days = (price_df['ts'].max() - price_df['ts'].min()) / (60 * 60 * 24)

    # 5. Parameter Grid Search
    bb_windows = [10, 20, 30]
    bb_multipliers = [1.5, 2.0, 2.5]
    results = []

    print("Running backtest grid search...")
    for window, mult in product(bb_windows, bb_multipliers):
        equity_curve, trades = run_backtest(price_df, signals_df, window, mult)
        if len(equity_curve) > 1:
            total_r, max_dd, sharpe = calculate_metrics(equity_curve, num_days)
            results.append(((window, mult), total_r, max_dd, sharpe, len(trades)))
    
    # Print results
    print("\n--- Backtest Results ---")
    print(f"{'Params (win, std)':<20} | {'Total Return':>15} | {'Max Drawdown':>15} | {'Sharpe Ratio':>15} | {'Num Trades':>12}")
    print('-'*85)
    sorted_results = sorted(results, key=lambda x: x[3], reverse=True) # Sort by Sharpe
    for params, total_r, max_dd, sharpe, num_trades in sorted_results:
        print(f"{str(params):<20} | {total_r:>14.2%} | {max_dd:>14.2%} | {sharpe:>15.2f} | {num_trades:>12}")

    # Plot the best result
    if sorted_results:
        best_params = sorted_results[0][0]
        print(f"\nPlotting equity curve for best params: {best_params}")
        best_equity_curve, _ = run_backtest(price_df, signals_df, best_params[0], best_params[1])
        plt.figure(figsize=(12, 6))
        plt.plot(best_equity_curve)
        plt.title(f'Equity Curve - Best Params: {best_params} (Sharpe: {sorted_results[0][3]:.2f})')
        plt.xlabel('Trade Number')
        plt.ylabel('Equity (USDT)')
        plt.grid(True)
        plt.savefig('equity_curve.png')
        print("Saved equity curve to equity_curve.png")