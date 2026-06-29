"""Core data models for the personal investment framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class AssetType(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    BOND = "bond"
    CRYPTO = "crypto"
    CASH = "cash"
    REAL_ESTATE = "real_estate"
    COMMODITY = "commodity"
    OTHER = "other"


class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"


@dataclass
class Asset:
    """Represents a tradable asset."""

    symbol: str
    name: str
    asset_type: AssetType
    currency: str = "USD"

    def __post_init__(self) -> None:
        self.symbol = self.symbol.upper()
        if not self.symbol:
            raise ValueError("Asset symbol cannot be empty")
        if not self.name:
            raise ValueError("Asset name cannot be empty")

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "asset_type": self.asset_type.value,
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Asset":
        return cls(
            symbol=data["symbol"],
            name=data["name"],
            asset_type=AssetType(data["asset_type"]),
            currency=data.get("currency", "USD"),
        )


@dataclass
class Transaction:
    """Records a single portfolio transaction."""

    transaction_id: str
    transaction_type: TransactionType
    symbol: str
    quantity: Decimal
    price: Decimal
    transaction_date: date
    fees: Decimal = Decimal("0")
    notes: str = ""

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError("Quantity cannot be negative")
        if self.price < 0:
            raise ValueError("Price cannot be negative")
        if self.fees < 0:
            raise ValueError("Fees cannot be negative")
        self.symbol = self.symbol.upper()

    @property
    def total_cost(self) -> Decimal:
        """Total cost including fees (positive = cash outflow)."""
        if self.transaction_type == TransactionType.BUY:
            return self.quantity * self.price + self.fees
        elif self.transaction_type == TransactionType.SELL:
            return -(self.quantity * self.price - self.fees)
        elif self.transaction_type == TransactionType.DIVIDEND:
            return -self.quantity * self.price
        elif self.transaction_type == TransactionType.DEPOSIT:
            return -self.quantity
        elif self.transaction_type == TransactionType.WITHDRAWAL:
            return self.quantity
        return Decimal("0")

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "transaction_type": self.transaction_type.value,
            "symbol": self.symbol,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "transaction_date": self.transaction_date.isoformat(),
            "fees": str(self.fees),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        return cls(
            transaction_id=data["transaction_id"],
            transaction_type=TransactionType(data["transaction_type"]),
            symbol=data["symbol"],
            quantity=Decimal(data["quantity"]),
            price=Decimal(data["price"]),
            transaction_date=date.fromisoformat(data["transaction_date"]),
            fees=Decimal(data.get("fees", "0")),
            notes=data.get("notes", ""),
        )


@dataclass
class Holding:
    """Current holding of an asset in the portfolio."""

    symbol: str
    quantity: Decimal
    average_cost: Decimal

    @property
    def total_cost_basis(self) -> Decimal:
        return self.quantity * self.average_cost

    def current_value(self, current_price: Decimal) -> Decimal:
        return self.quantity * current_price

    def unrealized_gain(self, current_price: Decimal) -> Decimal:
        return self.current_value(current_price) - self.total_cost_basis

    def unrealized_gain_pct(self, current_price: Decimal) -> Optional[Decimal]:
        if self.total_cost_basis == 0:
            return None
        return (self.unrealized_gain(current_price) / self.total_cost_basis) * 100

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": str(self.quantity),
            "average_cost": str(self.average_cost),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Holding":
        return cls(
            symbol=data["symbol"],
            quantity=Decimal(data["quantity"]),
            average_cost=Decimal(data["average_cost"]),
        )


@dataclass
class TargetAllocation:
    """Desired allocation for portfolio rebalancing."""

    asset_type: AssetType
    target_pct: Decimal

    def to_dict(self) -> dict:
        return {
            "asset_type": self.asset_type.value,
            "target_pct": str(self.target_pct),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TargetAllocation":
        return cls(
            asset_type=AssetType(data["asset_type"]),
            target_pct=Decimal(data["target_pct"]),
        )
