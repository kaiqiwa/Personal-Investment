"""Tests for the Portfolio manager."""

from decimal import Decimal
from datetime import date
from pathlib import Path
import tempfile

import pytest

from investment.models import Asset, AssetType, TargetAllocation, TransactionType
from investment.portfolio import Portfolio


@pytest.fixture
def stock_asset():
    return Asset(symbol="AAPL", name="Apple Inc.", asset_type=AssetType.STOCK)


@pytest.fixture
def etf_asset():
    return Asset(symbol="SPY", name="S&P 500 ETF", asset_type=AssetType.ETF)


@pytest.fixture
def funded_portfolio(stock_asset, etf_asset):
    p = Portfolio(name="Test")
    p.add_asset(stock_asset)
    p.add_asset(etf_asset)
    p.deposit(Decimal("10000"))
    return p


class TestPortfolioDeposit:
    def test_deposit_increases_cash(self):
        p = Portfolio()
        p.deposit(Decimal("5000"))
        assert p.cash_balance == Decimal("5000")

    def test_deposit_records_transaction(self):
        p = Portfolio()
        p.deposit(Decimal("1000"))
        assert len(p.transactions) == 1
        assert p.transactions[0].transaction_type == TransactionType.DEPOSIT

    def test_deposit_zero_raises(self):
        p = Portfolio()
        with pytest.raises(ValueError):
            p.deposit(Decimal("0"))

    def test_deposit_negative_raises(self):
        p = Portfolio()
        with pytest.raises(ValueError):
            p.deposit(Decimal("-100"))


class TestPortfolioWithdraw:
    def test_withdraw_decreases_cash(self):
        p = Portfolio()
        p.deposit(Decimal("1000"))
        p.withdraw(Decimal("300"))
        assert p.cash_balance == Decimal("700")

    def test_withdraw_insufficient_funds_raises(self):
        p = Portfolio()
        p.deposit(Decimal("100"))
        with pytest.raises(ValueError, match="Insufficient cash"):
            p.withdraw(Decimal("200"))

    def test_withdraw_records_transaction(self):
        p = Portfolio()
        p.deposit(Decimal("1000"))
        p.withdraw(Decimal("200"))
        txns = p.get_transactions(txn_type=TransactionType.WITHDRAWAL)
        assert len(txns) == 1


class TestPortfolioBuy:
    def test_buy_creates_holding(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("150"))
        assert "AAPL" in funded_portfolio.holdings
        assert funded_portfolio.holdings["AAPL"].quantity == Decimal("10")

    def test_buy_reduces_cash(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("150"))
        assert funded_portfolio.cash_balance == Decimal("8500")

    def test_buy_with_fees_reduces_cash(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("150"), fees=Decimal("10"))
        assert funded_portfolio.cash_balance == Decimal("8490")

    def test_buy_average_cost_on_multiple_buys(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("100"))
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("200"))
        holding = funded_portfolio.holdings["AAPL"]
        assert holding.average_cost == Decimal("150")
        assert holding.quantity == Decimal("20")

    def test_buy_insufficient_cash_raises(self, stock_asset):
        p = Portfolio()
        p.add_asset(stock_asset)
        p.deposit(Decimal("100"))
        with pytest.raises(ValueError, match="Insufficient cash"):
            p.buy("AAPL", Decimal("10"), Decimal("150"))

    def test_buy_unknown_asset_raises(self):
        p = Portfolio()
        p.deposit(Decimal("10000"))
        with pytest.raises(ValueError, match="Unknown asset"):
            p.buy("ZZZZZ", Decimal("1"), Decimal("100"))

    def test_buy_records_transaction(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("5"), Decimal("200"))
        txns = funded_portfolio.get_transactions(symbol="AAPL", txn_type=TransactionType.BUY)
        assert len(txns) == 1


