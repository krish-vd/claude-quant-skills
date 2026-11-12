"""Risk-based position sizing for cash equities, futures and long options.

The rule is the same everywhere: risk a fixed fraction of the account, and let
the distance between entry and stop decide the size. Sizes are always rounded
DOWN, so the planned loss never exceeds the risk budget.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import ROUND_FLOOR, Decimal
from typing import Optional

from .charges import D, Number


@dataclass
class SizeResult:
    instrument: str
    direction: str
    units: Decimal  # shares, or contracts/lots
    quantity: Decimal  # shares or underlying units (lots x lot size)
    risk_budget: Decimal
    risk_per_unit: Decimal
    planned_loss: Decimal
    planned_loss_pct: Decimal
    position_value: Decimal
    position_pct_of_account: Decimal
    binding_constraint: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in asdict(self).items()}


def _check_common(account: Decimal, risk_pct: Decimal, entry: Decimal, stop: Decimal) -> str:
    if account <= 0:
        raise ValueError("account size must be positive")
    if not (Decimal(0) < risk_pct <= Decimal(100)):
        raise ValueError("risk_pct must be between 0 and 100")
    if entry <= 0 or stop <= 0:
        raise ValueError("entry and stop must be positive")
    if entry == stop:
        raise ValueError("stop cannot equal entry")
    return "long" if stop < entry else "short"


def _floor(value: Decimal, step: Decimal = Decimal(1)) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def size_cash(
    account: Number,
    risk_pct: Number,
    entry: Number,
    stop: Number,
    max_position_pct: Optional[Number] = None,
    cost_per_share: Number = 0,
    fractional_step: Optional[Number] = None,
) -> SizeResult:
    """Shares to trade so that a stop-out loses at most ``risk_pct`` of the account.

    ``cost_per_share`` is the round-trip cost per share (charges and expected
    slippage); it is added to the per-share risk. ``fractional_step`` allows
    fractional shares (for example 0.0001) where the broker supports them.
    Direction is inferred: a stop below entry is a long, above is a short.
    """
    account_d, risk_d, entry_d, stop_d = D(account), D(risk_pct), D(entry), D(stop)
    direction = _check_common(account_d, risk_d, entry_d, stop_d)
    step = D(fractional_step) if fractional_step else Decimal(1)
    risk_budget = account_d * risk_d / 100
    risk_per_share = abs(entry_d - stop_d) + D(cost_per_share)

    shares = _floor(risk_budget / risk_per_share, step)
    binding = "risk"
    notes: list[str] = []
    if max_position_pct is not None:
        cap_shares = _floor(account_d * D(max_position_pct) / 100 / entry_d, step)
        if cap_shares < shares:
            shares, binding = cap_shares, "max_position_pct"
    if direction == "long":
        affordable = _floor(account_d / entry_d, step)
        if affordable < shares:
            shares, binding = affordable, "account_cash"
            notes.append("Size limited to what the account can buy without leverage.")
    if shares <= 0:
        notes.append("Risk budget is smaller than the risk of one share: no position.")
    planned_loss = shares * risk_per_share
    value = shares * entry_d
    return SizeResult(
        "cash", direction, shares, shares, risk_budget, risk_per_share, planned_loss,
        planned_loss / account_d * 100, value, value / account_d * 100, binding, notes,
    )


def size_futures(
    account: Number,
    risk_pct: Number,
    entry: Number,
    stop: Number,
    multiplier: Number,
    margin_per_contract: Optional[Number] = None,
    cost_per_contract: Number = 0,
) -> SizeResult:
    """Contracts (lots) to trade. ``multiplier`` is the currency value of a 1.0
    price move for one contract: the lot size for NSE futures, the contract
    multiplier for MCX and US futures.
    """
    account_d, risk_d, entry_d, stop_d, mult = D(account), D(risk_pct), D(entry), D(stop), D(multiplier)
    direction = _check_common(account_d, risk_d, entry_d, stop_d)
    if mult <= 0:
        raise ValueError("multiplier must be positive")
    risk_budget = account_d * risk_d / 100
    risk_per_contract = abs(entry_d - stop_d) * mult + D(cost_per_contract)
    contracts = _floor(risk_budget / risk_per_contract)
    binding = "risk"
    notes: list[str] = []
    if margin_per_contract is not None:
        by_margin = _floor(account_d / D(margin_per_contract))
        if by_margin < contracts:
            contracts, binding = by_margin, "margin"
    else:
        notes.append("Margin not checked: pass margin_per_contract from your broker's margin calculator.")
    if contracts <= 0:
        notes.append("Risk budget is smaller than the risk of one contract: no position. Use a smaller contract or a tighter stop.")
    planned_loss = contracts * risk_per_contract
    notional = contracts * entry_d * mult
    return SizeResult(
        "futures", direction, contracts, contracts * mult, risk_budget, risk_per_contract, planned_loss,
        planned_loss / account_d * 100, notional, notional / account_d * 100, binding, notes,
    )


def size_long_option(
    account: Number,
    risk_pct: Number,
    premium: Number,
    lot_size: Number,
    stop_premium: Number = 0,
    cost_per_lot: Number = 0,
) -> SizeResult:
    """Lots of a BOUGHT option. Risk per lot is the premium you would lose:
    the whole premium by default, or premium minus ``stop_premium`` if you plan
    to exit at that premium. Option selling has open-ended risk and is not sized here.
    """
    account_d, risk_d, prem, lot, stop_p = D(account), D(risk_pct), D(premium), D(lot_size), D(stop_premium)
    if account_d <= 0 or prem <= 0 or lot <= 0:
        raise ValueError("account, premium and lot_size must be positive")
    if not (Decimal(0) < risk_d <= Decimal(100)):
        raise ValueError("risk_pct must be between 0 and 100")
    if not (Decimal(0) <= stop_p < prem):
        raise ValueError("stop_premium must be at least 0 and below the premium")
    risk_budget = account_d * risk_d / 100
    risk_per_lot = (prem - stop_p) * lot + D(cost_per_lot)
    lots = _floor(risk_budget / risk_per_lot)
    binding = "risk"
    notes: list[str] = []
    affordable = _floor(account_d / (prem * lot))
    if affordable < lots:
        lots, binding = affordable, "account_cash"
    if stop_p > 0:
        notes.append("A premium stop can gap through on fast moves or at the open; the full premium is the true maximum loss.")
    if lots <= 0:
        notes.append("Risk budget is smaller than the risk of one lot: no position.")
    planned_loss = lots * risk_per_lot
    outlay = lots * prem * lot
    return SizeResult(
        "long_option", "long", lots, lots * lot, risk_budget, risk_per_lot, planned_loss,
        planned_loss / account_d * 100, outlay, outlay / account_d * 100, binding, notes,
    )
