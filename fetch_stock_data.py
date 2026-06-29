"""
fetch_stock_data.py
====================
Step 1 – Retrieve price data for two stocks and build DataFrames.

Replace TICKER_1 / TICKER_2 with the actual ticker symbols you want to analyse
(e.g. "AAPL", "TSLA", "NVDA", "MSFT", …).

Free-tier limitations (yfinance / Yahoo Finance)
-------------------------------------------------
| Interval | Max lookback |
|----------|--------------|
| 1s       | Not supported by Yahoo Finance                     |
| 1m       | ~7 calendar days                                   |
| 2m       | ~60 calendar days                                  |
| 5m       | ~60 calendar days                                  |
| 15m      | ~60 calendar days                                  |
| 30m      | ~60 calendar days                                  |
| 1h       | ~730 days (2 years)                                |
| 1d       | Full history (20+ years)                           |

For 4 years of minute / second level data you need a paid provider such as:
  • Polygon.io  – https://polygon.io
  • Alpaca      – https://alpaca.markets
  • Interactive Brokers historical data API
  • Bloomberg / Refinitiv (institutional)

This script downloads everything that is freely available and shows you exactly
how to swap in a Polygon.io call to get the full 4-year minute series.
"""

import datetime
import time

import pandas as pd
import yfinance as yf

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION – change these values
# ──────────────────────────────────────────────────────────────────────────────
TICKER_1 = "AAPL"   # <-- replace with your first stock ticker
TICKER_2 = "NVDA"   # <-- replace with your second stock ticker

END_DATE   = datetime.date.today()
START_DATE = END_DATE - datetime.timedelta(days=4 * 365)   # approx 4 years ago

print(f"Tickers : {TICKER_1}, {TICKER_2}")
print(f"Period  : {START_DATE}  →  {END_DATE}\n")