class TestPortfolioSell:
    def test_sell_reduces_holding(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("100"))
        funded_portfolio.sell("AAPL", Decimal("4"), Decimal("120"))
        assert funded_portfolio.holdings["AAPL"].quantity == Decimal("6")

    def test_sell_all_removes_holding(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("100"))
        funded_portfolio.sell("AAPL", Decimal("10"), Decimal("120"))
        assert "AAPL" not in funded_portfolio.holdings

    def test_sell_increases_cash(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("100"))
        cash_before = funded_portfolio.cash_balance
        funded_portfolio.sell("AAPL", Decimal("5"), Decimal("120"))
        assert funded_portfolio.cash_balance == cash_before + Decimal("600")

    def test_sell_more_than_held_raises(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("5"), Decimal("100"))
        with pytest.raises(ValueError, match="Cannot sell"):
            funded_portfolio.sell("AAPL", Decimal("10"), Decimal("100"))

    def test_sell_not_held_raises(self, funded_portfolio):
        with pytest.raises(ValueError, match="No holding found"):
            funded_portfolio.sell("AAPL", Decimal("1"), Decimal("100"))


class TestPortfolioDividend:
    def test_dividend_increases_cash(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("100"))
        cash_before = funded_portfolio.cash_balance
        funded_portfolio.record_dividend("AAPL", Decimal("2"))
        assert funded_portfolio.cash_balance > cash_before

    def test_dividend_amount(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("100"))
        cash_before = funded_portfolio.cash_balance
        funded_portfolio.record_dividend("AAPL", Decimal("2"))
        assert funded_portfolio.cash_balance == cash_before + Decimal("20")

    def test_dividend_not_held_raises(self, funded_portfolio):
        with pytest.raises(ValueError, match="No holding found"):
            funded_portfolio.record_dividend("AAPL", Decimal("1"))


class TestPortfolioTargetAllocation:
    def test_set_valid_target(self):
        p = Portfolio()
        allocations = [
            TargetAllocation(asset_type=AssetType.STOCK, target_pct=Decimal("60")),
            TargetAllocation(asset_type=AssetType.BOND, target_pct=Decimal("30")),
            TargetAllocation(asset_type=AssetType.CASH, target_pct=Decimal("10")),
        ]
        p.set_target_allocations(allocations)
        assert len(p.target_allocations) == 3

    def test_target_not_summing_to_100_raises(self):
        p = Portfolio()
        with pytest.raises(ValueError, match="sum to 100"):
            p.set_target_allocations([
                TargetAllocation(asset_type=AssetType.STOCK, target_pct=Decimal("50")),
                TargetAllocation(asset_type=AssetType.BOND, target_pct=Decimal("40")),
            ])


class TestPortfolioPersistence:
    def test_save_and_load(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("10"), Decimal("150"))
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        try:
            funded_portfolio.save(path)
            loaded = Portfolio.load(path)
            assert loaded.name == funded_portfolio.name
            assert loaded.cash_balance == funded_portfolio.cash_balance
            assert "AAPL" in loaded.holdings
            assert loaded.holdings["AAPL"].quantity == Decimal("10")
            assert len(loaded.transactions) == len(funded_portfolio.transactions)
        finally:
            path.unlink(missing_ok=True)


class TestPortfolioQueries:
    def test_total_invested(self):
        p = Portfolio()
        p.deposit(Decimal("5000"))
        p.deposit(Decimal("3000"))
        p.withdraw(Decimal("1000"))
        assert p.total_invested() == Decimal("7000")

    def test_get_transactions_filtered_by_symbol(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("5"), Decimal("100"))
        funded_portfolio.buy("SPY", Decimal("2"), Decimal("400"))
        aapl_txns = funded_portfolio.get_transactions(symbol="AAPL")
        assert all(t.symbol == "AAPL" for t in aapl_txns)

    def test_get_transactions_filtered_by_type(self, funded_portfolio):
        funded_portfolio.buy("AAPL", Decimal("5"), Decimal("100"))
        buy_txns = funded_portfolio.get_transactions(txn_type=TransactionType.BUY)
        assert all(t.transaction_type == TransactionType.BUY for t in buy_txns)
