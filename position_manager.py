# file: position_manager.py
import asyncio
import json
import numpy as np
import sqlite3
from datetime import datetime, timezone

from db_utils import get_db_connection
from trade_logger import log_event
from bybit_wrapper import AsyncBybitWrapper
from risk_controls import update_pnl

# --- Константы ---
MANAGER_LOOP_SLEEP_INTERVAL = 15
ENTRY_GRID_ORDERS = 3

# ==============================================================================
# 1. ЗАДАЧА РАЗМЕЩЕНИЯ ОРДЕРОВ (уже была правильной)
# ==============================================================================
async def place_entry_grid(trade_id: int, total_qty: float, instruction: dict, bybit_client: AsyncBybitWrapper):
    """
    Выставляет сетку лимитных ордеров на вход для новой сделки.
    Эта функция корректно управляет своим собственным соединением с БД.
    """
    conn = get_db_connection()
    try:
        existing_orders = conn.execute("SELECT 1 FROM entry_orders WHERE trade_id = ?", (trade_id,)).fetchone()
        if existing_orders:
            log_event("GRID_PLACEMENT_SKIPPED", {"reason": "already_exists", "trade_id": trade_id})
            return

        precision = bybit_client.get_market_precision(instruction['symbol'])
        if not precision or not precision.get('amount'):
            log_event("GRID_PLACEMENT_ERROR", {"reason": "missing_precision", "trade_id": trade_id})
            return

        amount_step = precision.get('amount', 1e-8) # Безопасное значение по умолчанию
        order_qty = round(total_qty / ENTRY_GRID_ORDERS, int(-np.log10(amount_step)))
        if order_qty <= 0:
            log_event("GRID_PLACEMENT_ERROR", {"reason": "zero_order_qty", "trade_id": trade_id})
            return
            
        entry_prices = np.linspace(instruction['entry_start'], instruction['entry_end'], ENTRY_GRID_ORDERS)
        
        with conn:
            for price in entry_prices:
                try:
                    order = await bybit_client.create_limit_order(
                        symbol=instruction['symbol'], side=instruction['side'], amount=order_qty, price=price
                    )
                    log_event("ENTRY_ORDER_PLACED", {"trade_id": trade_id, "order_id": order['id'], "price": price})
                    conn.execute(
                        "INSERT INTO entry_orders (trade_id, exchange_order_id, status) VALUES (?, ?, ?)",
                        (trade_id, order['id'], 'open')
                    )
                except Exception as e:
                    log_event("ENTRY_ORDER_FAILED", {"trade_id": trade_id, "price": price, "error": str(e)})
    finally:
        if conn:
            conn.close()

# ==============================================================================
# 2. ГЛАВНЫЙ ЦИКЛ МЕНЕДЖЕРА (ИСПРАВЛЕНО)
# ==============================================================================
async def position_manager_loop(bybit_client: AsyncBybitWrapper):
    """Главный цикл, который управляет всеми активными и ожидающими сделками."""
    log_event("POSITION_MANAGER_STARTED", {})
    while True:
        try:
            trades_to_manage = []
            conn = get_db_connection()
            try:
                # Получаем список сделок и сразу закрываем соединение
                trades_to_manage_rows = conn.execute("SELECT * FROM managed_trades WHERE status != 'CLOSED'").fetchall()
                trades_to_manage = [dict(row) for row in trades_to_manage_rows]
            finally:
                conn.close()
            
            if not trades_to_manage:
                await asyncio.sleep(MANAGER_LOOP_SLEEP_INTERVAL)
                continue

            live_positions = await bybit_client.fetch_open_positions()
            
            active_symbols = {trade['symbol'] for trade in trades_to_manage}
            if active_symbols:
                # Эта функция сама управляет своим соединением
                await update_live_prices(bybit_client, list(active_symbols))
            
            for trade in trades_to_manage:
                # Передаем bybit_client, но не соединение
                await reconcile_and_manage(trade, live_positions.get(trade['symbol']), bybit_client)
                
        except asyncio.CancelledError:
            log_event("POSITION_MANAGER_STOPPED", {})
            break
        except Exception as e:
            log_event("POSITION_MANAGER_ERROR", {"error": str(e), "context": "Main Loop"})
        
        await asyncio.sleep(MANAGER_LOOP_SLEEP_INTERVAL)

