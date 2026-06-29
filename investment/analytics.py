"""Analytics module: portfolio metrics, allocation analysis, and rebalancing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from .models import Asset, AssetType, Holding, TargetAllocation
from .portfolio import Portfolio


@dataclass
class HoldingSnapshot:
    """Value and performance data for a single holding."""

    symbol: str
    asset_type: AssetType
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal
    current_value: Decimal
    cost_basis: Decimal
    unrealized_gain: Decimal
    unrealized_gain_pct: Optional[Decimal]
    portfolio_weight_pct: Decimal


@dataclass
class AllocationBreakdown:
    """Actual vs target allocation for an asset type."""

    asset_type: AssetType
    current_value: Decimal
    current_pct: Decimal
    target_pct: Optional[Decimal]
    drift_pct: Optional[Decimal]


@dataclass
class RebalanceTrade:
    """A suggested trade to bring allocations back to target."""

    symbol: str
    action: str          # "BUY" or "SELL"
    suggested_value: Decimal
    current_weight_pct: Decimal
    target_weight_pct: Decimal


def total_portfolio_value(
    portfolio: Portfolio,
    prices: Dict[str, Decimal],
) -> Decimal:
    """
    Calculate total portfolio value (holdings + cash).

    :param portfolio: the Portfolio instance
    :param prices: mapping of symbol -> current price
    """
    value = portfolio.cash_balance
    for symbol, holding in portfolio.holdings.items():
        price = prices.get(symbol)
        if price is None:
            raise ValueError(f"No price provided for '{symbol}'")
        value += holding.current_value(price)
    return value


def holding_snapshots(
    portfolio: Portfolio,
    prices: Dict[str, Decimal],
) -> List[HoldingSnapshot]:
    """
    Return a snapshot of each holding with current performance metrics.

    :param portfolio: the Portfolio instance
    :param prices: mapping of symbol -> current price
    """
    total = total_portfolio_value(portfolio, prices)
    snapshots: List[HoldingSnapshot] = []

    for symbol, holding in portfolio.holdings.items():
        price = prices.get(symbol)
        if price is None:
            raise ValueError(f"No price provided for '{symbol}'")
        asset = portfolio.get_asset(symbol)
        asset_type = asset.asset_type if asset else AssetType.OTHER

        cur_value = holding.current_value(price)
        cost_basis = holding.total_cost_basis
        gain = holding.unrealized_gain(price)
        gain_pct = holding.unrealized_gain_pct(price)
        weight = (cur_value / total * 100) if total > 0 else Decimal("0")

        snapshots.append(
            HoldingSnapshot(
                symbol=symbol,
                asset_type=asset_type,
                quantity=holding.quantity,
                average_cost=holding.average_cost,
                current_price=price,
                current_value=cur_value,
                cost_basis=cost_basis,
                unrealized_gain=gain,
                unrealized_gain_pct=gain_pct,
                portfolio_weight_pct=weight,
            )
        )

    return sorted(snapshots, key=lambda s: s.current_value, reverse=True)


def allocation_breakdown(
    portfolio: Portfolio,
    prices: Dict[str, Decimal],
) -> List[AllocationBreakdown]:
    """
    Show current allocation by asset type, with drift from targets if set.

    :param portfolio: the Portfolio instance
    :param prices: mapping of symbol -> current price
    """
    total = total_portfolio_value(portfolio, prices)
    type_values: Dict[AssetType, Decimal] = {t: Decimal("0") for t in AssetType}

    # Cash holdings
    type_values[AssetType.CASH] += portfolio.cash_balance

    for symbol, holding in portfolio.holdings.items():
        price = prices.get(symbol)
        if price is None:
            raise ValueError(f"No price provided for '{symbol}'")
        asset = portfolio.get_asset(symbol)
        asset_type = asset.asset_type if asset else AssetType.OTHER
        type_values[asset_type] += holding.current_value(price)

    target_map: Dict[AssetType, Decimal] = {
        ta.asset_type: ta.target_pct for ta in portfolio.target_allocations
    }

    result: List[AllocationBreakdown] = []
    for asset_type, value in type_values.items():
        if value == 0 and asset_type not in target_map:
            continue
        current_pct = (value / total * 100) if total > 0 else Decimal("0")
        target_pct = target_map.get(asset_type)
        drift = (current_pct - target_pct) if target_pct is not None else None
        result.append(
            AllocationBreakdown(
                asset_type=asset_type,
                current_value=value,
                current_pct=current_pct,
                target_pct=target_pct,
                drift_pct=drift,
            )
        )

    return sorted(result, key=lambda a: a.current_value, reverse=True)


def rebalance_suggestions(
    portfolio: Portfolio,
    prices: Dict[str, Decimal],
    threshold_pct: Decimal = Decimal("5"),
) -> List[RebalanceTrade]:
    """
    Suggest trades to rebalance the portfolio toward target allocations.

    Only returns suggestions where the drift exceeds *threshold_pct*.

    :param portfolio: the Portfolio instance
    :param prices: mapping of symbol -> current price
    :param threshold_pct: minimum drift (%) before a suggestion is made
    """
    if not portfolio.target_allocations:
        return []

    total = total_portfolio_value(portfolio, prices)
    if total == 0:
        return []

    breakdown = allocation_breakdown(portfolio, prices)
    suggestions: List[RebalanceTrade] = []

    for alloc in breakdown:
        if alloc.target_pct is None or alloc.drift_pct is None:
            continue
        if abs(alloc.drift_pct) < threshold_pct:
            continue

        target_value = total * alloc.target_pct / 100
        diff = target_value - alloc.current_value
        action = "BUY" if diff > 0 else "SELL"

        # Pick the largest holding of this asset type as representative symbol
        candidate_symbol = _largest_holding_by_type(portfolio, prices, alloc.asset_type)
        if candidate_symbol is None and action == "BUY":
            candidate_symbol = f"<{alloc.asset_type.value.upper()}>"

        if candidate_symbol:
            suggestions.append(
                RebalanceTrade(
                    symbol=candidate_symbol,
                    action=action,
                    suggested_value=abs(diff),
                    current_weight_pct=alloc.current_pct,
                    target_weight_pct=alloc.target_pct,
                )
            )

    return suggestions


def portfolio_return(
    portfolio: Portfolio,
    prices: Dict[str, Decimal],
) -> Dict[str, Decimal]:
    """
    Calculate overall portfolio return metrics.

    Returns a dict with:
    - total_value: current market value including cash
    - total_invested: net cash deposited
    - total_gain: total unrealized + income gain
    - total_return_pct: percentage return on invested capital
    """
    total = total_portfolio_value(portfolio, prices)
    invested = portfolio.total_invested()
    gain = total - invested
    return_pct = (gain / invested * 100) if invested > 0 else Decimal("0")

    return {
        "total_value": total,
        "total_invested": invested,
        "total_gain": gain,
        "total_return_pct": return_pct,
    }


# ------------------------------------------------------------------ #
# Internal helpers
# ------------------------------------------------------------------ #

def _largest_holding_by_type(
    portfolio: Portfolio,
    prices: Dict[str, Decimal],
    asset_type: AssetType,
) -> Optional[str]:
    """Return the symbol of the largest-value holding of a given asset type."""
    best_symbol: Optional[str] = None
    best_value = Decimal("0")
    for symbol, holding in portfolio.holdings.items():
        asset = portfolio.get_asset(symbol)
        if asset and asset.asset_type == asset_type:
            price = prices.get(symbol, Decimal("0"))
            value = holding.current_value(price)
            if value > best_value:
                best_value = value
                best_symbol = symbol
    return best_symbol
