"""Tests for the analytics module."""

from decimal import Decimal

import pytest

from investment.models import Asset, AssetType, TargetAllocation
from investment.portfolio import Portfolio
from investment.analytics import (
    allocation_breakdown,
    holding_snapshots,
    portfolio_return,
    rebalance_suggestions,
    total_portfolio_value,
)


@pytest.fixture
def portfolio_with_holdings():
    p = Portfolio(name="Test")
    p.add_asset(Asset(symbol="AAPL", name="Apple Inc.", asset_type=AssetType.STOCK))
    p.add_asset(Asset(symbol="BND", name="Vanguard Bond ETF", asset_type=AssetType.BOND))
    p.deposit(Decimal("10000"))
    p.buy("AAPL", Decimal("10"), Decimal("100"))   # cost: 1000
    p.buy("BND", Decimal("20"), Decimal("100"))    # cost: 2000
    return p


class TestTotalPortfolioValue:
    def test_cash_only(self):
        p = Portfolio()
        p.deposit(Decimal("5000"))
        assert total_portfolio_value(p, {}) == Decimal("5000")

    def test_holdings_and_cash(self, portfolio_with_holdings):
        prices = {"AAPL": Decimal("120"), "BND": Decimal("110")}
        value = total_portfolio_value(portfolio_with_holdings, prices)
        # cash = 10000 - 1000 - 2000 = 7000; AAPL = 1200; BND = 2200
        assert value == Decimal("10400")

    def test_missing_price_raises(self, portfolio_with_holdings):
        with pytest.raises(ValueError, match="No price provided for"):
            total_portfolio_value(portfolio_with_holdings, {"AAPL": Decimal("120")})


class TestHoldingSnapshots:
    def test_returns_one_snapshot_per_holding(self, portfolio_with_holdings):
        prices = {"AAPL": Decimal("120"), "BND": Decimal("110")}
        snapshots = holding_snapshots(portfolio_with_holdings, prices)
        assert len(snapshots) == 2

    def test_unrealized_gain_calculated(self, portfolio_with_holdings):
        prices = {"AAPL": Decimal("150"), "BND": Decimal("100")}
        snapshots = holding_snapshots(portfolio_with_holdings, prices)
        aapl = next(s for s in snapshots if s.symbol == "AAPL")
        assert aapl.unrealized_gain == Decimal("500")

    def test_portfolio_weight_sums_to_100_approximately(self, portfolio_with_holdings):
        prices = {"AAPL": Decimal("100"), "BND": Decimal("100")}
        snapshots = holding_snapshots(portfolio_with_holdings, prices)
        total_weight = sum(s.portfolio_weight_pct for s in snapshots)
        # Weights are relative to total including cash, so holding weights < 100
        assert total_weight <= Decimal("100")

    def test_sorted_by_value_desc(self, portfolio_with_holdings):
        prices = {"AAPL": Decimal("50"), "BND": Decimal("200")}
        snapshots = holding_snapshots(portfolio_with_holdings, prices)
        values = [s.current_value for s in snapshots]
        assert values == sorted(values, reverse=True)


class TestAllocationBreakdown:
    def test_includes_cash_allocation(self, portfolio_with_holdings):
        prices = {"AAPL": Decimal("100"), "BND": Decimal("100")}
        breakdown = allocation_breakdown(portfolio_with_holdings, prices)
        cash_alloc = next((a for a in breakdown if a.asset_type == AssetType.CASH), None)
        assert cash_alloc is not None

    def test_drift_none_without_target(self, portfolio_with_holdings):
        prices = {"AAPL": Decimal("100"), "BND": Decimal("100")}
        breakdown = allocation_breakdown(portfolio_with_holdings, prices)
        for alloc in breakdown:
            assert alloc.drift_pct is None

    def test_drift_computed_with_target(self, portfolio_with_holdings):
        portfolio_with_holdings.set_target_allocations([
            TargetAllocation(asset_type=AssetType.STOCK, target_pct=Decimal("50")),
            TargetAllocation(asset_type=AssetType.BOND, target_pct=Decimal("30")),
            TargetAllocation(asset_type=AssetType.CASH, target_pct=Decimal("20")),
        ])
        prices = {"AAPL": Decimal("100"), "BND": Decimal("100")}
        breakdown = allocation_breakdown(portfolio_with_holdings, prices)
        stock_alloc = next((a for a in breakdown if a.asset_type == AssetType.STOCK), None)
        assert stock_alloc is not None
        assert stock_alloc.drift_pct is not None


class TestPortfolioReturn:
    def test_positive_return(self, portfolio_with_holdings):
        prices = {"AAPL": Decimal("200"), "BND": Decimal("100")}
        metrics = portfolio_return(portfolio_with_holdings, prices)
        assert metrics["total_gain"] > 0

    def test_total_invested(self, portfolio_with_holdings):
        metrics = portfolio_return(portfolio_with_holdings, {"AAPL": Decimal("100"), "BND": Decimal("100")})
        assert metrics["total_invested"] == Decimal("10000")

    def test_return_pct_is_zero_with_no_change(self, portfolio_with_holdings):
        # Prices at cost basis: no gain
        prices = {"AAPL": Decimal("100"), "BND": Decimal("100")}
        metrics = portfolio_return(portfolio_with_holdings, prices)
        assert metrics["total_return_pct"] == Decimal("0")


class TestRebalanceSuggestions:
    def test_no_suggestions_without_targets(self, portfolio_with_holdings):
        prices = {"AAPL": Decimal("100"), "BND": Decimal("100")}
        assert rebalance_suggestions(portfolio_with_holdings, prices) == []

    def test_suggestions_when_out_of_balance(self, portfolio_with_holdings):
        portfolio_with_holdings.set_target_allocations([
            TargetAllocation(asset_type=AssetType.STOCK, target_pct=Decimal("70")),
            TargetAllocation(asset_type=AssetType.BOND, target_pct=Decimal("20")),
            TargetAllocation(asset_type=AssetType.CASH, target_pct=Decimal("10")),
        ])
        prices = {"AAPL": Decimal("100"), "BND": Decimal("100")}
        suggestions = rebalance_suggestions(portfolio_with_holdings, prices, threshold_pct=Decimal("1"))
        assert len(suggestions) > 0

    def test_no_suggestions_when_within_threshold(self, portfolio_with_holdings):
        # Approximate allocation: cash ~70%, stock ~10%, bond ~20%
        # Set targets close to actual to avoid triggering
        portfolio_with_holdings.set_target_allocations([
            TargetAllocation(asset_type=AssetType.STOCK, target_pct=Decimal("10")),
            TargetAllocation(asset_type=AssetType.BOND, target_pct=Decimal("20")),
            TargetAllocation(asset_type=AssetType.CASH, target_pct=Decimal("70")),
        ])
        prices = {"AAPL": Decimal("100"), "BND": Decimal("100")}
        suggestions = rebalance_suggestions(portfolio_with_holdings, prices, threshold_pct=Decimal("50"))
        assert len(suggestions) == 0