# ==============================================================================
# 3. ЛОГИКА СВЕРКИ И УПРАВЛЕНИЯ (ИСПРАВЛЕНО)
# ==============================================================================
async def reconcile_and_manage(trade: dict, live_position: dict, bybit_client: AsyncBybitWrapper):
    """
    Центральная стейт-машина для одной сделки.
    Больше не принимает 'conn', а создает соединения по необходимости.
    """
    trade_id = trade['id']
    status = trade['status']
    now_utc = datetime.now(timezone.utc).isoformat(timespec='microseconds')

    try:
        # --- Состояние: PENDING_ENTRY -> ACTIVE ---
        if status == 'PENDING_ENTRY' and live_position:
            avg_price = float(live_position['entryPrice'])
            exec_qty = float(live_position['contracts'])
            log_event("ENTRY_DETECTED", {"trade_id": trade_id, "avg_price": avg_price, "qty": exec_qty})
            
            sl_order = await bybit_client.create_order(
                symbol=trade['symbol'], type='market', side='buy' if trade['side'] == 'short' else 'sell',
                amount=exec_qty, params={'stopLoss': trade['initial_sl_price'], 'reduceOnly': True}
            )
            sl_order_id = sl_order.get('id')
            
            conn = get_db_connection()
            try:
                entry_orders_to_cancel = conn.execute("SELECT exchange_order_id FROM entry_orders WHERE trade_id = ? AND status = 'open'", (trade_id,)).fetchall()
            finally:
                conn.close()

            for order_row in entry_orders_to_cancel:
                await bybit_client.cancel_order(order_row['exchange_order_id'], trade['symbol'])

            conn = get_db_connection()
            try:
                with conn:
                    conn.execute(
                        "UPDATE managed_trades SET status=?, avg_entry_price=?, executed_qty=?, exchange_sl_order_id=?, updated_at=? WHERE id=?",
                        ('ACTIVE', avg_price, exec_qty, sl_order_id, now_utc, trade_id)
                    )
                    conn.execute("UPDATE entry_orders SET status='cancelled' WHERE trade_id=? AND status='open'", (trade_id,))
                log_event("TRADE_ACTIVATED", {"trade_id": trade_id, "sl_order_id": sl_order_id})
            finally:
                conn.close()

        # --- Состояние: ACTIVE -> CLOSED ---
        elif status == 'ACTIVE' and not live_position:
            # ... (код выше без изменений) ...
            pnl, reason = await get_realized_pnl(trade, bybit_client)

            conn = get_db_connection()
            try:
                with conn:
                    # ИСПРАВЛЕНИЕ: Добавляем недостающий UPDATE-запрос
                    conn.execute(
                        "UPDATE managed_trades SET status='CLOSED', close_reason=?, realized_pnl=?, updated_at=? WHERE id=?",
                        (reason, pnl, now_utc, trade_id)
                    )
                # Убедимся, что PnL не None перед обновлением
                if pnl is not None:
                    update_pnl(conn, pnl) 
            finally:
                conn.close()
            log_event("PNL_UPDATED", {"trade_id": trade_id, "pnl": pnl})

        # --- Состояние: ACTIVE (Управление TP / SL) ---
        elif status == 'ACTIVE' and live_position:
            remaining_tps = json.loads(trade['remaining_tps'])
            if not remaining_tps: return

            mark_price = float(live_position['markPrice'])
            next_tp_price = remaining_tps[0]

            tp_hit = (trade['side'] == 'long' and mark_price >= next_tp_price) or \
                     (trade['side'] == 'short' and mark_price <= next_tp_price)

            if tp_hit:
                initial_tps_count = len(json.loads(trade['initial_tps']))
                precision = bybit_client.get_market_precision(trade['symbol'])
                amount_step = precision.get('amount', 1e-8)
                tp_qty = round(trade['total_qty'] / initial_tps_count, int(-np.log10(amount_step)))
                
                if tp_qty > 0:
                    await bybit_client.create_limit_order(
                        symbol=trade['symbol'], side='buy' if trade['side'] == 'short' else 'sell',
                        amount=tp_qty, price=next_tp_price, params={'reduceOnly': True}
                    )
                
                remaining_tps.pop(0)
                conn = get_db_connection()
                try:
                    with conn:
                        conn.execute("UPDATE managed_trades SET remaining_tps=?, updated_at=? WHERE id=?", (json.dumps(remaining_tps), now_utc, trade_id))
                    log_event("TP_ORDER_PLACED", {"trade_id": trade_id, "tp_price": next_tp_price})
                finally:
                    conn.close()
            
            initial_tps_count = len(json.loads(trade['initial_tps']))
            tps_taken = initial_tps_count - len(remaining_tps)
            
            if (trade.get('move_sl_to_be_after_tp_index') is not None and 
                tps_taken >= trade['move_sl_to_be_after_tp_index'] and 
                trade['avg_entry_price'] is not None and
                trade['current_sl_price'] != trade['avg_entry_price']):
                
                new_sl_price = trade['avg_entry_price']
                log_event("MOVING_SL_TO_BREAKEVEN", {"trade_id": trade_id, "new_sl": new_sl_price})
                
                await bybit_client.edit_order(
                    trade['exchange_sl_order_id'], trade['symbol'], new_sl_price
                )
                conn = get_db_connection()
                try:
                    with conn:
                        conn.execute("UPDATE managed_trades SET current_sl_price=?, updated_at=? WHERE id=?", (new_sl_price, now_utc, trade_id))
                    log_event("SL_MOVE_SUCCESS", {"trade_id": trade_id})
                finally:
                    conn.close()

    except Exception as e:
        log_event("RECONCILE_ERROR", {"trade_id": trade_id, "error": str(e), "status": status})

