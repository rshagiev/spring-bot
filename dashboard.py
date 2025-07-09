# File: dashboard.py (ФИНАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ)
import streamlit as st
import pandas as pd
import requests
import sqlite3 # <-- Импортируем стандартный sqlite3
import sqlite_utils
import json
import os
from streamlit_autorefresh import st_autorefresh

# --- Конфигурация ---
API_BASE_URL = os.getenv("BOT_API_URL", "http://127.0.0.1:8000")
DB_FILE = os.getenv("TRADE_DB", "trades.sqlite")
REFRESH_INTERVAL_SECONDS = 5

st.set_page_config(
    page_title="Trading Bot Dashboard",
    layout="wide",
)

# --- Автоматическое обновление страницы ---
st_autorefresh(interval=REFRESH_INTERVAL_SECONDS * 1000, key="dashboard_refresh")

# --- Функции для загрузки данных ---
@st.cache_resource
def get_db_conn():
    """
    Кеширует подключение к БД.
    ИЗМЕНЕНО: Используем sqlite3 для создания потокобезопасного подключения.
    """
    try:
        # Создаем подключение с помощью стандартной библиотеки, отключая проверку потока
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        # Оборачиваем его в объект sqlite_utils
        return sqlite_utils.Database(conn)
    except Exception as e:
        st.error(f"Failed to connect to database: {DB_FILE}. Error: {e}")
        return None

@st.cache_data(ttl=REFRESH_INTERVAL_SECONDS)
def get_open_positions():
    """Запрашивает открытые позиции с нашего API."""
    try:
        response = requests.get(f"{API_BASE_URL}/open_positions")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return {}

@st.cache_data(ttl=REFRESH_INTERVAL_SECONDS)
def get_event_log(limit=20):
    """Читает последние события из лога."""
    db = get_db_conn()
    if db is None or 'trade_log' not in db.table_names():
        return []
    try:
        return list(db.table('trade_log').rows_where(order_by='id DESC', limit=limit))
    except Exception:
        return []

# --- Основная структура дашборда ---
st.title("🤖 LLM-Driven Trading Bot Dashboard")

# --- Секция 1: Открытые Позиции ---
st.subheader("📊 Open Positions")
positions_data = get_open_positions()
if positions_data:
    positions_df = pd.DataFrame(list(positions_data.values()))
    display_cols = {
        'symbol': 'Symbol', 'side': 'Side', 'contracts': 'Size',
        'entryPrice': 'Entry', 'markPrice': 'Mark', 'unrealizedPnl': 'uPNL'
    }
    existing_cols = [col for col in display_cols.keys() if col in positions_df.columns]
    if existing_cols:
        filtered_df = positions_df[existing_cols].rename(columns=display_cols)
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    else:
        st.info("No open positions with required data.")
else:
    st.info("No open positions or API not reachable.")

# --- Секция 2: Журнал Событий ---
st.subheader("📜 Recent Events")
log_data = get_event_log()
if log_data:
    log_df = pd.DataFrame(log_data)
    if 'payload_json' in log_df.columns:
        log_df['timestamp_utc'] = pd.to_datetime(log_df['timestamp_utc']).dt.strftime('%Y-%m-%d %H:%M:%S')
        def pretty_payload(payload_str):
            try: return json.loads(payload_str)
            except: return payload_str
        log_df['payload'] = log_df['payload_json'].apply(pretty_payload)
        st.dataframe(
            log_df[['timestamp_utc', 'event_type', 'payload']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.dataframe(log_df, use_container_width=True, hide_index=True)
else:
    st.warning("Event log is empty or database not found.")

# --- Секция 3: Кривая капитала (заглушка) ---
st.subheader("📈 Equity Curve (placeholder)")
st.info("Equity curve will be implemented once PnL data is logged upon trade closure.")