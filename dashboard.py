# file: dashboard.py
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from db_utils import get_db_connection
import json

# --- Конфигурация ---
REFRESH_INTERVAL_SECONDS = 10
st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")
st_autorefresh(interval=REFRESH_INTERVAL_SECONDS * 1000, key="dashboard_refresh")

# --- Функции для загрузки данных ---
@st.cache_data(ttl=REFRESH_INTERVAL_SECONDS)
def load_data():
    conn = get_db_connection()
    active = pd.read_sql_query("SELECT * FROM managed_trades WHERE status != 'CLOSED' ORDER BY created_at DESC", conn)
    history = pd.read_sql_query("SELECT * FROM managed_trades WHERE status = 'CLOSED' ORDER BY updated_at DESC LIMIT 50", conn)
    # Используем left join для обогащения активных сделок живыми ценами
    prices = pd.read_sql_query("SELECT * FROM live_prices", conn)
    if not active.empty and not prices.empty:
        active = pd.merge(active, prices, on='symbol', how='left')
    conn.close()
    return active, history

# --- Основная структура дашборда ---
st.title("🤖 Stateful Trading Bot Dashboard v2.0")
active_df, history_df = load_data()

# --- Блок 1: Управляемые Сделки ---
st.subheader("📊 Managed Trades")
if not active_df.empty:
    active_df['progress'] = active_df['executed_qty'] / active_df['total_qty']
    # Добавим uPNL (упрощенно)
    if 'mark_price' in active_df.columns:
        active_df['uPNL'] = (active_df['mark_price'] - active_df['avg_entry_price']) * active_df['executed_qty']
        active_df.loc[active_df['side'] == 'short', 'uPNL'] *= -1

    st.dataframe(
        active_df.style.bar(subset=['progress'], align='mid', color=['#d6e8d6', '#e8d6d6']),
        use_container_width=True, hide_index=True
    )
else:
    st.info("No active trades to manage.")

# --- Блок 2: История Сделок ---
st.subheader("📈 Trade History")
if not history_df.empty:
    st.dataframe(history_df, use_container_width=True, hide_index=True)
else:
    st.info("Trade history is empty.")

# --- Блок 3: Журнал Событий (опционально, если нужен) ---
# ...