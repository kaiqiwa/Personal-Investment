"""Tests for core data models."""

from decimal import Decimal
from datetime import date

import pytest

from investment.models import (
    Asset,
    AssetType,
    Holding,
    TargetAllocation,
    Transaction,
    TransactionType,
)


class TestAsset:
    def test_symbol_uppercased(self):
        asset = Asset(symbol="aapl", name="Apple Inc.", asset_type=AssetType.STOCK)
        assert asset.symbol == "AAPL"

    def test_default_currency_is_usd(self):
        asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type=AssetType.STOCK)
        assert asset.currency == "USD"

    def test_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            Asset(symbol="", name="Apple Inc.", asset_type=AssetType.STOCK)

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name cannot be empty"):
            Asset(symbol="AAPL", name="", asset_type=AssetType.STOCK)

    def test_to_dict_round_trip(self):
        asset = Asset(symbol="BTC", name="Bitcoin", asset_type=AssetType.CRYPTO, currency="USD")
        assert Asset.from_dict(asset.to_dict()) == asset


class TestTransaction:
    def test_buy_total_cost_includes_fees(self):
        txn = Transaction(
            transaction_id="t1",
            transaction_type=TransactionType.BUY,
            symbol="AAPL",
            quantity=Decimal("10"),
            price=Decimal("150"),
            transaction_date=date(2024, 1, 1),
            fees=Decimal("5"),
        )
        assert txn.total_cost == Decimal("1505")

    def test_sell_total_cost_is_negative_proceeds(self):
        txn = Transaction(
            transaction_id="t2",
            transaction_type=TransactionType.SELL,
            symbol="AAPL",
            quantity=Decimal("5"),
            price=Decimal("160"),
            transaction_date=date(2024, 1, 2),
            fees=Decimal("5"),
        )
        # sell → negative means cash inflow
        assert txn.total_cost == Decimal("-795")  # -(5*160 - 5)

    def test_dividend_total_cost_is_negative(self):
        txn = Transaction(
            transaction_id="t3",
            transaction_type=TransactionType.DIVIDEND,
            symbol="AAPL",
            quantity=Decimal("10"),
            price=Decimal("2"),
            transaction_date=date(2024, 1, 3),
        )
        assert txn.total_cost == Decimal("-20")

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            Transaction(
                transaction_id="t4",
                transaction_type=TransactionType.BUY,
                symbol="AAPL",
                quantity=Decimal("-1"),
                price=Decimal("100"),
                transaction_date=date(2024, 1, 1),
            )

    def test_to_dict_round_trip(self):
        txn = Transaction(
            transaction_id="t5",
            transaction_type=TransactionType.BUY,
            symbol="MSFT",
            quantity=Decimal("3"),
            price=Decimal("300"),
            transaction_date=date(2024, 3, 15),
            fees=Decimal("1.5"),
            notes="test",
        )
        assert Transaction.from_dict(txn.to_dict()) == txn


class TestHolding:
    def test_total_cost_basis(self):
        h = Holding(symbol="AAPL", quantity=Decimal("10"), average_cost=Decimal("150"))
        assert h.total_cost_basis == Decimal("1500")

    def test_current_value(self):
        h = Holding(symbol="AAPL", quantity=Decimal("10"), average_cost=Decimal("150"))
        assert h.current_value(Decimal("200")) == Decimal("2000")

    def test_unrealized_gain(self):
        h = Holding(symbol="AAPL", quantity=Decimal("10"), average_cost=Decimal("150"))
        assert h.unrealized_gain(Decimal("200")) == Decimal("500")

    def test_unrealized_gain_pct(self):
        h = Holding(symbol="AAPL", quantity=Decimal("10"), average_cost=Decimal("100"))
        pct = h.unrealized_gain_pct(Decimal("120"))
        assert pct == Decimal("20")

    def test_unrealized_gain_pct_zero_cost(self):
        h = Holding(symbol="AAPL", quantity=Decimal("10"), average_cost=Decimal("0"))
        assert h.unrealized_gain_pct(Decimal("100")) is None

    def test_to_dict_round_trip(self):
        h = Holding(symbol="TSLA", quantity=Decimal("5"), average_cost=Decimal("250"))
        assert Holding.from_dict(h.to_dict()) == h


class TestTargetAllocation:
    def test_to_dict_round_trip(self):
        ta = TargetAllocation(asset_type=AssetType.STOCK, target_pct=Decimal("60"))
        assert TargetAllocation.from_dict(ta.to_dict()) == ta
