# Personal Investment Framework

A lightweight, zero-dependency Python framework for managing your personal investment portfolio from the command line.

## Features

- **Portfolio management** — deposit/withdraw cash, buy/sell assets, record dividends
- **Holdings tracking** — average cost basis, unrealized gains/losses per position
- **Allocation analysis** — current allocation by asset type vs your targets
- **Rebalancing suggestions** — automatically identify positions that have drifted beyond a configurable threshold
- **JSON persistence** — your portfolio is saved in a plain JSON file that you can inspect, back up, or sync
- **Pure Python** — no third-party runtime dependencies

## Supported asset types

`stock`, `etf`, `bond`, `crypto`, `cash`, `real_estate`, `commodity`, `other`

## Installation

```bash
pip install -e .
```

This installs the `invest` CLI command.

## Quick start

```bash
# Create a new portfolio
invest init --name "My Portfolio"

# Register the assets you trade
invest add-asset AAPL "Apple Inc." stock
invest add-asset BND  "Vanguard Total Bond ETF" bond
invest add-asset BTC  "Bitcoin" crypto

# Fund the portfolio
invest deposit 50000

# Buy assets
invest buy AAPL 20 180.00 --fees 1.00
invest buy BND  100 75.00 --fees 0.50
invest buy BTC  0.5 42000 --fees 25.00

# Set target allocation for rebalancing
invest set-target stock=50 bond=30 crypto=10 cash=10

# Record a dividend
invest dividend AAPL 0.24

# Check portfolio status (supply current prices)
invest status --price AAPL=190 --price BND=74 --price BTC=48000

# View allocation breakdown vs targets
invest allocations --price AAPL=190 --price BND=74 --price BTC=48000

# Get rebalancing suggestions (default 5% drift threshold)
invest rebalance --price AAPL=190 --price BND=74 --price BTC=48000 --threshold 5

# Browse transaction history
invest history
invest history --symbol AAPL
```

## Portfolio file location

By default the portfolio is stored at `~/.investment/portfolio.json`. Use `--file` / `-f` to specify a different path:

```bash
invest --file ~/portfolios/retirement.json status --price ...
```

## Python API

You can also use the framework programmatically:

```python
from decimal import Decimal
from investment import Portfolio, Asset, AssetType, TargetAllocation
from investment import holding_snapshots, allocation_breakdown, rebalance_suggestions

# Build a portfolio
p = Portfolio(name="My Portfolio")
p.add_asset(Asset("AAPL", "Apple Inc.", AssetType.STOCK))
p.deposit(Decimal("10000"))
p.buy("AAPL", Decimal("10"), Decimal("180"))

# Analyse it
prices = {"AAPL": Decimal("200")}
for snap in holding_snapshots(p, prices):
    print(snap.symbol, snap.unrealized_gain, snap.unrealized_gain_pct)

# Persist
from pathlib import Path
p.save(Path("portfolio.json"))
p2 = Portfolio.load(Path("portfolio.json"))
```

## Running tests

```bash
pip install pytest
pytest
```

## Project structure

```
investment/
    __init__.py      # public API
    models.py        # data classes: Asset, Transaction, Holding, TargetAllocation
    portfolio.py     # Portfolio manager (buy/sell/deposit/withdraw/persist)
    analytics.py     # metrics, allocation breakdown, rebalancing suggestions
    cli.py           # `invest` command-line interface
tests/
    test_models.py
    test_portfolio.py
    test_analytics.py
pyproject.toml
requirements.txt
```