"""Turn the rulebook's charges into proportional cost rates for the backtester.

A backtest spans years, but the rulebook only records rates from late 2024.
The model therefore applies the rates in force on ONE date (today by default)
to every simulated trade. That answers "what would this strategy cost under
today's charges", which is the question that matters going forward; it is not
a reconstruction of historical charges.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from .charges import india_leg, us_equity_leg

_PROBE_PRICE, _PROBE_QTY = 100, 10_000  # turnover of 10,00,000; every statutory levy is proportional


@dataclass(frozen=True)
class CostModel:
    buy_frac: float
    sell_frac: float
    fixed_per_order: float
    description: str


def india_delivery(as_of: Optional[date] = None, brokerage_per_order: float = 0.0, dp_charge: float = 0.0) -> CostModel:
    """NSE delivery equity. ``dp_charge`` (sell side only) is spread evenly over both orders."""
    day = as_of or date.today()
    turnover = Decimal(_PROBE_PRICE * _PROBE_QTY)
    buy = india_leg("equity_delivery", "buy", _PROBE_PRICE, _PROBE_QTY, day).total / turnover
    sell = india_leg("equity_delivery", "sell", _PROBE_PRICE, _PROBE_QTY, day).total / turnover
    return CostModel(
        float(buy), float(sell), brokerage_per_order * 1.18 + dp_charge / 2,
        f"NSE delivery charges in force on {day.isoformat()} applied to all trades; "
        f"brokerage Rs {brokerage_per_order} per order plus 18% GST; DP charge Rs {dp_charge} per sell",
    )


def us_equity(as_of: Optional[date] = None, commission_per_order: float = 0.0) -> CostModel:
    """US stocks: the SEC fee on sells. The FINRA per-share fee (under a cent per 50 shares) is ignored."""
    day = as_of or date.today()
    sec = us_equity_leg("sell", _PROBE_PRICE, _PROBE_QTY, day).amount("sec_fee") / Decimal(_PROBE_PRICE * _PROBE_QTY)
    return CostModel(
        0.0, float(sec), commission_per_order,
        f"US SEC fee in force on {day.isoformat()} applied to all sells; commission ${commission_per_order} per order",
    )
