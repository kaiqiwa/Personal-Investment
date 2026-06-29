"""
Stock Price Data Retrieval
==========================
Retrieves historical OHLCV price data for two stocks using yfinance (Yahoo Finance).

Data availability limitations (Yahoo Finance API):
  - "1d" (daily)  : up to 10 years       ✅  best for 4-year analysis
  - "1h" (hourly) : up to ~730 days (2yr) ⚠️  only covers last 2 years
  - "1m" (minute) : last 60 days only     ❌  cannot cover 4 years via free API

  For true minute-level data over 4 years a paid data provider is required
  (e.g. Polygon.io, Alpaca Markets, Interactive Brokers).  This script uses the
  INTERVAL variable to let you switch between resolutions easily.

Usage:
    pip install -r requirements.txt
    python data_retrieval.py

Output:
    df_stock1  – DataFrame for TICKER_1
    df_stock2  – DataFrame for TICKER_2
    Both DataFrames have columns: Open, High, Low, Close, Volume
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ── Configuration ─────────────────────────────────────────────────────────────

TICKER_1 = "AAPL"   # ← change to your first stock symbol
TICKER_2 = "TSLA"   # ← change to your second stock symbol

# Choose one of: "1m", "2m", "5m", "15m", "30m", "60m", "1h", "1d", "1wk"
# See header docstring for availability limits.
INTERVAL = "1d"     # daily data gives the full 4-year window cleanly

YEARS_BACK = 4

# ── Date range ────────────────────────────────────────────────────────────────

end_date   = datetime.today()
start_date = end_date - timedelta(days=365 * YEARS_BACK)

# yfinance accepts strings in "YYYY-MM-DD" format
start_str = start_date.strftime("%Y-%m-%d")
end_str   = end_date.strftime("%Y-%m-%d")

print(f"Fetching {INTERVAL} data from {start_str} to {end_str}")
print(f"  Stock 1: {TICKER_1}")
print(f"  Stock 2: {TICKER_2}\n")

# ── Download ──────────────────────────────────────────────────────────────────

def fetch_stock_data(ticker: str, start: str, end: str, interval: str) -> pd.DataFrame:
    """Download OHLCV data for a single ticker and return a clean DataFrame."""
    raw = yf.download(
        tickers=ticker,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=True,   # adjusts for splits & dividends automatically
        progress=False,
    )

    if raw.empty:
        raise ValueError(
            f"No data returned for {ticker}. "
            "Check the ticker symbol and the interval/date-range limits."
        )

    # Flatten MultiIndex columns that yfinance sometimes produces
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    # Keep only the standard OHLCV columns
    columns_to_keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    df = raw[columns_to_keep].copy()

    df.index.name = "Datetime"
    df["Ticker"] = ticker
    return df


df_stock1 = fetch_stock_data(TICKER_1, start_str, end_str, INTERVAL)
df_stock2 = fetch_stock_data(TICKER_2, start_str, end_str, INTERVAL)

# ── Summary ───────────────────────────────────────────────────────────────────

for label, df, ticker in [
    ("df_stock1", df_stock1, TICKER_1),
    ("df_stock2", df_stock2, TICKER_2),
]:
    print(f"{'─'*50}")
    print(f"{label}  ({ticker})")
    print(f"  Rows      : {len(df):,}")
    print(f"  Date range: {df.index[0]}  →  {df.index[-1]}")
    print(f"  Columns   : {list(df.columns)}")
    print(df.tail(3).to_string())
    print()

# ── Optional: save to CSV ─────────────────────────────────────────────────────

df_stock1.to_csv(f"{TICKER_1}_price_data.csv")
df_stock2.to_csv(f"{TICKER_2}_price_data.csv")
print(f"Saved CSVs: {TICKER_1}_price_data.csv  |  {TICKER_2}_price_data.csv")