# ==============================================================================
# 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (ИСПРАВЛЕНО)
# ==============================================================================
async def update_live_prices(bybit_client: AsyncBybitWrapper, symbols: list):
    """Запрашивает и обновляет живые цены, управляя своим соединением."""
    conn = get_db_connection()
    try:
        tickers = await asyncio.gather(*[bybit_client.fetch_ticker_price(s) for s in symbols])
        now_utc = datetime.now(timezone.utc).isoformat(timespec='microseconds')
        
        with conn:
            for symbol, price in zip(symbols, tickers):
                if price > 0:
                    conn.execute(
                        "INSERT OR REPLACE INTO live_prices (symbol, mark_price, updated_at) VALUES (?, ?, ?)",
                        (symbol, price, now_utc)
                    )
    except Exception as e:
        log_event("LIVE_PRICE_UPDATE_ERROR", {"error": str(e)})
    finally:
        if conn:
            conn.close()

async def get_realized_pnl(trade: dict, bybit_client: AsyncBybitWrapper) -> tuple[float, str]:
    """
    Получает историю сделок пользователя с биржи для расчета PnL.
    Эта функция не взаимодействует с локальной БД.
    """
    try:
        my_trades = await bybit_client.fetch_my_trades(trade['symbol'], limit=20)
        
        trade_open_time = datetime.fromisoformat(trade['created_at'])
        relevant_trades = [t for t in my_trades if t.get('timestamp') and datetime.fromtimestamp(t['timestamp'] / 1000, tz=timezone.utc) > trade_open_time]
        
        if not relevant_trades:
            return 0.0, "UNKNOWN_NO_TRADES"

        realized_pnl = sum(t.get('fee', {}).get('cost', 0) * -1 for t in relevant_trades if t.get('fee'))

        last_trade = relevant_trades[-1]
        if last_trade.get('price') and trade.get('current_sl_price') and last_trade['price'] == trade['current_sl_price']:
            return realized_pnl, "SL_HIT"
        elif last_trade.get('price') and trade.get('initial_tps') and last_trade['price'] in json.loads(trade['initial_tps']):
             return realized_pnl, "TP_HIT"
        else:
            return realized_pnl, "MANUAL_OR_OTHER"

    except Exception as e:
        log_event("PNL_FETCH_ERROR", {"trade_id": trade['id'], "error": str(e)})
        return 0.0, "ERROR_FETCHING_PNL"