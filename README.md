# LLM-Driven Crypto Trading Bot

Автоматизированная система исполнения сигналов для Bybit, построенная по плану «LLM-пишет-код».  
Стратегия: человек-трейдер шлёт raw-сигналы → модуль **Spring Model** (Bollinger Bands) решает, брать ли сигнал → бот открывает позицию и жёстко контролирует риск.

---

## 📂 Содержимое репозитория

| Файл | Назначение |
|------|-----------|
| `spring_model.py` | Функция `bounce_prob()` возвращает вероятность отскока (0–1) |
| `backtest_runner.py` | Бэктест + grid-search параметров BB |
| `risk_controls.py` | Декоратор `@check_daily_drawdown` и helper `update_pnl()` |
| `.github/workflows/python-test.yml` | CI: прогоняет `pytest` на каждый PR |
| `tests/*` | Unit-тесты для всех модулей |
| `requirements.txt` | Зависимости (pandas, numpy …) |

---

## ⚙️ Быстрый старт

### 1. Клонируем и создаём окружение

```bash
git clone https://github.com/<YOUR_LOGIN>/spring-bot.git
cd spring-bot
python3 -m venv venv
source venv/bin/activate         # Windows → venv\Scripts\activate
pip install -r requirements.txt