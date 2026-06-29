"""Portfolio manager: handles all portfolio operations and persistence."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    Asset,
    AssetType,
    Holding,
    TargetAllocation,
    Transaction,
    TransactionType,
)

_PORTFOLIO_SCHEMA_VERSION = 1


class Portfolio:
    """
    Manages a personal investment portfolio.

    Supports buying and selling assets, tracking holdings, recording dividends,
    managing cash deposits/withdrawals, and persisting state to JSON.
    """

    def __init__(self, name: str = "My Portfolio") -> None:
        self.name = name
        self.assets: Dict[str, Asset] = {}
        self.holdings: Dict[str, Holding] = {}
        self.transactions: List[Transaction] = []
        self.target_allocations: List[TargetAllocation] = []
        self.cash_balance: Decimal = Decimal("0")

    # ------------------------------------------------------------------ #
    # Asset registry
    # ------------------------------------------------------------------ #

    def add_asset(self, asset: Asset) -> None:
        """Register an asset definition."""
        self.assets[asset.symbol] = asset

    def get_asset(self, symbol: str) -> Optional[Asset]:
        return self.assets.get(symbol.upper())

    # ------------------------------------------------------------------ #
    # Cash operations
    # ------------------------------------------------------------------ #

    def deposit(self, amount: Decimal, txn_date: Optional[date] = None, notes: str = "") -> Transaction:
        """Deposit cash into the portfolio."""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        txn = Transaction(
            transaction_id=str(uuid.uuid4()),
            transaction_type=TransactionType.DEPOSIT,
            symbol="CASH",
            quantity=amount,
            price=Decimal("1"),
            transaction_date=txn_date or date.today(),
            notes=notes,
        )
        self.cash_balance += amount
        self.transactions.append(txn)
        return txn

    def withdraw(self, amount: Decimal, txn_date: Optional[date] = None, notes: str = "") -> Transaction:
        """Withdraw cash from the portfolio."""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self.cash_balance:
            raise ValueError(f"Insufficient cash balance: have {self.cash_balance}, need {amount}")
        txn = Transaction(
            transaction_id=str(uuid.uuid4()),
            transaction_type=TransactionType.WITHDRAWAL,
            symbol="CASH",
            quantity=amount,
            price=Decimal("1"),
            transaction_date=txn_date or date.today(),
            notes=notes,
        )
        self.cash_balance -= amount
        self.transactions.append(txn)
        return txn

    # ------------------------------------------------------------------ #
    # Trading operations
    # ------------------------------------------------------------------ #

    def buy(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        txn_date: Optional[date] = None,
        fees: Decimal = Decimal("0"),
        notes: str = "",
    ) -> Transaction:
        """Purchase an asset."""
        symbol = symbol.upper()
        if symbol not in self.assets:
            raise ValueError(f"Unknown asset '{symbol}'. Register it with add_asset() first.")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if price < 0:
            raise ValueError("Price cannot be negative")

        total = quantity * price + fees
        if total > self.cash_balance:
            raise ValueError(
                f"Insufficient cash: need {total}, have {self.cash_balance}"
            )

        txn = Transaction(
            transaction_id=str(uuid.uuid4()),
            transaction_type=TransactionType.BUY,
            symbol=symbol,
            quantity=quantity,
            price=price,
            transaction_date=txn_date or date.today(),
            fees=fees,
            notes=notes,
        )

        self.cash_balance -= total
        self._update_holding_on_buy(symbol, quantity, price)
        self.transactions.append(txn)
        return txn

    def sell(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        txn_date: Optional[date] = None,
        fees: Decimal = Decimal("0"),
        notes: str = "",
    ) -> Transaction:
        """Sell an asset."""
        symbol = symbol.upper()
        if symbol not in self.holdings:
            raise ValueError(f"No holding found for '{symbol}'")
        holding = self.holdings[symbol]
        if quantity > holding.quantity:
            raise ValueError(
                f"Cannot sell {quantity} shares; only {holding.quantity} held"
            )
        if price < 0:
            raise ValueError("Price cannot be negative")

        proceeds = quantity * price - fees
        txn = Transaction(
            transaction_id=str(uuid.uuid4()),
            transaction_type=TransactionType.SELL,
            symbol=symbol,
            quantity=quantity,
            price=price,
            transaction_date=txn_date or date.today(),
            fees=fees,
            notes=notes,
        )

        self.cash_balance += proceeds
        self._update_holding_on_sell(symbol, quantity)
        self.transactions.append(txn)
        return txn

    def record_dividend(
        self,
        symbol: str,
        amount_per_share: Decimal,
        txn_date: Optional[date] = None,
        notes: str = "",
    ) -> Transaction:
        """Record a dividend payment for a held asset."""
        symbol = symbol.upper()
        if symbol not in self.holdings:
            raise ValueError(f"No holding found for '{symbol}'")
        holding = self.holdings[symbol]
        total_dividend = holding.quantity * amount_per_share

        txn = Transaction(
            transaction_id=str(uuid.uuid4()),
            transaction_type=TransactionType.DIVIDEND,
            symbol=symbol,
            quantity=holding.quantity,
            price=amount_per_share,
            transaction_date=txn_date or date.today(),
            notes=notes,
        )

        self.cash_balance += total_dividend
        self.transactions.append(txn)
        return txn

    # ------------------------------------------------------------------ #
    # Holdings internals
    # ------------------------------------------------------------------ #

    def _update_holding_on_buy(self, symbol: str, quantity: Decimal, price: Decimal) -> None:
        if symbol in self.holdings:
            existing = self.holdings[symbol]
            new_qty = existing.quantity + quantity
            new_avg = (existing.quantity * existing.average_cost + quantity * price) / new_qty
            self.holdings[symbol] = Holding(symbol=symbol, quantity=new_qty, average_cost=new_avg)
        else:
            self.holdings[symbol] = Holding(symbol=symbol, quantity=quantity, average_cost=price)

    def _update_holding_on_sell(self, symbol: str, quantity: Decimal) -> None:
        existing = self.holdings[symbol]
        new_qty = existing.quantity - quantity
        if new_qty == 0:
            del self.holdings[symbol]
        else:
            self.holdings[symbol] = Holding(
                symbol=symbol,
                quantity=new_qty,
                average_cost=existing.average_cost,
            )

    # ------------------------------------------------------------------ #
    # Target allocation
    # ------------------------------------------------------------------ #

    def set_target_allocations(self, allocations: List[TargetAllocation]) -> None:
        """Set target asset-type allocations. Percentages should sum to 100."""
        total = sum(a.target_pct for a in allocations)
        if abs(total - Decimal("100")) > Decimal("0.01"):
            raise ValueError(f"Target allocations must sum to 100%, got {total}%")
        self.target_allocations = list(allocations)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self, path: Path) -> None:
        """Serialize the portfolio to a JSON file."""
        data = {
            "schema_version": _PORTFOLIO_SCHEMA_VERSION,
            "name": self.name,
            "cash_balance": str(self.cash_balance),
            "assets": [a.to_dict() for a in self.assets.values()],
            "holdings": [h.to_dict() for h in self.holdings.values()],
            "transactions": [t.to_dict() for t in self.transactions],
            "target_allocations": [ta.to_dict() for ta in self.target_allocations],
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path) -> "Portfolio":
        """Deserialize a portfolio from a JSON file."""
        path = Path(path)
        data = json.loads(path.read_text())
        portfolio = cls(name=data.get("name", "My Portfolio"))
        portfolio.cash_balance = Decimal(data.get("cash_balance", "0"))
        for a in data.get("assets", []):
            asset = Asset.from_dict(a)
            portfolio.assets[asset.symbol] = asset
        for h in data.get("holdings", []):
            holding = Holding.from_dict(h)
            portfolio.holdings[holding.symbol] = holding
        portfolio.transactions = [Transaction.from_dict(t) for t in data.get("transactions", [])]
        portfolio.target_allocations = [
            TargetAllocation.from_dict(ta) for ta in data.get("target_allocations", [])
        ]
        return portfolio

    # ------------------------------------------------------------------ #
    # Convenience queries
    # ------------------------------------------------------------------ #

    def total_invested(self) -> Decimal:
        """Sum of all deposits minus withdrawals (net invested cash)."""
        total = Decimal("0")
        for txn in self.transactions:
            if txn.transaction_type == TransactionType.DEPOSIT:
                total += txn.quantity
            elif txn.transaction_type == TransactionType.WITHDRAWAL:
                total -= txn.quantity
        return total

    def get_transactions(
        self,
        symbol: Optional[str] = None,
        txn_type: Optional[TransactionType] = None,
    ) -> List[Transaction]:
        """Return transactions, optionally filtered by symbol and/or type."""
        results = self.transactions
        if symbol:
            s = symbol.upper()
            results = [t for t in results if t.symbol == s]
        if txn_type:
            results = [t for t in results if t.transaction_type == txn_type]
        return results
