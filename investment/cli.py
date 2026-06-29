"""Command-line interface for the personal investment framework."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from .analytics import (
    allocation_breakdown,
    holding_snapshots,
    portfolio_return,
    rebalance_suggestions,
)
from .models import Asset, AssetType, TargetAllocation
from .portfolio import Portfolio

_DEFAULT_DATA_FILE = Path.home() / ".investment" / "portfolio.json"


# ------------------------------------------------------------------ #
# Formatting helpers
# ------------------------------------------------------------------ #

def _fmt(value: Decimal, decimals: int = 2, prefix: str = "$") -> str:
    return f"{prefix}{value:,.{decimals}f}"


def _pct(value: Optional[Decimal], decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def _parse_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation:
        print(f"Error: '{value}' is not a valid number for {field}.", file=sys.stderr)
        sys.exit(1)


def _load_portfolio(path: Path) -> Portfolio:
    if not path.exists():
        print(f"Error: portfolio file not found at {path}.", file=sys.stderr)
        print("Run 'invest init' to create a new portfolio.", file=sys.stderr)
        sys.exit(1)
    return Portfolio.load(path)


# ------------------------------------------------------------------ #
# Sub-command handlers
# ------------------------------------------------------------------ #

def cmd_init(args: argparse.Namespace) -> None:
    path = Path(args.file)
    if path.exists():
        print(f"Portfolio file already exists at {path}.")
        return
    portfolio = Portfolio(name=args.name)
    portfolio.save(path)
    print(f"Created new portfolio '{args.name}' at {path}.")


def cmd_add_asset(args: argparse.Namespace) -> None:
    path = Path(args.file)
    portfolio = _load_portfolio(path)
    try:
        asset_type = AssetType(args.asset_type.lower())
    except ValueError:
        valid = [t.value for t in AssetType]
        print(f"Error: invalid asset type '{args.asset_type}'. Choose from: {valid}", file=sys.stderr)
        sys.exit(1)

    asset = Asset(
        symbol=args.symbol.upper(),
        name=args.name,
        asset_type=asset_type,
        currency=args.currency.upper(),
    )
    portfolio.add_asset(asset)
    portfolio.save(path)
    print(f"Added asset {asset.symbol} ({asset.name}) [{asset.asset_type.value}].")


def cmd_deposit(args: argparse.Namespace) -> None:
    path = Path(args.file)
    portfolio = _load_portfolio(path)
    amount = _parse_decimal(args.amount, "amount")
    txn_date = date.fromisoformat(args.date) if args.date else date.today()
    portfolio.deposit(amount, txn_date=txn_date, notes=args.notes or "")
    portfolio.save(path)
    print(f"Deposited {_fmt(amount)}. Cash balance: {_fmt(portfolio.cash_balance)}.")


def cmd_withdraw(args: argparse.Namespace) -> None:
    path = Path(args.file)
    portfolio = _load_portfolio(path)
    amount = _parse_decimal(args.amount, "amount")
    txn_date = date.fromisoformat(args.date) if args.date else date.today()
    try:
        portfolio.withdraw(amount, txn_date=txn_date, notes=args.notes or "")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    portfolio.save(path)
    print(f"Withdrew {_fmt(amount)}. Cash balance: {_fmt(portfolio.cash_balance)}.")


def cmd_buy(args: argparse.Namespace) -> None:
    path = Path(args.file)
    portfolio = _load_portfolio(path)
    qty = _parse_decimal(args.quantity, "quantity")
    price = _parse_decimal(args.price, "price")
    fees = _parse_decimal(args.fees, "fees") if args.fees else Decimal("0")
    txn_date = date.fromisoformat(args.date) if args.date else date.today()
    try:
        txn = portfolio.buy(
            symbol=args.symbol.upper(),
            quantity=qty,
            price=price,
            txn_date=txn_date,
            fees=fees,
            notes=args.notes or "",
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    portfolio.save(path)
    total = qty * price + fees
    print(f"Bought {qty} {args.symbol.upper()} @ {_fmt(price)} (fees {_fmt(fees)}) = {_fmt(total)}.")
    print(f"Cash balance: {_fmt(portfolio.cash_balance)}.")


def cmd_sell(args: argparse.Namespace) -> None:
    path = Path(args.file)
    portfolio = _load_portfolio(path)
    qty = _parse_decimal(args.quantity, "quantity")
    price = _parse_decimal(args.price, "price")
    fees = _parse_decimal(args.fees, "fees") if args.fees else Decimal("0")
    txn_date = date.fromisoformat(args.date) if args.date else date.today()
    try:
        portfolio.sell(
            symbol=args.symbol.upper(),
            quantity=qty,
            price=price,
            txn_date=txn_date,
            fees=fees,
            notes=args.notes or "",
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    portfolio.save(path)
    proceeds = qty * price - fees
    print(f"Sold {qty} {args.symbol.upper()} @ {_fmt(price)} (fees {_fmt(fees)}) = {_fmt(proceeds)} proceeds.")
    print(f"Cash balance: {_fmt(portfolio.cash_balance)}.")


def cmd_dividend(args: argparse.Namespace) -> None:
    path = Path(args.file)
    portfolio = _load_portfolio(path)
    amount_per_share = _parse_decimal(args.amount_per_share, "amount_per_share")
    txn_date = date.fromisoformat(args.date) if args.date else date.today()
    try:
        portfolio.record_dividend(
            symbol=args.symbol.upper(),
            amount_per_share=amount_per_share,
            txn_date=txn_date,
            notes=args.notes or "",
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    portfolio.save(path)
    holding = portfolio.holdings.get(args.symbol.upper())
    if holding:
        total = holding.quantity * amount_per_share
        print(f"Recorded dividend for {args.symbol.upper()}: {_fmt(amount_per_share)}/share × {holding.quantity} = {_fmt(total)}.")


def cmd_status(args: argparse.Namespace) -> None:
    path = Path(args.file)
    portfolio = _load_portfolio(path)

    if not args.prices and not portfolio.holdings:
        print(f"Portfolio: {portfolio.name}")
        print(f"  Cash: {_fmt(portfolio.cash_balance)}")
        print("  No holdings.")
        return

    prices = {}
    if args.prices:
        for pair in args.prices:
            symbol, price_str = pair.split("=", 1)
            prices[symbol.upper()] = _parse_decimal(price_str, f"price for {symbol}")

    missing = [s for s in portfolio.holdings if s not in prices]
    if missing:
        print(f"Error: no price provided for: {', '.join(missing)}", file=sys.stderr)
        print("Use --price SYMBOL=PRICE to supply current prices.", file=sys.stderr)
        sys.exit(1)

    metrics = portfolio_return(portfolio, prices)
    snapshots = holding_snapshots(portfolio, prices)

    print(f"\n{'=' * 60}")
    print(f"  Portfolio: {portfolio.name}")
    print(f"{'=' * 60}")
    print(f"  Total value:    {_fmt(metrics['total_value'])}")
    print(f"  Total invested: {_fmt(metrics['total_invested'])}")
    print(f"  Total gain:     {_fmt(metrics['total_gain'])}  ({_pct(metrics['total_return_pct'])})")
    print(f"  Cash balance:   {_fmt(portfolio.cash_balance)}")
    print(f"{'=' * 60}")

    if snapshots:
        print(f"\n  {'Symbol':<8} {'Qty':>10} {'Avg Cost':>10} {'Price':>10} {'Value':>12} {'Gain':>12} {'Gain%':>8} {'Weight':>7}")
        print(f"  {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*12} {'-'*12} {'-'*8} {'-'*7}")
        for s in snapshots:
            print(
                f"  {s.symbol:<8} {s.quantity:>10} "
                f"{_fmt(s.average_cost):>10} {_fmt(s.current_price):>10} "
                f"{_fmt(s.current_value):>12} {_fmt(s.unrealized_gain):>12} "
                f"{_pct(s.unrealized_gain_pct):>8} {_pct(s.portfolio_weight_pct):>7}"
            )

    print()


def cmd_allocations(args: argparse.Namespace) -> None:
    path = Path(args.file)
    portfolio = _load_portfolio(path)

    prices = {}
    if args.prices:
        for pair in args.prices:
            symbol, price_str = pair.split("=", 1)
            prices[symbol.upper()] = _parse_decimal(price_str, f"price for {symbol}")

    missing = [s for s in portfolio.holdings if s not in prices]
    if missing:
        print(f"Error: no price provided for: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    breakdown = allocation_breakdown(portfolio, prices)

    print(f"\n  {'Asset Type':<16} {'Value':>12} {'Current%':>10} {'Target%':>10} {'Drift':>8}")
    print(f"  {'-'*16} {'-'*12} {'-'*10} {'-'*10} {'-'*8}")
    for alloc in breakdown:
        target_str = _pct(alloc.target_pct) if alloc.target_pct is not None else "  N/A"
        drift_str = _pct(alloc.drift_pct) if alloc.drift_pct is not None else "  N/A"
        print(
            f"  {alloc.asset_type.value:<16} {_fmt(alloc.current_value):>12} "
            f"{_pct(alloc.current_pct):>10} {target_str:>10} {drift_str:>8}"
        )
    print()


def cmd_rebalance(args: argparse.Namespace) -> None:
    path = Path(args.file)
    portfolio = _load_portfolio(path)

    prices = {}
    if args.prices:
        for pair in args.prices:
            symbol, price_str = pair.split("=", 1)
            prices[symbol.upper()] = _parse_decimal(price_str, f"price for {symbol}")

    missing = [s for s in portfolio.holdings if s not in prices]
    if missing:
        print(f"Error: no price provided for: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    threshold = _parse_decimal(args.threshold, "threshold") if args.threshold else Decimal("5")
    suggestions = rebalance_suggestions(portfolio, prices, threshold_pct=threshold)

    if not suggestions:
        print("Portfolio is within target allocation bands. No rebalancing needed.")
        return

    print(f"\n  Rebalancing suggestions (threshold: {_pct(threshold)}):")
    print(f"\n  {'Symbol':<12} {'Action':<6} {'Value':>12} {'Current%':>10} {'Target%':>10}")
    print(f"  {'-'*12} {'-'*6} {'-'*12} {'-'*10} {'-'*10}")
    for s in suggestions:
        print(
            f"  {s.symbol:<12} {s.action:<6} {_fmt(s.suggested_value):>12} "
            f"{_pct(s.current_weight_pct):>10} {_pct(s.target_weight_pct):>10}"
        )
    print()


def cmd_history(args: argparse.Namespace) -> None:
    path = Path(args.file)
    portfolio = _load_portfolio(path)
    txns = portfolio.get_transactions(
        symbol=args.symbol.upper() if args.symbol else None,
    )
    if not txns:
        print("No transactions found.")
        return

    print(f"\n  {'Date':<12} {'Type':<12} {'Symbol':<8} {'Qty':>10} {'Price':>10} {'Fees':>8}")
    print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*10} {'-'*10} {'-'*8}")
    for t in txns:
        print(
            f"  {t.transaction_date.isoformat():<12} {t.transaction_type.value:<12} "
            f"{t.symbol:<8} {t.quantity:>10} {_fmt(t.price):>10} {_fmt(t.fees):>8}"
        )
    print()


def cmd_set_target(args: argparse.Namespace) -> None:
    """Set target allocation from --allocation TYPE=PCT pairs."""
    path = Path(args.file)
    portfolio = _load_portfolio(path)
    allocations = []
    for pair in args.allocation:
        atype_str, pct_str = pair.split("=", 1)
        try:
            atype = AssetType(atype_str.lower())
        except ValueError:
            valid = [t.value for t in AssetType]
            print(f"Error: unknown asset type '{atype_str}'. Choose from: {valid}", file=sys.stderr)
            sys.exit(1)
        pct = _parse_decimal(pct_str, f"percentage for {atype_str}")
        allocations.append(TargetAllocation(asset_type=atype, target_pct=pct))
    try:
        portfolio.set_target_allocations(allocations)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    portfolio.save(path)
    print("Target allocations updated:")
    for ta in portfolio.target_allocations:
        print(f"  {ta.asset_type.value}: {ta.target_pct}%")


# ------------------------------------------------------------------ #
# Argument parser
# ------------------------------------------------------------------ #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="invest",
        description="Personal Investment Framework — manage your portfolio from the command line.",
    )
    parser.add_argument(
        "--file", "-f",
        default=str(_DEFAULT_DATA_FILE),
        help=f"Path to portfolio JSON file (default: {_DEFAULT_DATA_FILE})",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # init
    p = sub.add_parser("init", help="Create a new portfolio file.")
    p.add_argument("--name", default="My Portfolio", help="Portfolio name.")
    p.set_defaults(func=cmd_init)

    # add-asset
    p = sub.add_parser("add-asset", help="Register an asset in the portfolio.")
    p.add_argument("symbol", help="Ticker symbol (e.g. AAPL).")
    p.add_argument("name", help="Full name of the asset.")
    p.add_argument("asset_type", help=f"Asset type: {[t.value for t in AssetType]}.")
    p.add_argument("--currency", default="USD", help="Currency (default: USD).")
    p.set_defaults(func=cmd_add_asset)

    # deposit
    p = sub.add_parser("deposit", help="Deposit cash into the portfolio.")
    p.add_argument("amount", help="Amount to deposit.")
    p.add_argument("--date", help="Transaction date (YYYY-MM-DD).")
    p.add_argument("--notes", help="Optional notes.")
    p.set_defaults(func=cmd_deposit)

    # withdraw
    p = sub.add_parser("withdraw", help="Withdraw cash from the portfolio.")
    p.add_argument("amount", help="Amount to withdraw.")
    p.add_argument("--date", help="Transaction date (YYYY-MM-DD).")
    p.add_argument("--notes", help="Optional notes.")
    p.set_defaults(func=cmd_withdraw)

    # buy
    p = sub.add_parser("buy", help="Buy shares of an asset.")
    p.add_argument("symbol", help="Ticker symbol.")
    p.add_argument("quantity", help="Number of shares.")
    p.add_argument("price", help="Price per share.")
    p.add_argument("--fees", help="Transaction fees.")
    p.add_argument("--date", help="Transaction date (YYYY-MM-DD).")
    p.add_argument("--notes", help="Optional notes.")
    p.set_defaults(func=cmd_buy)

    # sell
    p = sub.add_parser("sell", help="Sell shares of an asset.")
    p.add_argument("symbol", help="Ticker symbol.")
    p.add_argument("quantity", help="Number of shares.")
    p.add_argument("price", help="Price per share.")
    p.add_argument("--fees", help="Transaction fees.")
    p.add_argument("--date", help="Transaction date (YYYY-MM-DD).")
    p.add_argument("--notes", help="Optional notes.")
    p.set_defaults(func=cmd_sell)

    # dividend
    p = sub.add_parser("dividend", help="Record a dividend payment.")
    p.add_argument("symbol", help="Ticker symbol.")
    p.add_argument("amount_per_share", help="Dividend per share.")
    p.add_argument("--date", help="Transaction date (YYYY-MM-DD).")
    p.add_argument("--notes", help="Optional notes.")
    p.set_defaults(func=cmd_dividend)

    # status
    p = sub.add_parser("status", help="Show portfolio status and performance.")
    p.add_argument(
        "--price", "-p", dest="prices", action="append", metavar="SYMBOL=PRICE",
        help="Current price for an asset (repeat for each holding).",
    )
    p.set_defaults(func=cmd_status)

    # allocations
    p = sub.add_parser("allocations", help="Show allocation by asset type.")
    p.add_argument(
        "--price", "-p", dest="prices", action="append", metavar="SYMBOL=PRICE",
        help="Current price for an asset (repeat for each holding).",
    )
    p.set_defaults(func=cmd_allocations)

    # rebalance
    p = sub.add_parser("rebalance", help="Show rebalancing suggestions.")
    p.add_argument(
        "--price", "-p", dest="prices", action="append", metavar="SYMBOL=PRICE",
        help="Current price for an asset (repeat for each holding).",
    )
    p.add_argument("--threshold", default="5", help="Drift threshold % (default: 5).")
    p.set_defaults(func=cmd_rebalance)

    # history
    p = sub.add_parser("history", help="Show transaction history.")
    p.add_argument("--symbol", help="Filter by asset symbol.")
    p.set_defaults(func=cmd_history)

    # set-target
    p = sub.add_parser("set-target", help="Set target allocations for rebalancing.")
    p.add_argument(
        "allocation", nargs="+", metavar="TYPE=PCT",
        help="Asset type and target percentage, e.g. stock=60 bond=30 cash=10.",
    )
    p.set_defaults(func=cmd_set_target)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
