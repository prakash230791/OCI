"""
OCI Homelab - Stock Market AI Pipeline DAG
Runs Monday–Friday at 06:00 UTC.

Tasks:
  1. fetch_stock_data  — Download OHLCV + technical indicators via yfinance
  2. analyze_with_llm  — Get BUY/HOLD/SELL signals from Groq LLM
  3. send_alerts       — Send morning report via Telegram if any BUY signals
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator

# ---------------------------------------------------------------------------
# Default args
# ---------------------------------------------------------------------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ---------------------------------------------------------------------------
# Helper: read from env var first, fall back to Airflow Variable
# ---------------------------------------------------------------------------
def _get_config(env_var: str, airflow_var: str, default: str = "") -> str:
    return os.environ.get(env_var) or Variable.get(airflow_var, default_var=default)


DATA_DIR = Path("/home/ubuntu/ai-pipeline/data")
US_TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
IN_TICKERS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "BHARTIARTL.NS"]
ALL_TICKERS = US_TICKERS + IN_TICKERS


# ---------------------------------------------------------------------------
# Task 1: Fetch stock data + calculate RSI and MACD
# ---------------------------------------------------------------------------
def fetch_stock_data(**context) -> None:
    """Download OHLCV data for US + Indian stocks and compute RSI / MACD."""
    import pandas as pd
    import yfinance as yf

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    run_date = context["ds"]  # YYYY-MM-DD string
    results = {}

    for ticker in ALL_TICKERS:
        try:
            df = yf.download(ticker, period="60d", interval="1d", progress=False)
            if df.empty:
                print(f"[WARN] No data for {ticker}")
                continue

            close = df["Close"].squeeze()

            # RSI — 14-period
            delta = close.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(14).mean()
            avg_loss = loss.rolling(14).mean()
            rs = avg_gain / avg_loss.replace(0, float("nan"))
            rsi = (100 - (100 / (1 + rs))).iloc[-1]

            # MACD — (12, 26, 9)
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_value = macd_line.iloc[-1]
            macd_signal = signal_line.iloc[-1]
            macd_hist = macd_value - macd_signal

            results[ticker] = {
                "ticker": ticker,
                "date": run_date,
                "price": round(float(close.iloc[-1]), 4),
                "rsi": round(float(rsi), 2) if not pd.isna(rsi) else None,
                "macd": round(float(macd_value), 4),
                "macd_signal": round(float(macd_signal), 4),
                "macd_hist": round(float(macd_hist), 4),
                "volume": int(df["Volume"].iloc[-1]),
                "open": round(float(df["Open"].iloc[-1]), 4),
                "high": round(float(df["High"].iloc[-1]), 4),
                "low": round(float(df["Low"].iloc[-1]), 4),
            }
            print(f"[OK] {ticker}: price={results[ticker]['price']} RSI={results[ticker]['rsi']}")

        except Exception as exc:
            print(f"[ERROR] {ticker}: {exc}")

    output_file = DATA_DIR / f"stock_data_{run_date}.json"
    output_file.write_text(json.dumps(results, indent=2))
    print(f"Saved {len(results)} tickers to {output_file}")


# ---------------------------------------------------------------------------
# Task 2: Analyse with Groq LLM → store signals in PostgreSQL
# ---------------------------------------------------------------------------
def analyze_with_llm(**context) -> None:
    """Call Groq LLM for each ticker and persist BUY/HOLD/SELL signals to DB."""
    import psycopg2
    from groq import Groq

    run_date = context["ds"]
    data_file = DATA_DIR / f"stock_data_{run_date}.json"

    if not data_file.exists():
        raise FileNotFoundError(f"Stock data file not found: {data_file}")

    stock_data: dict = json.loads(data_file.read_text())
    if not stock_data:
        print("[WARN] No stock data to analyse.")
        return

    groq_api_key = _get_config("GROQ_API_KEY", "groq_api_key")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not set in environment or Airflow Variables")

    client = Groq(api_key=groq_api_key)

    # Database connection
    db_conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="ai_pipeline",
        user="aiuser",
        password="aipassword",
    )
    db_conn.autocommit = False
    cursor = db_conn.cursor()

    # Create table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_signals (
            id          SERIAL PRIMARY KEY,
            ticker      VARCHAR(20)   NOT NULL,
            date        DATE          NOT NULL,
            signal      VARCHAR(10)   NOT NULL,
            confidence  INTEGER       NOT NULL,
            rationale   TEXT,
            rsi         NUMERIC(8,2),
            macd        NUMERIC(10,4),
            price       NUMERIC(12,4),
            created_at  TIMESTAMPTZ   DEFAULT NOW()
        );
    """)

    for ticker, data in stock_data.items():
        try:
            prompt = f"""
You are a quantitative stock analyst. Analyse the following technical data and provide a trading signal.

Ticker: {ticker}
Date: {data['date']}
Current Price: {data['price']}
RSI (14): {data['rsi']}
MACD: {data['macd']}
MACD Signal: {data['macd_signal']}
MACD Histogram: {data['macd_hist']}

Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{{
  "signal": "BUY" | "HOLD" | "SELL",
  "confidence": <integer 1-10>,
  "rationale": "<one or two sentences explaining the signal>"
}}
"""
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )

            raw = response.choices[0].message.content.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            parsed = json.loads(raw)
            signal = parsed.get("signal", "HOLD").upper()
            confidence = int(parsed.get("confidence", 5))
            rationale = parsed.get("rationale", "")

            # Clamp confidence
            confidence = max(1, min(10, confidence))

            cursor.execute("""
                INSERT INTO stock_signals (ticker, date, signal, confidence, rationale, rsi, macd, price)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (ticker, run_date, signal, confidence, rationale,
                  data.get("rsi"), data.get("macd"), data.get("price")))

            print(f"[OK] {ticker}: {signal} (confidence {confidence}/10)")

        except Exception as exc:
            print(f"[ERROR] {ticker} LLM analysis failed: {exc}")
            db_conn.rollback()

    db_conn.commit()
    cursor.close()
    db_conn.close()
    print("All signals committed to PostgreSQL.")


# ---------------------------------------------------------------------------
# Task 3: Send Telegram alerts
# ---------------------------------------------------------------------------
def send_alerts(**context) -> None:
    """Read signals from PostgreSQL and send a morning report via Telegram."""
    import asyncio

    import psycopg2
    from telegram import Bot

    run_date = context["ds"]

    telegram_token = _get_config("TELEGRAM_BOT_TOKEN", "telegram_bot_token")
    telegram_chat_id = _get_config("TELEGRAM_CHAT_ID", "telegram_chat_id")

    if not telegram_token or not telegram_chat_id:
        print("[WARN] Telegram credentials not configured. Skipping alerts.")
        return

    db_conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="ai_pipeline",
        user="aiuser",
        password="aipassword",
    )
    cursor = db_conn.cursor()

    cursor.execute("""
        SELECT ticker, signal, confidence, rationale, rsi, macd, price
        FROM stock_signals
        WHERE date = %s
        ORDER BY confidence DESC;
    """, (run_date,))

    rows = cursor.fetchall()
    cursor.close()
    db_conn.close()

    if not rows:
        print("[INFO] No signals found for today. Skipping Telegram message.")
        return

    buy_signals = [r for r in rows if r[1] == "BUY"]

    if not buy_signals:
        print("[INFO] No BUY signals today. Skipping Telegram message.")
        return

    # Build message
    lines = [
        f"📈 *Morning Market Report — {run_date}*",
        "",
        f"✅ BUY Signals ({len(buy_signals)}):",
    ]
    for ticker, signal, conf, rationale, rsi, macd, price in buy_signals:
        lines.append(
            f"\n*{ticker}* @ ${price:.2f}\n"
            f"  Confidence: {conf}/10 | RSI: {rsi} | MACD: {macd:.4f}\n"
            f"  _{rationale}_"
        )

    hold_sell = [r for r in rows if r[1] != "BUY"]
    if hold_sell:
        lines.append("\n⚠️ Other signals:")
        for ticker, signal, conf, *_ in hold_sell:
            lines.append(f"  {ticker}: {signal} ({conf}/10)")

    message = "\n".join(lines)

    async def _send():
        bot = Bot(token=telegram_token)
        await bot.send_message(
            chat_id=telegram_chat_id,
            text=message,
            parse_mode="Markdown",
        )

    asyncio.run(_send())
    print(f"Telegram alert sent. {len(buy_signals)} BUY signal(s) reported.")


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="stock_market_pipeline",
    description="Fetch US+India stock data, analyse with Groq LLM, send Telegram alerts",
    default_args=default_args,
    schedule_interval="0 6 * * 1-5",  # Mon–Fri at 06:00 UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["stock", "llm", "groq", "telegram"],
) as dag:

    t1_fetch = PythonOperator(
        task_id="fetch_stock_data",
        python_callable=fetch_stock_data,
    )

    t2_analyse = PythonOperator(
        task_id="analyze_with_llm",
        python_callable=analyze_with_llm,
    )

    t3_alert = PythonOperator(
        task_id="send_alerts",
        python_callable=send_alerts,
    )

    t1_fetch >> t2_analyse >> t3_alert