# ──────────────────────────────────────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────────────────────────────────────
def _clean(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Flatten multi-level columns, ensure DatetimeIndex, sort, drop NaN rows."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    df.dropna(how="all", inplace=True)
    df.name = ticker
    return df


def _describe(df: pd.DataFrame, label: str) -> str:
    """Return a one-line description; handles empty DataFrames gracefully."""
    if df.empty:
        return f"{label}: NO DATA (network error or outside provider lookback window)"
    return (
        f"{label}: {len(df):,} rows  "
        f"({df.index[0]} → {df.index[-1]})"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 1.  DAILY DATA  –  4 years, full OHLCV + Adjusted Close
# ──────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("Downloading DAILY data (4 years) …")
print("=" * 60)

raw1_daily = yf.download(
    TICKER_1,
    start=START_DATE.isoformat(),
    end=END_DATE.isoformat(),
    interval="1d",
    auto_adjust=True,   # prices already adjusted for splits/dividends
    progress=False,
)
raw2_daily = yf.download(
    TICKER_2,
    start=START_DATE.isoformat(),
    end=END_DATE.isoformat(),
    interval="1d",
    auto_adjust=True,
    progress=False,
)

df1_daily = _clean(raw1_daily, TICKER_1)
df2_daily = _clean(raw2_daily, TICKER_2)

print(f"\n{_describe(df1_daily, TICKER_1 + ' daily')}")
if not df1_daily.empty:
    print(df1_daily.tail(3))

print(f"\n{_describe(df2_daily, TICKER_2 + ' daily')}")
if not df2_daily.empty:
    print(df2_daily.tail(3))


# ──────────────────────────────────────────────────────────────────────────────
# 2.  HOURLY DATA  –  up to ~730 days (free Yahoo Finance limit)
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Downloading HOURLY data (up to ~2 years) …")
print("=" * 60)

hourly_start = END_DATE - datetime.timedelta(days=729)

raw1_hourly = yf.download(
    TICKER_1,
    start=hourly_start.isoformat(),
    end=END_DATE.isoformat(),
    interval="1h",
    auto_adjust=True,
    progress=False,
)
raw2_hourly = yf.download(
    TICKER_2,
    start=hourly_start.isoformat(),
    end=END_DATE.isoformat(),
    interval="1h",
    auto_adjust=True,
    progress=False,
)

df1_hourly = _clean(raw1_hourly, TICKER_1)
df2_hourly = _clean(raw2_hourly, TICKER_2)

print(f"\n{_describe(df1_hourly, TICKER_1 + ' hourly')}")
print(_describe(df2_hourly, TICKER_2 + ' hourly'))


# ──────────────────────────────────────────────────────────────────────────────
# 3.  5-MINUTE DATA  –  last 60 calendar days (free Yahoo Finance limit)
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Downloading 5-MINUTE data (last ~60 days) …")
print("=" * 60)

five_min_start = END_DATE - datetime.timedelta(days=59)

raw1_5m = yf.download(
    TICKER_1,
    start=five_min_start.isoformat(),
    end=END_DATE.isoformat(),
    interval="5m",
    auto_adjust=True,
    progress=False,
)
raw2_5m = yf.download(
    TICKER_2,
    start=five_min_start.isoformat(),
    end=END_DATE.isoformat(),
    interval="5m",
    auto_adjust=True,
    progress=False,
)

df1_5m = _clean(raw1_5m, TICKER_1)
df2_5m = _clean(raw2_5m, TICKER_2)

print(f"\n{_describe(df1_5m, TICKER_1 + ' 5-min')}")
print(_describe(df2_5m, TICKER_2 + ' 5-min'))


# ──────────────────────────────────────────────────────────────────────────────
# 4.  1-MINUTE DATA  –  last 7 calendar days (free Yahoo Finance limit)
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Downloading 1-MINUTE data (last ~7 days) …")
print("=" * 60)

one_min_start = END_DATE - datetime.timedelta(days=6)

raw1_1m = yf.download(
    TICKER_1,
    start=one_min_start.isoformat(),
    end=END_DATE.isoformat(),
    interval="1m",
    auto_adjust=True,
    progress=False,
)
raw2_1m = yf.download(
    TICKER_2,
    start=one_min_start.isoformat(),
    end=END_DATE.isoformat(),
    interval="1m",
    auto_adjust=True,
    progress=False,
)

df1_1m = _clean(raw1_1m, TICKER_1)
df2_1m = _clean(raw2_1m, TICKER_2)

print(f"\n{_describe(df1_1m, TICKER_1 + ' 1-min')}")
print(_describe(df2_1m, TICKER_2 + ' 1-min'))


# ──────────────────────────────────────────────────────────────────────────────
# 5.  OPTIONAL: Polygon.io – 4 years of 1-minute data  (paid, free tier = 2yr)
#     Uncomment and set POLYGON_API_KEY to use.
# ──────────────────────────────────────────────────────────────────────────────
# import requests
#
# POLYGON_API_KEY = "YOUR_KEY_HERE"
#
# def fetch_polygon_aggs(ticker, from_date, to_date, timespan="minute",
#                        multiplier=1, limit=50000):
#     """
#     Fetch aggregate bars from Polygon.io for the full requested range,
#     paginating automatically.  Returns a tidy DataFrame.
#     """
#     url = (
#         f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/"
#         f"{multiplier}/{timespan}/"
#         f"{from_date}/{to_date}"
#     )
#     params = {
#         "adjusted": "true",
#         "sort": "asc",
#         "limit": limit,
#         "apiKey": POLYGON_API_KEY,
#     }
#     rows = []
#     while url:
#         r = requests.get(url, params=params)
#         r.raise_for_status()
#         data = r.json()
#         rows.extend(data.get("results", []))
#         url = data.get("next_url")   # pagination
#         params = {"apiKey": POLYGON_API_KEY}
#         time.sleep(0.2)              # respect rate limit
#
#     df = pd.DataFrame(rows)
#     df["timestamp"] = pd.to_datetime(df["t"], unit="ms", utc=True)
#     df = df.rename(columns={
#         "o": "Open", "h": "High", "l": "Low", "c": "Close",
#         "v": "Volume", "vw": "VWAP", "n": "Transactions",
#     })
#     df.set_index("timestamp", inplace=True)
#     df.drop(columns=["t"], inplace=True)
#     df.sort_index(inplace=True)
#     return df
#
# df1_1m_full = fetch_polygon_aggs(TICKER_1, START_DATE, END_DATE)
# df2_1m_full = fetch_polygon_aggs(TICKER_2, START_DATE, END_DATE)
# print(f"{TICKER_1} Polygon 1-min: {len(df1_1m_full):,} rows")
# print(f"{TICKER_2} Polygon 1-min: {len(df2_1m_full):,} rows")


# ──────────────────────────────────────────────────────────────────────────────
# 6.  SUMMARY – the two "primary" DataFrames for downstream analysis
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("PRIMARY DataFrames available for analysis:")
print("=" * 60)
def _row(name, df, label):
    return f"  {name:<12} – {_describe(df, label)}"

print(f"""
{_row('df1_daily',  df1_daily,  TICKER_1 + ' daily OHLCV, 4 years')}
{_row('df2_daily',  df2_daily,  TICKER_2 + ' daily OHLCV, 4 years')}

{_row('df1_hourly', df1_hourly, TICKER_1 + ' hourly OHLCV, ~2 years')}
{_row('df2_hourly', df2_hourly, TICKER_2 + ' hourly OHLCV, ~2 years')}

{_row('df1_5m',     df1_5m,     TICKER_1 + ' 5-min OHLCV, last ~60 days')}
{_row('df2_5m',     df2_5m,     TICKER_2 + ' 5-min OHLCV, last ~60 days')}

{_row('df1_1m',     df1_1m,     TICKER_1 + ' 1-min OHLCV, last ~7 days')}
{_row('df2_1m',     df2_1m,     TICKER_2 + ' 1-min OHLCV, last ~7 days')}

  Note: for 4 years of 1-minute data uncomment the Polygon.io section above.
""")

# Optional: save to CSV / Parquet for offline use
# df1_daily.to_csv(f"{TICKER_1}_daily.csv")
# df2_daily.to_csv(f"{TICKER_2}_daily.csv")
# df1_1m.to_parquet(f"{TICKER_1}_1m.parquet")
# df2_1m.to_parquet(f"{TICKER_2}_1m.parquet")
